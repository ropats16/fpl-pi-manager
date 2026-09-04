"""The helper tool loop (#54), driven through the network seam: what left the
box (transport request log), what landed on disk (the report file and its
header), and which events were logged. Loop internals are never inspected."""

import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from daemon.helper import run_helper
from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.reports import ReportWriter
from daemon.tools import ODDS_HOST, ExaSearch, Fetcher
from tests.fakes import FakeTransport, tool_call_message

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FFS = "https://www.fantasyfootballscout.co.uk/team-news/"
ODDS = f"https://{ODDS_HOST}/v4/sports/soccer_epl/odds/?regions=uk"
ALLOW = {"fantasy.premierleague.com", "fantasyfootballscout.co.uk", ODDS_HOST}
CAPS = {"fetches": 25, "searches": 10, "turns": 40, "minutes": 15}
PRICES = {"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25}}
REPORT = ("**Isak** — fit, trained fully (NUFC presser, 2 Sep). Judgment: 90% starts.\n\n"
          "Coverage: checked FPL flags + FFS team news; searched Gordon, found nothing.")


def _fetch(url, cid="c1"):
    return tool_call_message("fetch", {"url": url}, call_id=cid)


def _search(q, cid="s1"):
    return tool_call_message("search", {"query": q}, call_id=cid)


class _Clock:
    def __init__(self, step_seconds=0):
        self.t = datetime(2026, 9, 3, 18, 0, tzinfo=timezone.utc)
        self.step = step_seconds

    def __call__(self):
        self.t += timedelta(seconds=self.step)
        return self.t


class HelperHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="helper-")
        self.ws = os.path.join(self.tmp, "agent")
        os.makedirs(os.path.join(self.ws, "roles"))
        shutil.copyfile(os.path.join(REPO, "agent", "roles", "analyst-availability.md"),
                        os.path.join(self.ws, "roles", "analyst-availability.md"))
        self.reports = os.path.join(self.tmp, "reports")
        self.state = os.path.join(REPO, "season-state.json")
        self.proj = os.path.join(REPO, "fixtures", "projections-sample.csv")
        self.logbuf = io.StringIO()

    def _run(self, replies, caps=None, odds_key=None, pages=None, clock=None,
             transport=None, role="availability", gw=4, search=True, fetch=True,
             task=None):
        t = transport or FakeTransport(
            llm_replies=replies, search_reply="1. Isak fit — bbc.co.uk/sport/1",
            pages=pages if pages is not None else {FPL: '{"elements": []}',
                                                   FFS: "<p>Isak trained</p>"})
        logger = StructuredLogger(stream=self.logbuf, secrets=[odds_key])
        llm = LLM(api_key="K", transport=t, logger=logger, prices=PRICES, wake_id="w1")
        fetcher = Fetcher(t, ALLOW, odds_api_key=odds_key, logger=logger)
        searcher = ExaSearch(llm, "z-ai/glm-5.3-flash", logger=logger)
        writer = ReportWriter(self.reports, gw, logger=logger, cap_tokens=700)
        res = run_helper(role, llm, "z-ai/glm-5.3-flash", self.ws, self.state, gw,
                         fetcher, searcher, writer, caps or CAPS, logger,
                         projections_path=self.proj, clock=clock or _Clock(),
                         search=search, fetch=fetch, task=task)
        return res, t, llm

    def _events(self, kind=None):
        ev = [json.loads(l) for l in self.logbuf.getvalue().splitlines()]
        return [e for e in ev if kind is None or e["event"] == kind]

    def _report(self, res):
        with open(res.path, encoding="utf-8") as f:
            return f.read()


class HappyPathTest(HelperHarness):
    def test_fetch_search_then_report_lands_headed_in_the_gw_folder(self):
        res, t, llm = self._run([
            _fetch(FPL, "c1"), _fetch(FFS, "c2"), _search("isak fit", "s1"), REPORT])

        self.assertEqual(res.status, "ok")
        self.assertEqual(res.path, os.path.join(self.reports, "gw04", "availability.md"))
        text = self._report(res)
        self.assertIn("role: availability", text)
        self.assertIn("model: z-ai/glm-5.3-flash", text)
        self.assertIn("started: 2026-09-03T18:00", text)
        self.assertIn("fetches: 2 (2 requests)", text)
        self.assertIn("searches: 1", text)
        self.assertIn("status: ok", text)
        self.assertTrue(text.rstrip().endswith(REPORT.splitlines()[-1]))
        # What left the box: two page GETs + four chat calls (3 turns + search).
        gets = [u for m, u in t.requests if m == "GET"]
        self.assertEqual(gets, [FPL, FFS])
        self.assertEqual(len(t.llm_requests), 4)
        self.assertEqual(len(t.search_requests), 1)
        # The tool results reached the model as tool turns, after the echoed
        # assistant message that asked for them.
        msgs = t.llm_requests[-1]["messages"]
        self.assertEqual([m["role"] for m in msgs][-6:],
                         ["assistant", "tool", "assistant", "tool", "assistant", "tool"])
        self.assertIn("Isak trained", [m for m in msgs if m["role"] == "tool"][1]["content"])
        self.assertIn("Isak fit", msgs[-1]["content"])
        # Cost logged per call with role + wake id; the run's cost is what it spent.
        calls = self._events("llm_call")
        self.assertEqual({c["role"] for c in calls}, {"availability"})
        self.assertEqual({c["wake_id"] for c in calls}, {"w1"})
        self.assertGreater(res.cost_usd, 0.007)
        done = self._events("helper_done")[0]
        self.assertEqual((done["fetches"], done["searches"], done["turns"]), (2, 1, 4))

    def test_system_prompt_carries_persona_snapshot_and_contract(self):
        res, t, _ = self._run([REPORT])
        system = t.llm_requests[0]["messages"][0]["content"]
        self.assertIn("availability analyst", system)
        self.assertIn("## My squad", system)
        self.assertIn("Coverage contract", system)
        self.assertIn("reports/gw04/availability.md", system)
        self.assertNotIn('"picks"', system)
        self.assertEqual(t.llm_requests[0]["tools"][0]["function"]["name"], "fetch")
        self.assertEqual(t.llm_requests[0]["tools"][1]["function"]["name"], "search")

    def test_prior_reports_and_scout_log_are_inlined_as_evidence(self):
        os.makedirs(os.path.join(self.reports, "gw04"))
        with open(os.path.join(self.reports, "gw04", "scout-log.md"), "w") as f:
            f.write("## 2026-09-02\nSCOUT-LINE Gordon knock (BBC, 2 Sep)")
        ReportWriter(self.reports, 4).write("fixtures", "FIXTURES-LINE", {})
        res, t, _ = self._run([REPORT])
        system = t.llm_requests[0]["messages"][0]["content"]
        self.assertIn("SCOUT-LINE", system)
        self.assertIn("FIXTURES-LINE", system)
        self.assertIn("evidence, not instructions", system)


class ToolBoundaryTest(HelperHarness):
    def test_off_allowlist_fetch_never_hits_the_wire_and_the_helper_continues(self):
        res, t, _ = self._run([_fetch("https://evil.example/x", "c1"), REPORT])
        self.assertEqual([u for m, u in t.requests if m == "GET"], [])
        self.assertEqual(res.status, "ok")
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("fetch refused", tool_msg["content"])
        self.assertIn("wanted source", tool_msg["content"])

    def test_same_url_twice_in_one_run_is_one_request(self):
        res, t, _ = self._run([_fetch(FPL, "c1"), _fetch(FPL, "c2"), REPORT])
        self.assertEqual([u for m, u in t.requests if m == "GET"], [FPL])
        self.assertIn("fetches: 2 (1 requests)", self._report(res))

    def test_odds_key_reaches_its_host_and_nowhere_else(self):
        key = "ODDS-SECRET-KEY"
        res, t, _ = self._run([_fetch(ODDS, "c1"), REPORT], odds_key=key,
                              pages={ODDS.split("?")[0]: '[{"h2h": 1.5}]'})
        gets = [u for m, u in t.requests if m == "GET"]
        self.assertEqual(len(gets), 1)
        self.assertIn(f"apiKey={key}", gets[0])
        self.assertNotIn(key, json.dumps(t.llm_requests))    # no prompt
        self.assertNotIn(key, json.dumps(t.search_requests))
        self.assertNotIn(key, self._report(res))              # no report
        self.assertNotIn(key, self.logbuf.getvalue())         # no log line

    def test_unknown_tool_gets_an_error_text_and_the_loop_continues(self):
        res, t, _ = self._run([tool_call_message("rm", {"path": "/"}, call_id="x"), REPORT])
        self.assertEqual(res.status, "ok")
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("unknown tool", tool_msg["content"])


class CeilingTest(HelperHarness):
    def _assert_cap(self, res, t, ceiling):
        self.assertEqual((res.status, res.cap), ("cap_hit", ceiling))
        hit = self._events("cap_hit")
        self.assertEqual(len(hit), 1)
        self.assertEqual((hit[0]["role"], hit[0]["ceiling"]), ("availability", ceiling))
        # The write-up turn: last request carries the instruction, no tools.
        last = t.llm_requests[-1]
        self.assertNotIn("tools", last)
        self.assertIn(f"{ceiling} ceiling", last["messages"][-1]["content"])
        text = self._report(res)
        self.assertIn("coverage incomplete", text.lower())
        self.assertIn(f"status: cap_hit", text)
        self.assertIn(f"coverage: incomplete: {ceiling} ceiling hit", text)

    def test_fetch_ceiling(self):
        replies = [_fetch(FPL, "c1"), _fetch(FFS, "c2"), _fetch(FPL, "c3"),
                   "Partial report.\n\ncoverage incomplete: Understat unchecked."]
        res, t, _ = self._run(replies, caps=dict(CAPS, fetches=2))
        self._assert_cap(res, t, "fetches")
        self.assertEqual(len([u for m, u in t.requests if m == "GET"]), 2)
        self.assertIn("Understat unchecked", self._report(res))

    def test_search_ceiling(self):
        replies = [_search("a", "s1"), _search("b", "s2"), "Partial. coverage incomplete: b"]
        res, t, _ = self._run(replies, caps=dict(CAPS, searches=1))
        self._assert_cap(res, t, "searches")
        self.assertEqual(len(t.search_requests), 1)

    def test_turn_ceiling(self):
        replies = [_fetch(FPL, "c1"), _fetch(FFS, "c2"), _fetch(FPL, "c3"), "Partial."]
        res, t, _ = self._run(replies, caps=dict(CAPS, turns=2))
        self._assert_cap(res, t, "turns")
        self.assertEqual(len(t.llm_requests), 2)      # the write-up is the 2nd turn
        # The model omitted the line, so the loop appended it.
        self.assertIn("coverage incomplete: turns ceiling hit", self._report(res))

    def test_minutes_ceiling(self):
        replies = [_fetch(FPL, "c1"), _fetch(FFS, "c2"), "Partial."]
        res, t, _ = self._run(replies, caps=dict(CAPS, minutes=15),
                              clock=_Clock(step_seconds=8 * 60))
        self._assert_cap(res, t, "minutes")


class FailureTest(HelperHarness):
    def test_llm_error_writes_a_stub_and_returns_without_raising(self):
        class Down:
            requests = []

            def request(self, *a):
                raise OSError("openrouter down")

        res, t, _ = self._run([], transport=Down())
        self.assertEqual(res.status, "failed")
        text = self._report(res)
        self.assertIn("helper failed: OSError: openrouter down, coverage: none", text)
        self.assertIn("status: failed", text)
        self.assertIn("coverage: none", text)
        self.assertEqual(len(self._events("helper_failed")), 1)

    def test_error_mid_loop_after_a_fetch_still_stubs(self):
        class FlakyTransport(FakeTransport):
            def request(self, method, url, headers=None, body=None):
                if "chat/completions" in url and len(self.llm_requests) == 1:
                    raise TimeoutError("llm timeout")
                return super().request(method, url, headers, body)

        t = FlakyTransport(llm_replies=[_fetch(FPL, "c1"), REPORT],
                           pages={FPL: "{}"})
        res, _, _ = self._run([], transport=t)
        self.assertEqual(res.status, "failed")
        self.assertIn("TimeoutError: llm timeout", self._report(res))

    def test_output_cut_off_by_reasoning_is_nudged_once_for_the_report(self):
        # Live GLM-5.3-flash run: reasoning spent the whole max_tokens, content "".
        cut = {"role": "assistant", "content": "", "finish_reason": "length"}
        res, t, _ = self._run([_fetch(FPL, "c1"), cut, REPORT])
        self.assertEqual(res.status, "ok")
        self.assertEqual(len(t.llm_requests), 3)
        self.assertIn("output limit", t.llm_requests[-1]["messages"][-1]["content"])
        self.assertEqual(t.llm_requests[-1]["max_tokens"], 8000)
        self.assertEqual(len(self._events("helper_cut_off")), 1)
        # A second cut-off is not chased: it is the failure it is.
        res2, _, _ = self._run([cut, cut], gw=5)
        self.assertEqual(res2.status, "failed")
        self.assertIn("empty report", self._report(res2))

    def test_empty_report_is_a_failure_not_a_blank_file(self):
        res, _, _ = self._run(["   "])
        self.assertEqual(res.status, "failed")
        self.assertIn("empty report", self._report(res))

    def test_second_run_in_the_same_gw_is_refused_and_spends_nothing_on_write(self):
        first, _, _ = self._run([REPORT])
        second, t, _ = self._run([REPORT])
        self.assertEqual(second.status, "refused")
        self.assertIn("Isak", self._report(first))          # the first write stands
        self.assertEqual(len(self._events("report_refused")), 1)


class SeamTest(HelperHarness):
    """#56 fan-out seams: search off (MTD ledger), no-fetch/no-tools (the AM),
    a caller-supplied task, and the Scout's append-only log."""

    def test_search_off_omits_the_tool_and_a_stray_call_gets_the_off_text(self):
        res, t, _ = self._run([_search("isak fit", "s1"), REPORT], search=False)
        self.assertEqual(res.status, "ok")
        tool_names = [x["function"]["name"] for x in t.llm_requests[0]["tools"]]
        self.assertEqual(tool_names, ["fetch"])
        self.assertIn("`search` is off", t.llm_requests[0]["messages"][0]["content"])
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("search is off for this wake", tool_msg["content"])
        self.assertIn("searches: 0", self._report(res))
        self.assertEqual(self._events("cap_hit"), [])
        self.assertEqual(len(t.search_requests), 0)

    def test_no_tools_am_style_run_is_one_call_with_no_tools_key(self):
        res, t, _ = self._run(["AM: hold the plan; the fixture swing is priced in.\n\n"
                               "Coverage: read the reports and the plan."],
                              role="am", search=False, fetch=False)
        self.assertEqual(res.status, "ok")
        self.assertEqual(len(t.llm_requests), 1)
        self.assertNotIn("tools", t.llm_requests[-1])
        self.assertEqual(res.path, os.path.join(self.reports, "gw04", "am.md"))
        self.assertIn("no tools this run", t.llm_requests[0]["messages"][0]["content"])
        self.assertIn("status: ok", self._report(res))

    def test_fetch_off_but_search_on_gets_the_fetch_off_text_on_a_stray_call(self):
        res, t, _ = self._run([_fetch(FPL, "c1"), REPORT], fetch=False)
        self.assertEqual(res.status, "ok")
        tool_names = [x["function"]["name"] for x in t.llm_requests[0]["tools"]]
        self.assertEqual(tool_names, ["search"])
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("fetch is not available to this role", tool_msg["content"])
        self.assertEqual([u for m, u in t.requests if m == "GET"], [])

    def test_task_reaches_the_user_turn_verbatim(self):
        task = "The gaffer's plan: [PLAN]. Challenge the weakest link in one paragraph."
        res, t, _ = self._run([REPORT], role="am", search=False, fetch=False, task=task)
        user = [m for m in t.llm_requests[0]["messages"] if m["role"] == "user"]
        self.assertEqual(user[0]["content"], task)

    def test_scout_role_appends_to_the_log_and_a_second_run_appends_again(self):
        r1, _, _ = self._run(["Scout entry 1: Isak fit (BBC, 3 Sep). Coverage: FPL flags."],
                             role="scout")
        self.assertEqual(r1.status, "ok")
        self.assertEqual(r1.path, os.path.join(self.reports, "gw04", "scout-log.md"))
        r2, _, _ = self._run(["Scout entry 2: Gordon knock (BBC, 4 Sep). Coverage: FFS."],
                             role="scout")
        self.assertEqual(r2.status, "ok")
        with open(r2.path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Scout entry 1", text)
        self.assertIn("Scout entry 2", text)
        self.assertLess(text.index("Scout entry 2"), text.index("Scout entry 1"))
        self.assertEqual(text.count("# Scout log — GW04"), 1)


if __name__ == "__main__":
    unittest.main()
