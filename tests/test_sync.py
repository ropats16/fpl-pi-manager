"""Season-state auto-sync: the daemon rolls season-state.json to the next
gameweek on its own (the review wake once a GW settles, the draft wake as a
guard) — the GW2→GW3 gap that left the gaffer drafting from the GW1 squad."""

import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.__main__ import REPO_ROOT, run_sync_cmd
from daemon.logging_setup import StructuredLogger
from daemon.sync import SeasonSync, free_transfers_entering
from tests.fakes import FakeTransport

BOOT = {"players": [
    {"id": 1, "web_name": "Raya", "element_type": 1, "team": 1, "now_cost": 60},
    {"id": 2, "web_name": "Gabriel", "element_type": 2, "team": 1, "now_cost": 80},
    {"id": 3, "web_name": "Shaw", "element_type": 2, "team": 2, "now_cost": 45},
    {"id": 4, "web_name": "van Ewijk", "element_type": 2, "team": 3, "now_cost": 40},
    {"id": 5, "web_name": "B.Fernandes", "element_type": 3, "team": 2, "now_cost": 120},
    {"id": 6, "web_name": "Slater", "element_type": 3, "team": 4, "now_cost": 45},
    {"id": 7, "web_name": "Mbeumo", "element_type": 3, "team": 2, "now_cost": 80},
    {"id": 8, "web_name": "Szoboszlai", "element_type": 3, "team": 5, "now_cost": 70},
    {"id": 9, "web_name": "João Pedro", "element_type": 4, "team": 6, "now_cost": 77},
    {"id": 10, "web_name": "Haaland", "element_type": 4, "team": 7, "now_cost": 155},
    {"id": 11, "web_name": "Calvert-Lewin", "element_type": 4, "team": 8, "now_cost": 60},
    {"id": 12, "web_name": "Palmer", "element_type": 1, "team": 9, "now_cost": 40},
    {"id": 13, "web_name": "Mitchell", "element_type": 2, "team": 10, "now_cost": 45},
    {"id": 14, "web_name": "Diop", "element_type": 2, "team": 9, "now_cost": 40},
    {"id": 15, "web_name": "Hughes", "element_type": 3, "team": 10, "now_cost": 45}],
    "teams": [{"id": i, "short_name": s} for i, s in enumerate(
        ("ARS", "MUN", "COV", "HUL", "LIV", "CHE", "MCI", "LEE", "IPS", "CRY"), 1)],
    "events": []}
PICKS = {"picks": [{"element": i, "position": i, "is_captain": i == 5,
                    "is_vice_captain": i == 10} for i in range(1, 16)],
         "entry_history": {"event": 2, "bank": 0, "value": 1002, "event_transfers": 1}}
HISTORY = {"current": [{"event": 1, "event_transfers": 0, "event_transfers_cost": 0},
                       {"event": 2, "event_transfers": 1, "event_transfers_cost": 0}],
           "chips": []}
NOW = datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc)


class FreeTransfersTest(unittest.TestCase):
    def _h(self, transfers, chips=()):
        cur = [{"event": i + 1, "event_transfers": t} for i, t in enumerate(transfers)]
        return {"current": cur, "chips": [{"name": n, "event": e} for n, e in chips]}

    def test_one_transfer_spent_leaves_one_entering_the_next_gw(self):
        self.assertEqual(free_transfers_entering(self._h([0, 1]), 3), 1)

    def test_rolling_accumulates_and_caps_at_five(self):
        self.assertEqual(free_transfers_entering(self._h([0, 0, 0]), 4), 3)
        self.assertEqual(free_transfers_entering(self._h([0] * 9), 10), 5)

    def test_a_hit_never_goes_below_one(self):
        self.assertEqual(free_transfers_entering(self._h([0, 3]), 3), 1)

    def test_wildcard_and_free_hit_freeze_the_count(self):
        # FPL's example: 4 saved, Free Hit played, still 4 the next GW — a chip
        # week neither spends nor adds a free transfer.
        self.assertEqual(free_transfers_entering(self._h([0, 0, 8], chips=(("wildcard", 3),)), 4), 2)
        self.assertEqual(free_transfers_entering(self._h([0, 0, 8], chips=(("freehit", 3),)), 4), 2)
        self.assertEqual(free_transfers_entering(self._h([0, 0, 0, 0, 9], chips=(("freehit", 5),)), 6), 4)

    def test_entering_gw1_or_gw2_is_one_and_missing_history_is_tolerated(self):
        self.assertEqual(free_transfers_entering(self._h([]), 1), 1)
        self.assertEqual(free_transfers_entering(self._h([]), 2), 1)
        self.assertEqual(free_transfers_entering({}, 4), 3)     # nothing recorded = rolled


class SeasonSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sync-")
        self.state_path = os.path.join(self.tmp, "season-state.json")
        shutil.copy(os.path.join(REPO_ROOT, "fixtures", "season-state.json"),
                    self.state_path)
        self.logbuf = io.StringIO()
        self.calls = []

    def _state(self):
        with open(self.state_path, encoding="utf-8") as f:
            return json.load(f)

    def _sync(self, entry_id=2928517, picks=PICKS, history=HISTORY, boot=BOOT):
        def rec(name, value):
            def f(*a):
                self.calls.append((name,) + a)
                if isinstance(value, Exception):
                    raise value
                return value
            return f
        return SeasonSync(self.state_path, entry_id, fetch_picks=rec("picks", picks),
                          fetch_history=rec("history", history),
                          fetch_bootstrap=rec("bootstrap", boot),
                          logger=StructuredLogger(stream=self.logbuf),
                          clock=lambda: NOW)

    def _events(self, kind):
        return [json.loads(l) for l in self.logbuf.getvalue().splitlines()
                if json.loads(l)["event"] == kind]

    def test_rolls_the_state_to_the_target_gw_from_the_settled_gws_picks(self):
        self.assertEqual(self._state()["current_gw"], 1)
        res = self._sync().ensure(3)
        self.assertEqual(res["status"], "synced")
        self.assertEqual((res["from_gw"], res["to_gw"], res["free_transfers"]), (1, 3, 1))
        self.assertIn(("picks", 2), self.calls)          # GW3's squad = what GW2 fielded
        st = self._state()
        self.assertEqual(st["current_gw"], 3)
        self.assertEqual(st["free_transfers"], 1)
        self.assertEqual(st["entry_id"], 2928517)
        names = [p["name"] for p in st["squad"]["picks"]]
        self.assertIn("Slater", names)
        self.assertNotIn("Yates", names)
        bench = [p["name"] for p in st["squad"]["picks"] if not p["starting"]]
        self.assertEqual(bench, ["Palmer", "Mitchell", "Diop", "Hughes"])
        self.assertEqual((st["captain"], st["vice"]), (5, 10))
        self.assertEqual(st["history"][-1]["type"], "auto-sync")
        ev = self._events("season_sync")
        self.assertEqual(ev[-1]["status"], "synced")

    def test_already_at_or_past_the_target_is_a_no_op_without_a_request(self):
        self._sync().ensure(3)
        self.calls.clear()
        res = self._sync().ensure(3)
        self.assertEqual(res["status"], "current")
        self.assertEqual(self.calls, [])
        self.assertEqual(self._sync().ensure(2)["status"], "current")

    def test_no_entry_id_is_skipped_and_logged_not_raised(self):
        res = self._sync(entry_id=None).ensure(3)
        self.assertEqual((res["status"], res["reason"]), ("skipped", "no entry id"))
        self.assertEqual(self.calls, [])
        self.assertEqual(self._state()["current_gw"], 1)

    def test_a_fetch_failure_leaves_the_file_untouched_and_reports_error(self):
        before = self._state()
        res = self._sync(picks=OSError("fpl down")).ensure(3)
        self.assertEqual(res["status"], "error")
        self.assertIn("OSError", res["reason"])
        self.assertEqual(self._state(), before)
        self.assertEqual(self._events("sync_error")[0]["target_gw"], 3)

    def test_a_missing_state_file_is_an_error_not_a_crash(self):
        os.remove(self.state_path)
        self.assertEqual(self._sync().ensure(3)["status"], "error")


EVENTS = [{"id": 3, "deadline_time": "2026-09-04T17:30:00Z", "finished": False},
          {"id": 4, "deadline_time": "2026-09-12T12:30:00Z", "finished": False}]


class SyncCmdTest(unittest.TestCase):
    """`daemon sync [--gw N]`: the operator's hand-crank of the same path."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sync-cmd-")
        self.state_path = os.path.join(self.tmp, "season-state.json")
        shutil.copy(os.path.join(REPO_ROOT, "fixtures", "season-state.json"),
                    self.state_path)
        self.env = {"GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "TT",
                    "OPENROUTER_API_KEY": "KK", "GAFFER_STATE_PATH": self.state_path,
                    "FPL_ENTRY_ID": "2928517"}
        self.out = io.StringIO()
        self.targets = []

    def _fake_sync(self, target_gw):
        self.targets.append(target_gw)
        return {"status": "synced", "from_gw": 1, "to_gw": target_gw,
                "free_transfers": 1, "squad": 15}

    def test_targets_the_next_unfinished_gw_and_prints_the_outcome(self):
        rc = run_sync_cmd([], env=self.env, transport=FakeTransport(), out=self.out,
                          fetch_events=lambda: EVENTS, now=NOW, sync=self._fake_sync)
        self.assertEqual(rc, 0)
        self.assertEqual(self.targets, [3])
        self.assertIn("sync: gw=3 status=synced from=1 free_transfers=1", self.out.getvalue())

    def test_gw_flag_overrides(self):
        rc = run_sync_cmd(["--gw", "5"], env=self.env, transport=FakeTransport(),
                          out=self.out, fetch_events=lambda: EVENTS, now=NOW,
                          sync=self._fake_sync)
        self.assertEqual(rc, 0)
        self.assertEqual(self.targets, [5])

    def test_error_status_is_exit_one(self):
        rc = run_sync_cmd([], env=self.env, transport=FakeTransport(), out=self.out,
                          fetch_events=lambda: EVENTS, now=NOW,
                          sync=lambda gw: {"status": "error", "reason": "OSError: down",
                                           "from_gw": 1, "to_gw": gw})
        self.assertEqual(rc, 1)
        self.assertIn("status=error", self.out.getvalue())


if __name__ == "__main__":
    unittest.main()
