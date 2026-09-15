"""The gaffer's chat tools (spec §2): each tool's behaviour, its per-wake cap,
and the rule that a tool whose dependency is None is not offered. Tools that
touch the network run over a real Fetcher/ExaSearch on the faked transport; the
git host is a small duck-typed fake (PR 2 adds it to GhGitHost/FakeGitHost)."""

import io
import json
import os
import shutil
import tempfile
import unittest

from daemon.gaffer_tools import build_gaffer_tools
from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.reports import ReportWriter
from daemon.tools import ExaSearch, Fetcher
from tests.fakes import FakeTransport

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPL = "https://fantasy.premierleague.com"
BOOTSTRAP = f"{FPL}/api/bootstrap-static/"
FIXTURES = f"{FPL}/api/fixtures/"
ALLOW = {"fantasy.premierleague.com"}

_BOOT = json.dumps({
    "elements": [
        {"id": 1, "web_name": "Haaland", "team": 2, "element_type": 4,
         "now_cost": 151, "status": "a", "news": "", "form": "8.2",
         "ep_next": "7.5", "selected_by_percent": "62.1",
         "expected_goal_involvements": "1.2", "total_points": 40},
        {"id": 2, "web_name": "Saka", "team": 1, "element_type": 3,
         "now_cost": 101, "status": "d", "news": "knock - 75% chance",
         "form": "5.1", "ep_next": "4.0", "selected_by_percent": "40.0",
         "expected_goal_involvements": "0.6", "total_points": 28}],
    "teams": [
        {"id": 1, "name": "Arsenal", "short_name": "ARS", "strength_attack_home": 1300,
         "strength_attack_away": 1310, "strength_defence_home": 1290,
         "strength_defence_away": 1280},
        {"id": 2, "name": "Man City", "short_name": "MCI", "strength_attack_home": 1350,
         "strength_attack_away": 1340, "strength_defence_home": 1300,
         "strength_defence_away": 1290}],
    "events": [{"id": 4, "name": "Gameweek 4", "is_next": True}]})
_FIX = json.dumps([
    {"id": 10, "event": 4, "team_h": 2, "team_a": 1, "team_h_difficulty": 2,
     "team_a_difficulty": 4, "finished": False},
    {"id": 11, "event": 5, "team_h": 1, "team_a": 2, "team_h_difficulty": 4,
     "team_a_difficulty": 2, "finished": False}])


class FakeHost:
    def __init__(self):
        self.opened = []

    def open_issue(self, title, body, labels):
        self.opened.append({"title": title, "body": body, "labels": labels})
        n = len(self.opened)
        return n, f"https://github.com/x/issues/{n}"

    def issue_status(self, n):
        return f"issue #{n}: open, title 'X', labels gaffer"

    def pr_status(self, n):
        return f"pr #{n}: open, draft=False, checks passing, mergeable"


class GafferToolsHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gaffer-tools-")
        self.reports = os.path.join(self.tmp, "reports")
        self.ws = os.path.join(REPO, "agent")
        self.state = os.path.join(REPO, "season-state.json")
        self.proj = os.path.join(REPO, "fixtures", "projections-sample.csv")
        self.logbuf = io.StringIO()
        self.gw = 4
        self.asked = []
        self.host = FakeHost()

    def _helper_runner(self, role, question):
        self.asked.append((role, question))
        return f"{role} says: canned answer to {question!r}"

    def _fetcher(self, transport):
        logger = StructuredLogger(stream=self.logbuf, secrets=[])
        return Fetcher(transport, ALLOW, logger=logger)

    def _searcher(self, transport):
        logger = StructuredLogger(stream=self.logbuf, secrets=[])
        llm = LLM(api_key="K", transport=transport, logger=logger,
                  prices={"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25}})
        return ExaSearch(llm, "z-ai/glm-5.3-flash", logger=logger)

    def _build(self, fetcher="_", searcher="_", helper_runner="_", host="_",
               transport=None):
        t = transport or FakeTransport(pages={BOOTSTRAP: _BOOT, FIXTURES: _FIX},
                                       search_reply="1. Saka fit — bbc/1")
        fetcher = self._fetcher(t) if fetcher == "_" else fetcher
        searcher = self._searcher(t) if searcher == "_" else searcher
        helper_runner = self._helper_runner if helper_runner == "_" else helper_runner
        host = self.host if host == "_" else host
        from daemon.config import Config
        from daemon.llm import DEFAULT_BASE_URL
        cfg = Config(allowlist={1}, telegram_token="t", openrouter_key="k",
                     model="moonshotai/kimi-k2.5", base_url=DEFAULT_BASE_URL,
                     system_prompt="s")
        tools = build_gaffer_tools(cfg, self.ws, self.state, self.reports, self.proj,
                                   self.gw, fetcher, searcher, helper_runner, host)
        return {tool.name: tool for tool in tools}, t

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class InventoryTest(GafferToolsHarness):
    def test_all_nine_tools_offered_with_the_spec_caps(self):
        tools, _ = self._build()
        self.assertEqual(set(tools), {"ask_helper", "read_report", "read_projections",
                                      "fpl_lookup", "search", "fetch", "open_ticket",
                                      "ticket_status", "pr_status"})
        caps = {n: t.cap for n, t in tools.items()}
        self.assertEqual(caps, {"ask_helper": 6, "read_report": 6, "read_projections": 6,
                                "fpl_lookup": 6, "search": 3, "fetch": 5,
                                "open_ticket": 1, "ticket_status": 4, "pr_status": 4})

    def test_missing_dependencies_drop_their_tools(self):
        tools, _ = self._build(host=None, searcher=None, fetcher=None,
                               helper_runner=None)
        # host None -> no ticket tools; searcher None -> no search; fetcher None ->
        # no fetch and no fpl_lookup; helper_runner None -> no ask_helper.
        self.assertEqual(set(tools), {"read_report", "read_projections"})


class AskHelperTest(GafferToolsHarness):
    def test_runs_the_role_and_appends_a_qa_section_to_its_report(self):
        tools, _ = self._build()
        out = tools["ask_helper"].fn(role="availability", question="is Saka fit?")
        self.assertIn("canned answer", out)
        self.assertEqual(self.asked, [("availability", "is Saka fit?")])
        path = os.path.join(self.reports, "gw04", "availability.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("— availability (asked)", text)
        self.assertIn("canned answer to 'is Saka fit?'", text)

    def test_append_keeps_an_existing_report_body(self):
        ReportWriter(self.reports, self.gw).write("market", "PRIOR-MARKET-BODY", {})
        tools, _ = self._build()
        tools["ask_helper"].fn(role="market", question="price risk on Saka?")
        with open(os.path.join(self.reports, "gw04", "market.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("PRIOR-MARKET-BODY", text)
        self.assertIn("— market (asked)", text)

    def test_unknown_role_is_refused_without_calling_the_runner(self):
        tools, _ = self._build()
        out = tools["ask_helper"].fn(role="gardener", question="x")
        self.assertIn("gardener", out)
        self.assertEqual(self.asked, [])
        self.assertFalse(os.path.exists(os.path.join(self.reports, "gw04")))


class ReadReportTest(GafferToolsHarness):
    def test_reads_a_written_report_body(self):
        ReportWriter(self.reports, self.gw).write("fixtures", "FIXTURES-BODY-XYZ", {})
        tools, _ = self._build()
        out = tools["read_report"].fn(role="fixtures")
        self.assertIn("FIXTURES-BODY-XYZ", out)

    def test_missing_report_says_so(self):
        tools, _ = self._build()
        out = tools["read_report"].fn(role="quality")
        self.assertIn("no", out.lower())
        self.assertIn("quality", out)

    def test_path_traversal_role_is_refused_and_reads_nothing(self):
        # A model-chosen role that escapes the GW folder must never read a file.
        ReportWriter(self.reports, self.gw).write("fixtures", "SECRET-BODY", {})
        tools, _ = self._build()
        out = tools["read_report"].fn(role="../../fixtures")
        self.assertIn("unknown role", out)
        self.assertNotIn("SECRET-BODY", out)


class ReadProjectionsTest(GafferToolsHarness):
    def test_returns_rows_across_gameweeks_for_a_named_player(self):
        tools, _ = self._build()
        out = tools["read_projections"].fn(name="Raya")
        self.assertIn("Raya", out)
        self.assertIn("GW1", out)
        self.assertIn("GW2", out)

    def test_unknown_player_says_so(self):
        tools, _ = self._build()
        out = tools["read_projections"].fn(name="Nobody")
        self.assertIn("Nobody", out)


class FplLookupTest(GafferToolsHarness):
    def test_player_lookup_is_structured_from_the_bootstrap(self):
        tools, t = self._build()
        out = tools["fpl_lookup"].fn(kind="player", name="Haaland")
        self.assertIn("Haaland", out)
        self.assertIn("MCI", out)
        self.assertIn("15.1", out)                 # now_cost 151 -> £15.1m
        gets = [u for m, u in t.requests if m == "GET"]
        self.assertEqual(gets, [BOOTSTRAP])

    def test_player_lookup_caches_the_bootstrap_across_calls(self):
        tools, t = self._build()
        tools["fpl_lookup"].fn(kind="player", name="Haaland")
        tools["fpl_lookup"].fn(kind="player", name="Saka")
        self.assertEqual([u for m, u in t.requests if m == "GET"], [BOOTSTRAP])

    def test_team_lookup(self):
        tools, _ = self._build()
        out = tools["fpl_lookup"].fn(kind="team", name="Arsenal")
        self.assertIn("ARS", out)

    def test_fixtures_lookup_lists_upcoming_matches(self):
        tools, t = self._build()
        out = tools["fpl_lookup"].fn(kind="fixtures", name="Man City")
        self.assertIn("GW4", out)
        gets = [u for m, u in t.requests if m == "GET"]
        self.assertIn(FIXTURES, gets)

    def test_off_allowlist_is_never_the_issue_here_but_bad_kind_is_reported(self):
        tools, _ = self._build()
        out = tools["fpl_lookup"].fn(kind="manager", name="x")
        self.assertIn("kind", out.lower())


class SearchFetchTest(GafferToolsHarness):
    def test_search_tool_calls_the_searcher(self):
        tools, t = self._build()
        out = tools["search"].fn(query="Saka injury news")
        self.assertIn("Saka fit", out)
        self.assertEqual(len(t.search_requests), 1)

    def test_fetch_tool_is_allowlisted(self):
        tools, t = self._build()
        out = tools["fetch"].fn(url="https://evil.example/x")
        self.assertIn("refused", out)
        self.assertEqual([u for m, u in t.requests if m == "GET"], [])


class TicketTest(GafferToolsHarness):
    def test_open_ticket_labels_gaffer_and_returns_number_and_url(self):
        tools, _ = self._build()
        out = tools["open_ticket"].fn(title="Re-run projections", body="spec here")
        self.assertEqual(self.host.opened[0]["labels"], ["gaffer"])
        self.assertIn("#1", out)
        self.assertIn("https://github.com/x/issues/1", out)

    def test_ticket_status_and_pr_status_coerce_the_number(self):
        tools, _ = self._build()
        self.assertIn("issue #7", tools["ticket_status"].fn(number="7"))
        self.assertIn("pr #9", tools["pr_status"].fn(number=9))


if __name__ == "__main__":
    unittest.main()
