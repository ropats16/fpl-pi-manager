"""`daemon scout` (#57): the daily Scout wake — one flash tool loop for the next
unfinished GW, appended (newest first) to that GW's scout-log.md, URGENT
findings flagged for the brief — through the HTTP-edge harness."""

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.__main__ import REPO_ROOT, run_scout_cmd
from daemon.ledger import Ledger
from daemon.plan import ApprovalStore
from tests.fakes import FakeTransport

EVENTS = [{"id": 3, "deadline_time": "2026-09-04T17:30:00Z", "finished": False},
          {"id": 4, "deadline_time": "2026-09-12T10:00:00Z", "finished": False}]
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)      # GW3 gone -> next is 4
ENTRY = "Haaland trained fully (FFS, 5 Sep). Nothing else moved.\n\nCoverage: FPL flags, FFS."
URGENT_ENTRY = ("**URGENT**: Saka out 3 weeks (Arteta presser, 6 Sep) — voids the (VC).\n\n"
                "Coverage: presser, FPL flags.")
PLAN = {"transfers_in": ["Palmer"], "transfers_out": ["Saka"], "hits": 0,
        "starting_xi": ["Raya"], "captain": "Haaland", "vice": "Saka", "chip": None,
        "contingencies": []}


class ScoutCmdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scout-cmd-")
        self.env = {
            "GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "TT",
            "OPENROUTER_API_KEY": "KK",
            "GAFFER_REPORTS_DIR": os.path.join(self.tmp, "reports"),
            "GAFFER_DATA_DIR": os.path.join(self.tmp, "data"),
            "GAFFER_APPROVAL_STATE_PATH": os.path.join(self.tmp, "approval-state.json"),
            "GAFFER_PROJECTIONS_PATH": os.path.join(REPO_ROOT, "fixtures",
                                                    "projections-sample.csv"),
            # Frozen GW1 fixture: the events-failure fallback must not read the
            # tracked root state (rolled to GW3 on the Pi).
            "GAFFER_STATE_PATH": os.path.join(REPO_ROOT, "fixtures",
                                              "season-state.json"),
        }
        self.out = io.StringIO()

    def _run(self, args=(), transport=None, fetch_events=lambda: EVENTS, reply=ENTRY,
             now=NOW):
        t = transport or FakeTransport(llm_replies=[reply])
        rc = run_scout_cmd(list(args), env=self.env, transport=t, out=self.out,
                           fetch_events=fetch_events, now=now)
        return rc, t

    def _log(self, gw=4):
        path = os.path.join(self.tmp, "reports", f"gw{gw:02d}", "scout-log.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _events(self, kind):
        return [json.loads(l) for l in self.out.getvalue().splitlines()
                if l.startswith("{") and json.loads(l)["event"] == kind]

    def test_appends_one_dated_entry_for_the_next_gw_creating_the_folder(self):
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "reports")))
        rc, t = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(t.llm_requests[0]["model"], "z-ai/glm-5.3-flash")
        self.assertIn("scout", t.llm_requests[0]["messages"][0]["content"].lower())
        log = self._log()
        self.assertTrue(log.startswith("# Scout log — GW04"))
        self.assertIn("2026-09-05", log)
        self.assertIn("Haaland trained fully", log)
        summary = self.out.getvalue().splitlines()[-1]
        self.assertIn("scout: gw=4 status=ok", summary)
        self.assertIn("entries=1 urgent=False", summary)
        self.assertIn("cost=$", summary)

    def test_second_run_same_day_appends_again_newest_first(self):
        self._run(reply="FIRST sweep.\n\nCoverage: FPL.")
        rc, t = self._run(reply="SECOND sweep.\n\nCoverage: FPL.",
                          now=NOW.replace(hour=16))
        self.assertEqual(rc, 0)
        self.assertEqual(len(t.llm_requests), 1)          # it ran: not write-once
        log = self._log()
        self.assertEqual(log.count("# Scout log — GW04"), 1)
        self.assertLess(log.index("SECOND sweep"), log.index("FIRST sweep"))
        self.assertIn("entries=2", self.out.getvalue().splitlines()[-1])

    def test_task_carries_the_current_plan_so_the_scout_can_judge_voiding_news(self):
        store = ApprovalStore(self.env["GAFFER_APPROVAL_STATE_PATH"])
        store.reset_for(4)
        store.set_pending(4, PLAN)
        rc, t = self._run()
        task = t.llm_requests[0]["messages"][-1]["content"]
        self.assertIn("URGENT", task)
        self.assertIn("Saka→Palmer", task)
        self.assertIn("(C) Haaland", task)

    def test_a_plan_for_another_gw_is_not_offered_as_the_current_plan(self):
        store = ApprovalStore(self.env["GAFFER_APPROVAL_STATE_PATH"])
        store.reset_for(3)
        store.set_pending(3, PLAN)
        rc, t = self._run()
        task = t.llm_requests[0]["messages"][-1]["content"]
        self.assertNotIn("Saka→Palmer", task)
        self.assertIn("no plan on record", task)

    def test_urgent_finding_is_flagged_in_the_log_the_event_stream_and_the_summary(self):
        rc, t = self._run(reply=URGENT_ENTRY)
        self.assertEqual(rc, 0)
        self.assertIn("URGENT", self._log())
        urgent = self._events("scout_urgent")
        self.assertEqual(len(urgent), 1)
        self.assertEqual(urgent[0]["gw"], 4)
        self.assertIn("Saka out 3 weeks", urgent[0]["line"])
        self.assertIn("urgent=True", self.out.getvalue().splitlines()[-1])

    def test_gw_flag_overrides_and_events_fetch_is_skipped(self):
        def boom():
            raise AssertionError("must not fetch events")
        rc, _ = self._run(["--gw", "7"], fetch_events=boom)
        self.assertEqual(rc, 0)
        self.assertTrue(self._log(7).startswith("# Scout log — GW07"))

    def test_events_failure_falls_back_to_season_state_gw(self):
        def boom():
            raise OSError("fpl down")
        rc, _ = self._run(fetch_events=boom)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "reports", "gw01",
                                                    "scout-log.md")))
        self.assertIn("helper_events_error", self.out.getvalue())

    def test_bad_gw_flag_is_exit_two_without_spending(self):
        rc, t = self._run(["--gw", "soon"])
        self.assertEqual(rc, 2)
        self.assertEqual(t.llm_requests, [])

    def test_llm_failure_is_a_stub_entry_and_exit_zero(self):
        class Down:
            requests = []

            def request(self, *a):
                raise OSError("openrouter down")
        rc, _ = self._run(transport=Down())
        self.assertEqual(rc, 0)
        log = self._log()
        self.assertIn("status failed", log)
        self.assertIn("helper failed: OSError: openrouter down, coverage: none", log)
        self.assertIn("status=failed", self.out.getvalue().splitlines()[-1])

    def test_ledger_helpers_off_is_a_stub_entry_with_no_llm_call(self):
        ledger = Ledger(os.path.join(self.tmp, "data", "spend-ledger.json"))
        ledger.add(4.9, NOW, source="seed")
        rc, t = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(t.llm_requests, [])
        self.assertIn("helper skipped: month-to-date ledger: helpers off", self._log())
        self.assertIn("status=skipped", self.out.getvalue().splitlines()[-1])

    def test_ledger_search_off_runs_without_the_search_tool_and_records_spend(self):
        ledger = Ledger(os.path.join(self.tmp, "data", "spend-ledger.json"))
        ledger.add(4.2, NOW, source="seed")
        rc, t = self._run(transport=FakeTransport(
            llm_replies=[ENTRY], usage={"prompt_tokens": 2000, "completion_tokens": 300}))
        self.assertEqual(rc, 0)
        names = [x["function"]["name"] for x in t.llm_requests[0]["tools"]]
        self.assertEqual(names, ["fetch"])
        self.assertGreater(Ledger(ledger.path).total(NOW), 4.2)


if __name__ == "__main__":
    unittest.main()
