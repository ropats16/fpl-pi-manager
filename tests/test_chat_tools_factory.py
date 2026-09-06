"""`build_chat_tools_factory` (spec §2/§4 wiring): ask_helper runs the real seat
with `task=question` under reduced caps, the MTD ledger gates chat search, a
missing gameweek withholds the seat/report tools, and a real git host lights up
the ticket tools. run_helper is stubbed so no LLM/network is touched."""

import io
import os
import types
import unittest
from unittest import mock

from daemon.__main__ import ASK_HELPER_CAPS, build_chat_tools_factory
from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL, LLM
from daemon.logging_setup import StructuredLogger
from daemon.propose import FakeGitHost
from daemon.reports import ReportWriter
from tests.fakes import FakeTransport

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, "fixtures", "season-state.json")
PROJ = os.path.join(REPO, "fixtures", "projections-sample.csv")


class _Ledger:
    def __init__(self, mode="full"):
        self._mode = mode

    def mode(self, now=None):
        return self._mode


def _cfg():
    return Config(allowlist={1}, telegram_token="t", openrouter_key="k",
                  model="moonshotai/kimi-k2.5", base_url=DEFAULT_BASE_URL,
                  system_prompt="s")


class ChatFactoryHarness(unittest.TestCase):
    def setUp(self):
        self.tmp_reports = os.path.join(REPO, "fixtures")   # unused unless written
        self.recorded = []

    def _env(self, reports_dir, state=STATE):
        return {"GAFFER_STATE_PATH": state, "GAFFER_REPORTS_DIR": reports_dir,
                "GAFFER_PROJECTIONS_PATH": PROJ,
                "GAFFER_WORKSPACE_DIR": os.path.join(REPO, "agent")}

    def _stub_run_helper(self, answer="STUB ANSWER"):
        rec = self.recorded

        def fake(role, llm, model, ws, state, gw, fetcher, searcher, writer, caps,
                 logger, projections_path=None, clock=None, search=True, fetch=True,
                 task=None):
            rec.append({"role": role, "caps": caps, "search": search, "fetch": fetch,
                        "task": task, "gw": gw})
            path = writer.write(role, f"{answer} :: {task}", {})
            return types.SimpleNamespace(path=path, reason=None, status="ok")
        return fake

    def _factory(self, reports_dir, host=None, ledger=None, state=STATE):
        cfg = _cfg()
        transport = FakeTransport()
        logger = StructuredLogger(stream=io.StringIO(), secrets=[])
        llm = LLM(api_key="k", transport=transport, logger=logger)
        return build_chat_tools_factory(cfg, self._env(reports_dir, state), transport,
                                        llm, logger, host=host, ledger=ledger)


class AskHelperWiringTest(ChatFactoryHarness):
    def test_ask_helper_passes_task_and_reduced_caps_to_run_helper(self):
        import tempfile
        with tempfile.TemporaryDirectory() as reports:
            factory = self._factory(reports)
            with mock.patch("daemon.__main__.run_helper", self._stub_run_helper()):
                tools = {t.name: t for t in factory()}
                out = tools["ask_helper"].fn(role="availability", question="is Saka fit?")
            self.assertIn("STUB ANSWER", out)
            self.assertEqual(self.recorded[0]["task"], "is Saka fit?")
            self.assertEqual(self.recorded[0]["caps"], ASK_HELPER_CAPS)
            self.assertTrue(self.recorded[0]["search"])         # full ledger

    def test_search_off_ledger_drops_search_and_runs_ask_fetch_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as reports:
            factory = self._factory(reports, ledger=_Ledger("search_off"))
            with mock.patch("daemon.__main__.run_helper", self._stub_run_helper()):
                tools = {t.name: t for t in factory()}
                self.assertNotIn("search", tools)               # tool withheld
                tools["ask_helper"].fn(role="market", question="price risk?")
            self.assertFalse(self.recorded[0]["search"])        # run_helper search=False


class GwGuardTest(ChatFactoryHarness):
    def test_missing_state_withholds_seat_and_report_tools(self):
        import tempfile
        with tempfile.TemporaryDirectory() as reports:
            factory = self._factory(reports, state=os.path.join(reports, "nope.json"))
            tools = {t.name for t in factory()}
        self.assertNotIn("ask_helper", tools)
        self.assertNotIn("read_report", tools)
        self.assertIn("read_projections", tools)                # no gameweek needed


class HostWiringTest(ChatFactoryHarness):
    def test_real_host_lights_up_the_ticket_tools(self):
        import tempfile
        with tempfile.TemporaryDirectory() as reports:
            factory = self._factory(reports, host=FakeGitHost())
            tools = {t.name for t in factory()}
        self.assertTrue({"open_ticket", "ticket_status", "pr_status"} <= tools)

    def test_no_host_offers_no_ticket_tools(self):
        import tempfile
        with tempfile.TemporaryDirectory() as reports:
            factory = self._factory(reports, host=None)
            tools = {t.name for t in factory()}
        self.assertFalse({"open_ticket", "ticket_status", "pr_status"} & tools)


if __name__ == "__main__":
    unittest.main()
