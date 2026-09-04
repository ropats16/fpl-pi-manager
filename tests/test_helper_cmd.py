"""`daemon helper <role>` (#54): one role by name, on its mapped model, into
the next GW's report folder — through the HTTP-edge harness."""

import io
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.__main__ import REPO_ROOT, run_helper_cmd
from tests.fakes import FakeTransport

FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
EVENTS = [{"id": 3, "deadline_time": "2026-09-04T17:30:00Z", "finished": False},
          {"id": 4, "deadline_time": "2026-09-12T10:00:00Z", "finished": False}]
NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)      # GW3 gone -> next is 4
REPORT = "Haaland fit (FFS, 3 Sep).\n\nCoverage: FPL flags checked."


class HelperCmdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="helper-cmd-")
        self.env = {
            "GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "TT",
            "OPENROUTER_API_KEY": "KK",
            "GAFFER_REPORTS_DIR": os.path.join(self.tmp, "reports"),
            "GAFFER_PROJECTIONS_PATH": os.path.join(REPO_ROOT, "fixtures",
                                                    "projections-sample.csv"),
            # Frozen GW1 fixture: the events-failure fallback must not read the
            # tracked root state (rolled to GW3 on the Pi).
            "GAFFER_STATE_PATH": os.path.join(REPO_ROOT, "fixtures",
                                              "season-state.json"),
        }
        self.out = io.StringIO()

    def _run(self, args, transport=None, fetch_events=lambda: EVENTS):
        t = transport or FakeTransport(llm_replies=[REPORT])
        rc = run_helper_cmd(args, env=self.env, transport=t, out=self.out,
                            fetch_events=fetch_events, now=NOW)
        return rc, t

    def test_unknown_role_is_a_clear_error(self):
        rc, t = self._run(["goalkeeping-coach"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown role 'goalkeeping-coach'", self.out.getvalue())
        self.assertIn("availability", self.out.getvalue())
        self.assertEqual(t.llm_requests, [])
        rc, _ = self._run([])
        self.assertEqual(rc, 2)

    def test_runs_the_named_role_on_its_mapped_model_for_the_next_gw(self):
        rc, t = self._run(["availability"])
        self.assertEqual(rc, 0)
        path = os.path.join(self.tmp, "reports", "gw04", "availability.md")
        self.assertTrue(os.path.exists(path))
        self.assertEqual(t.llm_requests[0]["model"], "z-ai/glm-5.3-flash")
        self.assertIn("availability analyst", t.llm_requests[0]["messages"][0]["content"])
        summary = self.out.getvalue().splitlines()[-1]
        self.assertIn("helper: role=availability gw=4 status=ok", summary)
        self.assertIn("cost=$", summary)

    def test_gw_flag_overrides_and_events_fetch_is_skipped(self):
        def boom():
            raise AssertionError("must not fetch events")
        rc, _ = self._run(["availability", "--gw", "7"], fetch_events=boom)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "reports", "gw07",
                                                    "availability.md")))

    def test_events_failure_falls_back_to_season_state_gw(self):
        def boom():
            raise OSError("fpl down")
        rc, _ = self._run(["availability"], fetch_events=boom)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "reports", "gw01",
                                                    "availability.md")))
        self.assertIn("helper_events_error", self.out.getvalue())

    def test_second_run_same_gw_is_refused_without_spending(self):
        self._run(["availability"])
        rc, t = self._run(["availability"])
        self.assertEqual(rc, 0)
        self.assertEqual(t.llm_requests, [])
        self.assertIn("already written (write-once)", self.out.getvalue())

    def test_llm_failure_is_a_stub_report_and_exit_zero(self):
        class Down:
            requests = []

            def request(self, *a):
                raise OSError("openrouter down")
        rc, _ = self._run(["availability"], transport=Down())
        self.assertEqual(rc, 0)
        with open(os.path.join(self.tmp, "reports", "gw04", "availability.md")) as f:
            self.assertIn("helper failed: OSError: openrouter down, coverage: none", f.read())
        self.assertIn("status=failed", self.out.getvalue())

    def test_unknown_search_provider_is_a_config_error_at_wiring_time(self):
        self.env["GAFFER_SEARCH_PROVIDER"] = "brave"
        with self.assertRaises(ValueError) as cm:
            self._run(["availability"])
        self.assertIn("brave", str(cm.exception))

    def test_am_role_runs_on_the_third_family_model(self):
        rc, t = self._run(["am"])
        self.assertEqual(rc, 0)
        self.assertEqual(t.llm_requests[0]["model"], "qwen/qwen3.8-max")


if __name__ == "__main__":
    unittest.main()
