"""Prompt-assembly unit tests (#16).

Covers the distiller (season-state + projections -> prose facts, never raw JSON),
the name-join that bridges synthetic squad ids to real projection rows, and the
Assembler's index-then-fetch layout with a hard token cap.
"""

import json
import os
import tempfile
import unittest

from daemon.prompt import (
    Assembler,
    estimate_tokens,
    load_projections,
    normalize_name,
    season_snapshot,
    select_playbook,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(HERE, "season-state.json")
PROJ = os.path.join(HERE, "fixtures", "projections-sample.csv")
AGENT = os.path.join(HERE, "agent")


def _state():
    with open(STATE) as f:
        return json.load(f)


class NormalizeNameTest(unittest.TestCase):
    def test_bridges_dotted_and_spaced_variants(self):
        self.assertEqual(normalize_name("Bruno Fernandes"), normalize_name("B.Fernandes"))
        self.assertEqual(normalize_name("Joao Pedro"), normalize_name("J.Pedro"))
        self.assertEqual(normalize_name("van Ewijk"), normalize_name("Van Ewijk"))


class LoadProjectionsTest(unittest.TestCase):
    def test_filters_to_the_current_gameweek(self):
        proj = load_projections(PROJ, gw=1)
        # keyed by (name, pos) so same-surname players in different positions don't collide
        self.assertEqual(proj[(normalize_name("Raya"), "GKP")]["xpts"], 5.1)  # gw1, not gw2's 4.8

    def test_missing_file_yields_empty_join(self):
        self.assertEqual(load_projections(None, gw=1), {})
        self.assertEqual(load_projections("/no/such.csv", gw=1), {})

    def _tmp_csv(self, body):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write("id,web_name,pos,team,gw,now_cost,xmins,xpts,horizon_xpts\n" + body)
        return path

    def test_skips_malformed_rows_without_crashing(self):
        # a blank gw and a short/garbage row must not abort the whole load
        path = self._tmp_csv(
            "1,Raya,GKP,1,1,6.0,90,5.1,23\n"
            "2,Broken,GKP,1,,6.0,90,4.0,20\n"          # blank gw
            "not,enough,cols\n")                        # short row
        proj = load_projections(path, gw=1)
        self.assertIn((normalize_name("Raya"), "GKP"), proj)
        self.assertNotIn((normalize_name("Broken"), "GKP"), proj)

    def test_empty_name_key_is_never_indexed(self):
        path = self._tmp_csv("9,Bruno G.,MID,1,1,5.0,90,4.0,20\n")  # normalizes to ""
        proj = load_projections(path, gw=1)
        self.assertNotIn(("", "MID"), proj)


class SeasonSnapshotTest(unittest.TestCase):
    def test_lists_squad_players_with_projected_points(self):
        snap = season_snapshot(_state(), load_projections(PROJ, gw=1))
        self.assertIn("Haaland", snap)
        self.assertIn("7.9", snap)          # Haaland's GW1 projection joined in
        self.assertIn("Bruno Fernandes", snap)

    def test_reports_bank_free_transfers_and_captain(self):
        snap = season_snapshot(_state(), load_projections(PROJ, gw=1))
        self.assertIn("Haaland", snap)      # captain id 13 resolved to a name
        self.assertRegex(snap, r"[Ff]ree transfer")
        self.assertRegex(snap, r"[Bb]ank")

    def test_never_emits_raw_state_json(self):
        state = _state()
        snap = season_snapshot(state, load_projections(PROJ, gw=1))
        for marker in ('"picks"', "bought_for", "bench_order", '"starting"'):
            self.assertNotIn(marker, snap)
        self.assertNotIn(json.dumps(state["squad"]), snap)

    def test_marks_unmatched_players_without_crashing(self):
        snap = season_snapshot(_state(), {})   # no projections available
        self.assertIn("Haaland", snap)         # squad facts still render from state

    def test_join_is_position_scoped_so_same_surname_does_not_cross_wires(self):
        # Squad's bench Palmer is a GKP; a Cole-Palmer-style MID must not leak in.
        proj = {(normalize_name("Palmer"), "GKP"): {"xpts": 0.4, "horizon_xpts": 2.0, "xmins": 5},
                (normalize_name("Palmer"), "MID"): {"xpts": 6.6, "horizon_xpts": 30.0, "xmins": 90}}
        snap = season_snapshot(_state(), proj)
        self.assertRegex(snap, r"Palmer .*GKP.* 0\.4 pts")
        self.assertNotIn("6.6 pts", snap)

    def test_tolerates_missing_money_fields(self):
        state = _state()
        state["bank"] = None
        state["squad"]["value"] = None
        snap = season_snapshot(state, {})      # must not raise on None scalars
        self.assertIn("Haaland", snap)

    def test_states_the_concrete_season_and_gameweek_as_a_time_anchor(self):
        # The model has no innate sense of "when": left abstract ("current season")
        # it backfills its training-era season (e.g. 2024/25) and rejects the live
        # squad as corrupt. The snapshot must state the CONCRETE season + gameweek
        # from state so any model, whatever its training cutoff, anchors on ground
        # truth rather than its own memory of the calendar. (#data-trust / time-anchor)
        snap = season_snapshot(_state(), {})       # state season is "2026-27", gw 1
        self.assertIn("2026/27", snap)             # concrete season, never just "current"
        low = snap.lower()
        self.assertRegex(low, r"gameweek 1\b|gw\s?1\b")
        self.assertRegex(low, r"trained before|training data|predates")  # names the cutoff gap

    def test_grounds_squad_as_live_fpl_truth_over_stale_model_knowledge(self):
        # The model's training predates this season, so it flags real transfers /
        # promotions (Mbeumo->MUN, Joao Pedro->CHE, a promoted club) as "corrupt"
        # data. The snapshot must assert the FPL API is the source of truth and
        # forbid overriding it from prior-season memory. (#projections/#data-trust)
        snap = season_snapshot(_state(), {})
        low = snap.lower()
        self.assertIn("ground truth", low)
        self.assertIn("fpl api", low)
        self.assertRegex(low, r"do not|never|don't")   # an explicit don't-flag directive
        self.assertRegex(low, r"transfer|promot|current season|training")


def _tmp_workspace():
    root = tempfile.mkdtemp(prefix="gaffer-ws-")
    os.makedirs(os.path.join(root, "roles"))
    os.makedirs(os.path.join(root, "playbooks"))
    os.makedirs(os.path.join(root, "memory"))
    os.makedirs(os.path.join(root, "reports", "gw01"))
    with open(os.path.join(root, "GAFFER.md"), "w") as f:
        f.write("# GAFFER\nPERSONA-MARKER: I am the gaffer.\n")
    with open(os.path.join(root, "memory", "MEMORY.md"), "w") as f:
        f.write("# Memory\n- MEMORY-ENTRY: GW1 is an initial build.\n")
    with open(os.path.join(root, "playbooks", "squad-review.md"), "w") as f:
        f.write("# Squad review\nSQUAD-PLAYBOOK: summarise grounded in the snapshot.\n")
    with open(os.path.join(root, "reports", "gw01", "scout-log.md"), "w") as f:
        f.write("scout stuff\n")
    return root


class SelectPlaybookTest(unittest.TestCase):
    def test_team_question_routes_to_squad_review(self):
        self.assertEqual(select_playbook("how's my team looking?"), "squad-review")

    def test_unknown_question_defaults_to_squad_review(self):
        self.assertEqual(select_playbook("random chatter"), "squad-review")

    def test_draft_and_final_deadline_texts_route_distinctly(self):
        # The #18 brief wake drives both playbooks via its synthetic user text.
        self.assertEqual(select_playbook("produce the GW2 draft deadline brief"),
                         "deadline-brief")
        self.assertEqual(select_playbook("final pre-deadline check for GW2"),
                         "deadline-final")


class AssemblerTest(unittest.TestCase):
    def _assembler(self, cap=None):
        root = _tmp_workspace()
        kw = {"projections_path": PROJ, "gw": 1}
        if cap is not None:
            kw["cap_tokens"] = cap
        return Assembler(root, STATE, **kw)

    def test_prompt_carries_persona_snapshot_memory_and_report_index(self):
        prompt = self._assembler().assemble_system_prompt("how's my team looking?")
        self.assertIn("PERSONA-MARKER", prompt)
        self.assertIn("MEMORY-ENTRY", prompt)
        self.assertIn("SQUAD-PLAYBOOK", prompt)
        self.assertIn("Haaland", prompt)            # distilled squad fact
        self.assertIn("gw01", prompt)               # report index lists the gw folder

    def test_prompt_holds_no_raw_state_json(self):
        prompt = self._assembler().assemble_system_prompt("how's my team looking?")
        for marker in ('"picks"', "bought_for", "bench_order"):
            self.assertNotIn(marker, prompt)

    def test_real_workspace_prompt_is_within_the_25k_cap(self):
        prompt = self._assembler().assemble_system_prompt("how's my team looking?")
        self.assertLessEqual(estimate_tokens(prompt), 25000)

    def test_tiny_cap_is_enforced_yet_squad_facts_survive(self):
        prompt = self._assembler(cap=400).assemble_system_prompt("how's my team looking?")
        self.assertLessEqual(estimate_tokens(prompt), 400)
        self.assertIn("Haaland", prompt)            # critical facts kept when trimming

    def test_trimming_drops_index_sections_but_keeps_persona_and_facts(self):
        # Cap sized to hold the must-keep block (headline + persona + full snapshot,
        # ~450 tokens now the snapshot carries the time anchor) while still being far
        # under the oversized memory section, so trimming must drop the index, not the
        # identity or facts.
        root = _tmp_workspace()
        with open(os.path.join(root, "memory", "MEMORY.md"), "w") as f:
            f.write("MEMORY-BIG " + ("lesson " * 400))     # oversized index section
        prompt = Assembler(root, STATE, projections_path=PROJ, gw=1, cap_tokens=600) \
            .assemble_system_prompt("how's my team looking?")
        self.assertLessEqual(estimate_tokens(prompt), 600)
        self.assertIn("PERSONA-MARKER", prompt)            # identity survives trimming
        self.assertIn("Haaland", prompt)                   # facts survive trimming
        self.assertNotIn("MEMORY-BIG", prompt)             # the bloated section is dropped

    def test_build_messages_puts_snapshot_in_system_and_question_last(self):
        msgs = self._assembler().build_messages("how's my team looking?")
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[-1], {"role": "user", "content": "how's my team looking?"})
        self.assertIn("Haaland", msgs[0]["content"])


class RealWorkspaceTest(unittest.TestCase):
    """Guards the committed agent/ workspace against the assembly contract."""

    def _prompt(self):
        return Assembler(AGENT, STATE, projections_path=PROJ, gw=1) \
            .assemble_system_prompt("how's my team looking?")

    def test_committed_workspace_is_loaded_into_the_prompt(self):
        prompt = self._prompt()
        self.assertIn("gaffer", prompt.lower())     # GAFFER.md persona present
        self.assertIn("Haaland", prompt)            # distilled squad fact present

    def test_committed_workspace_prompt_is_within_the_25k_cap(self):
        self.assertLessEqual(estimate_tokens(self._prompt()), 25000)

    def test_committed_workspace_prompt_has_no_raw_state_json(self):
        prompt = self._prompt()
        for marker in ('"picks"', "bought_for", "bench_order"):
            self.assertNotIn(marker, prompt)


if __name__ == "__main__":
    unittest.main()
