"""Unit + wired tests for the post-GW review wake (#21).

The pure graders (build_scorecard / render_scorecard / review_headline) are
tested against a fixed 15-man fixture whose every number is hand-computed here,
so the model never grades itself — the code does, and the code is checked.
`run_review` is exercised end-to-end over injected edges (same harness posture
as tests/test_brief.py): a fake telegram recorder, a stub assembler, a
StructuredLogger over a StringIO, and a TemporaryDirectory for state/reports/
snapshot/diary.
"""

import csv
import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from daemon.logging_setup import StructuredLogger
from daemon.learnings import LearningsLog
from daemon.review import (ReviewStore, build_scorecard, decision_log_excerpt,
                           latest_finished_gw, load_gw_projections,
                           next_review_gw, render_scorecard, review_headline,
                           run_review, snapshot_path, snapshot_projections,
                           TOP_MISSES)

MINUS = "−"


def _dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# --- the 15-man fixture ------------------------------------------------------

# id -> (web_name, pos, club)
PLAYERS = {
    1: ("Raya", "GKP", "ARS"), 2: ("Gabriel", "DEF", "ARS"),
    3: ("Mitchell", "DEF", "CRY"), 4: ("Shaw", "DEF", "MUN"),
    5: ("Bruno", "MID", "MUN"), 6: ("Mbeumo", "MID", "MUN"),
    7: ("Szoboszlai", "MID", "LIV"), 8: ("Yates", "MID", "NFO"),
    9: ("Haaland", "FWD", "MCI"), 10: ("Joao Pedro", "FWD", "CHE"),
    11: ("Calvert", "FWD", "LEE"), 12: ("PalmerG", "GKP", "IPS"),
    13: ("Diop", "DEF", "IPS"), 14: ("Hughes", "MID", "CRY"),
    15: ("Wissa", "FWD", "BRE"), 20: ("Slater", "MID", "NFO"),
}
LIVE_PTS = {1: 6, 2: 2, 3: 8, 4: 1, 5: 4, 6: 5, 7: 2, 8: 2, 9: 13, 10: 6,
            11: 0, 12: 3, 13: 9, 14: 1, 15: 2, 20: 8}
PROJ_XP = {1: 3.0, 2: 4.0, 3: 3.0, 4: 2.5, 5: 6.0, 6: 5.0, 7: 4.5, 8: 2.0,
           9: 8.0, 10: 5.0, 11: 4.0, 12: 2.0, 13: 2.0, 14: 2.0, 15: 3.0}


def players_index():
    return {pid: {"web_name": w, "pos": p, "team": c}
            for pid, (w, p, c) in PLAYERS.items()}


def live_index():
    return {pid: {"minutes": 90, "total_points": pts, "goals_scored": 0,
                  "assists": 0, "clean_sheets": 0, "bonus": 0}
            for pid, pts in LIVE_PTS.items()}


def projections_by_id():
    return {"by_id": {pid: {"id": pid, "web_name": PLAYERS[pid][0],
                            "pos": PLAYERS[pid][1], "xpts": xp, "xmins": 90.0}
                      for pid, xp in PROJ_XP.items()},
            "by_name": {}}


def entry_picks(entry_history=True):
    picks = []
    for pos in range(1, 12):                       # elements 1..11 start
        picks.append({"element": pos, "position": pos,
                      "multiplier": 2 if pos == 5 else 1,
                      "is_captain": pos == 5, "is_vice_captain": pos == 10})
    for i, el in enumerate((12, 13, 14, 15)):      # bench 12..15
        picks.append({"element": el, "position": 12 + i, "multiplier": 0,
                      "is_captain": False, "is_vice_captain": False})
    out = {"picks": picks}
    if entry_history:
        out["entry_history"] = {"points": 51, "points_on_bench": 6,
                                "rank": 412345, "overall_rank": 3100000,
                                "event_transfers": 1, "event_transfers_cost": 0,
                                "bank": 5}
    return out


def decision(hits=0, captain="Haaland"):
    return {"plan": {"transfers_out": ["Yates"], "transfers_in": ["Slater"],
                     "hits": hits, "starting_xi": [], "captain": captain,
                     "vice": "Joao Pedro", "chip": None, "contingencies": []},
            "status": "locked", "recorded_at": "2026-09-01T10:00:00Z"}


def a_scorecard(**over):
    kw = {"gw": 3, "live": live_index(), "picks": entry_picks(),
          "players": players_index(), "projections": projections_by_id(),
          "decision": decision(), "picks_source": "entry"}
    kw.update(over)
    return build_scorecard(kw["gw"], kw["live"], kw["picks"], kw["players"],
                           kw["projections"], kw["decision"],
                           picks_source=kw["picks_source"])


# --- latest_finished_gw ------------------------------------------------------


class LatestFinishedGwTest(unittest.TestCase):
    def test_data_checked_false_is_skipped(self):
        events = [{"id": 1, "finished": True, "data_checked": True},
                  {"id": 2, "finished": True, "data_checked": False}]
        self.assertEqual(latest_finished_gw(events), 1)

    def test_missing_data_checked_key_is_accepted(self):
        self.assertEqual(latest_finished_gw([{"id": 5, "finished": True}]), 5)

    def test_none_finished_is_none(self):
        self.assertIsNone(latest_finished_gw([{"id": 1, "finished": False}]))
        self.assertIsNone(latest_finished_gw([]))

    def test_highest_finished_wins(self):
        events = [{"id": 1, "finished": True, "data_checked": True},
                  {"id": 3, "finished": True, "data_checked": True},
                  {"id": 2, "finished": True, "data_checked": True}]
        self.assertEqual(latest_finished_gw(events), 3)


# --- snapshot_projections ----------------------------------------------------


class SnapshotProjectionsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = self._tmp.name
        self.src = os.path.join(self.d, "projections.csv")
        fields = ["id", "web_name", "pos", "team", "gw", "now_cost", "xmins",
                  "xpts", "horizon_xpts"]
        with open(self.src, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for gw in (2, 3):
                for pid in (1, 2, 3):
                    w.writerow({"id": pid, "web_name": PLAYERS[pid][0],
                                "pos": PLAYERS[pid][1], "team": PLAYERS[pid][2],
                                "gw": gw, "now_cost": 50, "xmins": 90,
                                "xpts": PROJ_XP[pid], "horizon_xpts": 10})

    def test_writes_only_gw_rows_with_header(self):
        out = os.path.join(self.d, "snap.csv")
        n = snapshot_projections(self.src, 3, out)
        self.assertEqual(n, 3)
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["gw"] == "3" for r in rows))

    def test_missing_source_writes_nothing(self):
        out = os.path.join(self.d, "snap.csv")
        self.assertEqual(snapshot_projections(os.path.join(self.d, "no.csv"),
                                              3, out), 0)
        self.assertFalse(os.path.exists(out))

    def test_no_matching_rows_writes_no_partial_file(self):
        out = os.path.join(self.d, "snap.csv")
        self.assertEqual(snapshot_projections(self.src, 99, out), 0)
        self.assertFalse(os.path.exists(out))
        self.assertFalse(os.path.exists(out + ".tmp"))


# --- load_gw_projections -----------------------------------------------------


class LoadGwProjectionsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "snap.csv")
        with open(self.path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "web_name", "pos", "xpts",
                                              "xmins"])
            w.writeheader()
            for pid in (1, 5):
                w.writerow({"id": pid, "web_name": PLAYERS[pid][0],
                            "pos": PLAYERS[pid][1], "xpts": PROJ_XP[pid],
                            "xmins": 90})

    def test_by_id_and_by_name(self):
        proj = load_gw_projections(self.path)
        self.assertEqual(proj["by_id"][1]["xpts"], 3.0)
        self.assertEqual(proj["by_name"][("raya", "GKP")]["xpts"], 3.0)
        self.assertEqual(proj["by_name"][("bruno", "MID")]["xpts"], 6.0)

    def test_missing_file_is_empty(self):
        proj = load_gw_projections(os.path.join(self._tmp.name, "none.csv"))
        self.assertEqual(proj, {"by_id": {}, "by_name": {}})


# --- ReviewStore -------------------------------------------------------------


class ReviewStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "data", "review-state.json")

    def test_missing_is_none(self):
        self.assertIsNone(ReviewStore(self.path).last_reviewed_gw())

    def test_mark_round_trip(self):
        ReviewStore(self.path).mark(4, now=_dt("2026-09-01T10:00:00Z"))
        self.assertEqual(ReviewStore(self.path).last_reviewed_gw(), 4)

    def test_corrupt_is_none(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            f.write("{ not json")
        self.assertIsNone(ReviewStore(self.path).last_reviewed_gw())


# --- build_scorecard ---------------------------------------------------------


class BuildScorecardTest(unittest.TestCase):
    def setUp(self):
        self.sc = a_scorecard()

    def test_projected_xi_doubles_the_captain(self):
        # 41.0 over the ten non-captain starters + 6.0*2 for (C) Bruno = 53.0.
        self.assertAlmostEqual(self.sc["projected_xi"], 53.0)
        self.assertEqual(self.sc["matched"], (11, 11))

    def test_points_come_from_entry_history_not_the_code_sum(self):
        self.assertEqual(self.sc["points"], 51)      # entry_history wins
        self.assertEqual(self.sc["actual_xi"], 53)   # code-computed sum differs
        self.assertEqual(self.sc["points_on_bench"], 6)
        self.assertEqual(self.sc["overall_rank"], 3100000)

    def test_misses_sorted_and_capped(self):
        under, over = self.sc["misses"]["under"], self.sc["misses"]["over"]
        self.assertLessEqual(len(under), TOP_MISSES)
        self.assertLessEqual(len(over), TOP_MISSES)
        self.assertEqual(under[0]["name"], "Calvert")      # -4.0, biggest under
        self.assertAlmostEqual(under[0]["delta"], -4.0)
        self.assertEqual(over[0]["name"], "Diop")          # +7, biggest over

    def test_captain_grade_and_gain_vs_best(self):
        cap = self.sc["captain"]
        self.assertEqual((cap["name"], cap["points"]), ("Bruno", 4))
        self.assertEqual((cap["vice_name"], cap["vice_points"]),
                         ("Joao Pedro", 6))
        self.assertEqual((cap["best_name"], cap["best_points"]), ("Haaland", 13))
        self.assertEqual(cap["gain_vs_best"], -9)          # (4-13)*(2-1): armband swap

    def test_plan_captain_flags_the_app_override(self):
        self.assertEqual(self.sc["plan_captain"], "Haaland")

    def test_transfers_net_of_no_hit(self):
        [t] = self.sc["transfers"]
        self.assertEqual((t["out"], t["in"]), ("Yates", "Slater"))
        self.assertEqual((t["out_points"], t["in_points"], t["net"]), (2, 8, 6))
        self.assertEqual(self.sc["transfers_net"], 6)      # 6 - 0 hit

    def test_transfers_net_subtracts_the_hit(self):
        sc = a_scorecard(decision=decision(hits=4))
        self.assertEqual(sc["hits"], 4)
        self.assertEqual(sc["transfers_net"], 2)           # 6 - 4

    def test_bench_calls_name_the_lowest_beaten_starter(self):
        calls = {(c["bench"], c["starter"]) for c in self.sc["bench_calls"]}
        self.assertIn(("Diop", "Shaw"), calls)     # DEF 9 > Shaw 1 (lowest DEF)
        self.assertIn(("Wissa", "Calvert"), calls)  # FWD 2 > Calvert 0
        self.assertNotIn("Hughes", {c["bench"] for c in self.sc["bench_calls"]})

    def test_no_projections_adds_a_gap(self):
        sc = a_scorecard(projections={"by_id": {}, "by_name": {}})
        self.assertIn("no projections snapshot for GW3", sc["gaps"])
        self.assertEqual(sc["projected_xi"], 0)
        self.assertEqual(sc["matched"], (0, 11))

    def test_no_decision_adds_a_gap(self):
        sc = a_scorecard(decision=None)
        self.assertIn("no daemon decision recorded for GW3 (ad-hoc gameweek)",
                      sc["gaps"])
        self.assertIsNone(sc["decision_status"])
        self.assertEqual(sc["transfers"], [])

    def test_synthetic_id_name_join_fallback_with_state_gap(self):
        # Squad ids are synthetic (season-state before pull-squad): id 905 is not
        # in the bootstrap, so the row resolves by (normalized name, pos) instead.
        players = {5: {"web_name": "B.Fernandes", "pos": "MID", "team": "MUN"}}
        live = {5: {"minutes": 90, "total_points": 9}}
        proj = {"by_id": {5: {"xpts": 6.0}}, "by_name": {}}
        picks = {"picks": [{"id": 905, "name": "Bruno Fernandes", "pos": "MID",
                            "position": 5, "multiplier": 2, "is_captain": True,
                            "is_vice_captain": False}]}
        sc = build_scorecard(3, live, picks, players, proj, None,
                             picks_source="state")
        row = sc["rows"][0]
        self.assertEqual(row["name"], "B.Fernandes")       # joined to the real name
        self.assertEqual(row["actual"], 9)                 # live points found
        self.assertIn("picks from season state (no entry id) — autosubs not applied",
                      sc["gaps"])
        self.assertFalse(any("could not resolve" in g for g in sc["gaps"]))

    def test_unresolved_pick_gets_a_gap_and_none_actual(self):
        picks = {"picks": [{"id": 777, "name": "Ghost", "pos": "MID",
                            "position": 1, "multiplier": 1}]}
        sc = build_scorecard(3, {}, picks, {}, {"by_id": {}, "by_name": {}},
                             None, picks_source="state")
        self.assertIsNone(sc["rows"][0]["actual"])
        self.assertTrue(any("could not resolve squad pick 'Ghost'" in g
                            for g in sc["gaps"]))

    def test_rows_cover_all_fifteen_sorted_by_abs_delta(self):
        self.assertEqual(len(self.sc["rows"]), 15)
        deltas = [abs(r["delta"]) for r in self.sc["rows"] if r["delta"] is not None]
        self.assertEqual(deltas, sorted(deltas, reverse=True))


class AfterTheWhistleTest(unittest.TestCase):
    """What FPL applied after the whistle is re-derived in code, not trusted
    from the payload's multipliers: autosubs, the armband passing to the vice,
    chips — and a plan that was never applied is labelled as such."""

    def test_autosub_moves_the_bench_player_into_the_effective_xi(self):
        live = live_index()
        live[11] = {"minutes": 0, "total_points": 0}     # Calvert did not play
        picks = entry_picks()
        picks["automatic_subs"] = [{"element_in": 15, "element_out": 11}]
        sc = build_scorecard(3, live, picks, players_index(),
                             projections_by_id(), decision())
        self.assertEqual(sc["autosubs"], [{"in": "Wissa", "in_points": 2,
                                           "out": "Calvert", "out_points": 0}])
        by = {r["name"]: r for r in sc["rows"]}
        self.assertTrue(by["Wissa"]["starter"] and by["Wissa"]["multiplier"] == 1)
        self.assertFalse(by["Calvert"]["starter"])
        # Wissa's 2 counted; he is not a "bench call" and Calvert is the bench 0.
        self.assertNotIn("Wissa", {c["bench"] for c in sc["bench_calls"]})
        # The planned XI (11 as entered) is still the projection frame.
        self.assertEqual(sc["matched"], (11, 11))
        self.assertIn("Autosubs (applied by FPL)", render_scorecard(sc))

    def test_armband_passes_to_the_vice_when_the_captain_does_not_play(self):
        live = live_index()
        live[5] = {"minutes": 0, "total_points": 0}      # Bruno (C) did not play
        picks = entry_picks()
        picks["automatic_subs"] = [{"element_in": 14, "element_out": 5}]
        sc = build_scorecard(3, live, picks, players_index(),
                             projections_by_id(), decision())
        cap = sc["captain"]
        self.assertEqual((cap["name"], cap["points"]), ("Joao Pedro", 6))
        self.assertTrue(cap["armband_passed"])
        self.assertEqual(cap["planned_name"], "Bruno")
        self.assertEqual(cap["gain_vs_best"], -7)         # 6 - 13, ×1
        by = {r["name"]: r for r in sc["rows"]}
        self.assertEqual(by["Joao Pedro"]["multiplier"], 2)
        self.assertIn("(C→VC) Joao Pedro 6", review_headline(sc))
        self.assertIn("armband passed", render_scorecard(sc))

    def test_triple_captain_scales_the_gain_and_projection(self):
        picks = entry_picks()
        picks["active_chip"] = "3xc"
        sc = build_scorecard(3, live_index(), picks, players_index(),
                             projections_by_id(), decision())
        self.assertEqual(sc["captain"]["gain_vs_best"], -18)   # (4-13)*(3-1)
        self.assertEqual(sc["projected_xi"], 53.0 + 6.0)        # Bruno ×3
        self.assertIn("chip 3xc", render_scorecard(sc))

    def test_bench_boost_counts_all_fifteen(self):
        picks = entry_picks()
        picks["active_chip"] = "bboost"
        sc = build_scorecard(3, live_index(), picks, players_index(),
                             projections_by_id(), decision())
        self.assertEqual(sc["matched"], (15, 15))
        self.assertEqual(sc["bench_calls"], [])
        self.assertEqual(sc["actual_xi"], 53 + 3 + 9 + 1 + 2)

    def test_no_write_plan_transfers_are_labelled_not_applied(self):
        d = decision()
        d["status"] = "no_write"
        sc = build_scorecard(3, live_index(), entry_picks(), players_index(),
                             projections_by_id(), d)
        self.assertFalse(sc["transfers_applied"])
        self.assertEqual(sc["transfers"][0]["net"], 6)       # still computed
        self.assertIn("NOT applied", render_scorecard(sc))
        self.assertIn("(not applied)", review_headline(sc))

    def test_ambiguous_or_unknown_transfer_name_is_a_gap_not_a_guess(self):
        players = players_index()
        players[30] = {"web_name": "B.Silva", "pos": "MID", "team": "MCI"}
        players[31] = {"web_name": "F.Silva", "pos": "FWD", "team": "WOL"}
        live = live_index()
        live[30], live[31] = {"minutes": 90, "total_points": 12}, {"minutes": 90, "total_points": 1}
        d = decision()
        d["plan"]["transfers_in"] = ["Silva", "Ghost"]
        d["plan"]["transfers_out"] = ["Yates", "Hughes"]
        sc = build_scorecard(3, live, entry_picks(), players, projections_by_id(), d)
        self.assertIsNone(sc["transfers"][0]["in_points"])
        self.assertIsNone(sc["transfers"][0]["net"])
        self.assertIsNone(sc["transfers_net"])                # not all resolved
        self.assertIn("transfer name 'Silva' ambiguous — not graded", sc["gaps"])
        self.assertIn("transfer name 'Ghost' unknown — not graded", sc["gaps"])
        # An exact web_name still resolves through the ambiguity.
        d["plan"]["transfers_in"] = ["B.Silva"]
        d["plan"]["transfers_out"] = ["Yates"]
        sc = build_scorecard(3, live, entry_picks(), players, projections_by_id(), d)
        self.assertEqual(sc["transfers"][0]["in_points"], 12)

    def test_app_transfers_without_a_plan_are_a_gap(self):
        sc = build_scorecard(3, live_index(), entry_picks(), players_index(),
                             projections_by_id(), None)
        self.assertIn("1 transfer(s) made in the app but no plan recorded — "
                      "not graded", sc["gaps"])


class NextReviewGwTest(unittest.TestCase):
    def test_no_history_starts_at_the_latest_settled_gw(self):
        self.assertEqual(next_review_gw(3, None), 3)

    def test_reviews_missed_gameweeks_in_order(self):
        self.assertEqual(next_review_gw(4, 2), 3)         # slept through 3 and 4
        self.assertEqual(next_review_gw(4, 3), 4)

    def test_nothing_owed(self):
        self.assertIsNone(next_review_gw(None, None))
        self.assertIsNone(next_review_gw(3, 3))
        self.assertIsNone(next_review_gw(3, 5))


class DecisionLogExcerptTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="gaffer-reports-")
        os.makedirs(os.path.join(self.d, "gw03"))
        self.path = os.path.join(self.d, "gw03", "decision-log.md")

    def test_missing_log_is_empty(self):
        self.assertEqual(decision_log_excerpt(self.d, 4), "")

    def test_fences_are_stripped_and_the_tail_is_bounded(self):
        with open(self.path, "w") as f:
            f.write("## Deadline brief\n\nWHY: Saka home run.\n\n```plan\n"
                    "{\"captain\": \"Haaland\"}\n```\n\n" + "AM dissent line\n" * 400)
        text = decision_log_excerpt(self.d, 3, max_chars=200)
        self.assertNotIn("```", text)
        self.assertNotIn('"captain"', text)
        self.assertLessEqual(len(text), 201)                # "…" + a whole-line tail
        self.assertTrue(text.startswith("…AM dissent line"))


# --- render_scorecard --------------------------------------------------------


class RenderScorecardTest(unittest.TestCase):
    def test_never_contains_json_or_a_learnings_key(self):
        text = render_scorecard(a_scorecard())
        self.assertNotIn("{", text)
        self.assertNotIn('"lesson"', text)

    def test_headline_and_sections_present(self):
        text = render_scorecard(a_scorecard())
        self.assertIn("GW3 scorecard", text)
        self.assertIn("Biggest misses", text)
        self.assertIn(f"Calvert (FWD) proj 4.0 → actual 0 ({MINUS}4.0)", text)
        self.assertIn(f"best in XI: Haaland 13 ({MINUS}9 vs best)", text)

    def test_gaps_section_is_spelled_out(self):
        text = render_scorecard(a_scorecard(decision=None))
        self.assertIn("## Gaps", text)
        self.assertIn("no daemon decision recorded for GW3 (ad-hoc gameweek)", text)


# --- review_headline ---------------------------------------------------------


class ReviewHeadlineTest(unittest.TestCase):
    def test_three_lines_when_transfers_present(self):
        lines = review_headline(a_scorecard()).splitlines()
        self.assertEqual(lines[0],
                         "GW3 review — 51 pts (proj 53.0) · bench 6 · rank 3.1M")
        self.assertEqual(lines[1],
                         f"(C) Bruno 4 — best in XI: Haaland 13 ({MINUS}9 vs best)")
        self.assertEqual(lines[2], "Yates→Slater: +6 net")

    def test_transfer_line_dropped_when_no_transfers(self):
        sc = a_scorecard(decision={"plan": {"transfers_out": [],
                         "transfers_in": [], "hits": 0, "captain": "Bruno",
                         "vice": "Joao Pedro", "chip": None,
                         "starting_xi": [], "contingencies": []},
                         "status": "locked", "recorded_at": "x"})
        self.assertEqual(len(review_headline(sc).splitlines()), 2)

    def test_points_none_renders_na(self):
        sc = a_scorecard()
        sc["points"] = None
        self.assertIn("— n/a pts", review_headline(sc))

    def test_no_entry_history_renders_rank_na(self):
        sc = a_scorecard(picks=entry_picks(entry_history=False))
        self.assertIn("rank n/a", review_headline(sc))

    def test_no_matched_projection_renders_proj_na_not_zero(self):
        # An ad-hoc GW with no snapshot must not read as "proj 0.0" — that would
        # grade a 51-pt week as a +51 beat of the model.
        sc = a_scorecard(projections={"by_id": {}, "by_name": {}})
        self.assertIn("(proj n/a)", review_headline(sc))
        self.assertIn("(proj n/a, 0/11 matched)", render_scorecard(sc))

    def test_rank_formats(self):
        from daemon.review import _fmt_rank
        self.assertEqual(_fmt_rank(3100000), "3.1M")
        self.assertEqual(_fmt_rank(412000), "412k")
        self.assertEqual(_fmt_rank(812), "812")
        self.assertEqual(_fmt_rank(None), "n/a")


# --- run_review harness ------------------------------------------------------


class _Recorder:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send_message(self, chat_id, text):
        if self.fail:
            raise RuntimeError("sendMessage failed")
        self.sent.append({"chat_id": chat_id, "text": text})


class _Assembler:
    def __init__(self):
        self.seen = []

    def build_messages(self, user_text):
        self.seen.append(user_text)
        return [{"role": "system", "content": "SYS"},
                {"role": "user", "content": user_text}]


EVENTS_GW3 = [{"id": 1, "finished": True, "data_checked": True},
              {"id": 2, "finished": True, "data_checked": True},
              {"id": 3, "finished": True, "data_checked": True}]

REPLY = ("Honest review: the (C) Bruno call was luck-negative vs Haaland.\n\n"
         "```learnings\n" + json.dumps({"specific": [
             {"lesson": "REVIEW-LESSON captaining a form pick over the premium "
                        "ceiling cost 18 pts on a fixture-led read.",
              "evidence": "GW3 review, decision log 2026-09-01."}]}) + "\n```")


class RunReviewHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = self._tmp.name
        self.state_path = os.path.join(d, "season-state.json")
        self.reports_dir = os.path.join(d, "reports")
        self.snapshot_dir = os.path.join(d, "data")
        self.diary = os.path.join(d, "memory", "learnings.md")
        self.store = ReviewStore(os.path.join(d, "data", "review-state.json"))
        self.log = io.StringIO()
        self.logger = StructuredLogger(stream=self.log)
        self.assembler = _Assembler()
        # season state with a recorded GW3 decision
        with open(self.state_path, "w") as f:
            json.dump({"season": "2026-27", "current_gw": 3,
                       "captain": 5, "vice": 10,
                       "squad": {"picks": []},
                       "decisions": {"gw03": decision()}}, f)
        # the projection snapshot the brief wake would have stored at act time
        os.makedirs(self.snapshot_dir, exist_ok=True)
        with open(snapshot_path(self.snapshot_dir, 3), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "web_name", "pos", "xpts",
                                              "xmins"])
            w.writeheader()
            for pid, xp in PROJ_XP.items():
                w.writerow({"id": pid, "web_name": PLAYERS[pid][0],
                            "pos": PLAYERS[pid][1], "xpts": xp, "xmins": 90})

    def actuals_ok(self, gw):
        return {"live": live_index(), "picks": entry_picks(),
                "players": players_index()}

    def _run(self, events=EVENTS_GW3, fetch_actuals=None, replies=(REPLY,),
            telegram=None, learnings="diary", events_fn=None):
        telegram = _Recorder() if telegram is None else telegram
        pending = list(replies)
        self.llm_calls = []

        def llm_complete(messages):
            self.llm_calls.append(messages)
            r = pending.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        lrn = None
        if learnings == "diary":
            lrn = LearningsLog(self.diary)
        rc = run_review(
            fetch_events=(events_fn or (lambda: events)),
            fetch_actuals=fetch_actuals or self.actuals_ok,
            llm_complete=llm_complete, assembler_factory=lambda: self.assembler,
            store=self.store, telegram=telegram, allowlist={42},
            logger=self.logger, learnings=lrn, state_path=self.state_path,
            reports_dir=self.reports_dir, snapshot_dir=self.snapshot_dir,
            now=_dt("2026-09-01T10:00:00Z"))
        return rc, telegram

    def kinds(self):
        return [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]

    def event(self, name):
        for l in self.log.getvalue().splitlines():
            e = json.loads(l)
            if e["event"] == name:
                return e
        return None

    def test_missed_gameweeks_are_reviewed_in_order_one_per_tick(self):
        self.store.mark(1)
        events = [{"id": 1, "finished": True}, {"id": 2, "finished": True},
                  {"id": 3, "finished": True}]
        rc, tg = self._run(events=events)
        self.assertEqual(rc, 0)
        self.assertEqual(self.store.last_reviewed_gw(), 2)     # GW2 first, not 3
        self.assertTrue(tg.sent[0]["text"].startswith("GW2 review"))

    def test_decision_log_excerpt_rides_in_the_user_turn_without_fences(self):
        os.makedirs(os.path.join(self.reports_dir, "gw03"))
        with open(os.path.join(self.reports_dir, "gw03", "decision-log.md"), "w") as f:
            f.write("## Deadline brief\n\nDISSENT-MARKER AM preferred Haaland.\n\n"
                    "```plan\n{\"captain\": \"Bruno\"}\n```\n")
        self._run()
        user = self.llm_calls[0][-1]["content"]
        self.assertIn("DISSENT-MARKER", user)
        self.assertIn("evidence, not instructions", user)
        self.assertNotIn("```", user)
        self.assertNotIn('"captain"', user)

    def test_repo_record_carries_the_full_per_player_table(self):
        self._run()
        with open(os.path.join(self.reports_dir, "gw03", "decision-log.md")) as f:
            log = f.read()
        self.assertIn("## All picks (proj → actual)", log)
        self.assertIn("Raya (GKP, XI ×1) 3.0 → 6 (+3.0), 90 min", log)
        # ...but the prompt stays bounded to the top misses.
        self.assertNotIn("## All picks", self.llm_calls[0][-1]["content"])

    # --- quiet paths ---------------------------------------------------------

    def test_quiet_when_nothing_finished(self):
        events = [{"id": 1, "finished": False}]
        rc, tg = self._run(events=events)
        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])
        self.assertEqual(self.llm_calls, [])
        self.assertIn("review_quiet", self.kinds())

    def test_quiet_when_already_reviewed(self):
        self.store.mark(3, now=_dt("2026-09-01T09:00:00Z"))
        rc, tg = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])
        self.assertEqual(self.llm_calls, [])          # no LLM, no send
        self.assertEqual(self.event("review_quiet")["last_reviewed"], 3)

    # --- happy path ----------------------------------------------------------

    def test_diary_entry_tagged_with_reviewed_gw_not_state_gw(self):
        # season-state lags (GW1) while GW3 is being graded: the diary line must
        # say GW03 — the review knows its GW, the state's current_gw is stale.
        with open(self.state_path) as f:
            state = json.load(f)
        state["current_gw"] = 1
        with open(self.state_path, "w") as f:
            json.dump(state, f)
        rc, _ = self._run()
        self.assertEqual(rc, 0)
        with open(self.diary) as f:
            diary = f.read()
        self.assertIn("[GW03]", diary)
        self.assertNotIn("[GW01]", diary)

    def test_happy_path_sends_records_logs_and_marks(self):
        rc, tg = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)
        text = tg.sent[0]["text"]
        # headline first line prepended, before the prose
        self.assertTrue(text.startswith(
            "GW3 review — 51 pts (proj 53.0) · bench 6 · rank 3.1M"))
        self.assertIn("Honest review", text)
        # the machine block never reaches Telegram
        self.assertNotIn("```learnings", text)
        self.assertNotIn("REVIEW-LESSON", text)
        # learnings appended to the temp diary
        with open(self.diary) as f:
            diary = f.read()
        self.assertIn("REVIEW-LESSON", diary)
        # decision log carries the title and the FULL reply
        log = os.path.join(self.reports_dir, "gw03", "decision-log.md")
        with open(log) as f:
            body = f.read()
        self.assertIn("Post-GW review", body)
        self.assertIn("Honest review", body)
        self.assertIn("REVIEW-LESSON", body)           # full reply logged
        # store marked, review_sent journalled
        self.assertEqual(ReviewStore(self.store.path).last_reviewed_gw(), 3)
        sent = self.event("review_sent")
        self.assertEqual((sent["gw"], sent["points"]), (3, 51))
        self.assertEqual(sent["projected_xi"], 53.0)

    def test_user_text_routes_to_the_review_playbook(self):
        self._run()
        self.assertTrue(self.assembler.seen[0].startswith(
            "post-GW review for GW3"))

    def test_stray_plan_block_is_stripped_from_telegram(self):
        reply = ("Quick review, no lesson.\n\n```plan\n"
                 + json.dumps({"captain": "Haaland"}) + "\n```")
        rc, tg = self._run(replies=(reply,), learnings=None)
        self.assertEqual(rc, 0)
        self.assertNotIn("```", tg.sent[0]["text"])
        self.assertNotIn("plan", tg.sent[0]["text"].split("\n\n", 1)[1])

    # --- failure paths -------------------------------------------------------

    def test_send_failure_returns_1_and_does_not_mark(self):
        rc, tg = self._run(telegram=_Recorder(fail=True))
        self.assertEqual(rc, 1)
        self.assertIsNone(ReviewStore(self.store.path).last_reviewed_gw())
        self.assertIn("review_send_error", self.kinds())

    def test_llm_error_returns_1_and_does_not_mark(self):
        rc, tg = self._run(replies=(RuntimeError("llm down"),))
        self.assertEqual(rc, 1)
        self.assertEqual(tg.sent, [])
        self.assertIsNone(ReviewStore(self.store.path).last_reviewed_gw())
        self.assertEqual(self.event("review_error")["stage"], "llm")

    def test_fetch_actuals_error_returns_1(self):
        def boom(gw):
            raise RuntimeError("live fetch failed")
        rc, tg = self._run(fetch_actuals=boom)
        self.assertEqual(rc, 1)
        self.assertEqual(self.llm_calls, [])
        self.assertIsNone(ReviewStore(self.store.path).last_reviewed_gw())
        self.assertEqual(self.event("review_error")["stage"], "actuals")

    def test_fetch_events_error_returns_1(self):
        def boom():
            raise RuntimeError("bootstrap failed")
        rc, tg = self._run(events_fn=boom)
        self.assertEqual(rc, 1)
        self.assertEqual(self.event("review_error")["stage"], "events")

    def test_decision_log_failure_does_not_block_send_or_mark(self):
        # reports_dir is a FILE, so append_decision_log's makedirs raises — the
        # send already happened and the mark must still land.
        open(self.reports_dir, "w").close()
        rc, tg = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)
        self.assertEqual(ReviewStore(self.store.path).last_reviewed_gw(), 3)
        self.assertIn("decision_log_error", self.kinds())

    def test_state_fallback_when_no_entry_picks(self):
        # No entry id -> actuals["picks"] is None -> convert season-state squad.
        with open(self.state_path, "w") as f:
            json.dump({"season": "2026-27", "current_gw": 3, "captain": 5,
                       "vice": 10, "squad": {"picks": [
                           {"id": 5, "name": "Bruno", "pos": "MID",
                            "starting": True, "bench_order": None},
                           {"id": 9, "name": "Haaland", "pos": "FWD",
                            "starting": True, "bench_order": None},
                           {"id": 12, "name": "PalmerG", "pos": "GKP",
                            "starting": False, "bench_order": 0}]}}, f)

        def actuals_no_picks(gw):
            return {"live": live_index(), "picks": None,
                    "players": players_index()}
        rc, tg = self._run(fetch_actuals=actuals_no_picks)
        self.assertEqual(rc, 0)
        with open(os.path.join(self.reports_dir, "gw03", "decision-log.md")) as f:
            body = f.read()
        self.assertIn("picks from season state", body)


if __name__ == "__main__":
    unittest.main()
