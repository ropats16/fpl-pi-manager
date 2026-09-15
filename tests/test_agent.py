"""The shared tool-loop core `run_agent` (spec §1), driven through the network
seam: what the model was offered, which tools ran, and the caps/status the loop
enforces. Never inspects loop internals beyond the public AgentResult."""

import io
import json
import unittest
from datetime import datetime, timedelta, timezone

from daemon.agent import AgentResult, Caps, Tool, run_agent
from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from tests.fakes import FakeTransport, tool_call_message

PRICES = {"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25},
          "moonshotai/kimi-k2.5": {"prompt": 0.6, "completion": 2.5}}
CAPS = Caps(turns=12, minutes=6, cost_usd=0.40)


class _Clock:
    def __init__(self, step_seconds=0):
        self.t = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        self.step = step_seconds

    def __call__(self):
        self.t += timedelta(seconds=self.step)
        return self.t


class AgentHarness(unittest.TestCase):
    def setUp(self):
        self.logbuf = io.StringIO()

    def _llm(self, transport, model="moonshotai/kimi-k2.5"):
        logger = StructuredLogger(stream=self.logbuf, secrets=[])
        return LLM(api_key="K", model=model, transport=transport, logger=logger,
                   prices=PRICES, wake_id="w1"), logger

    def _tool(self, name="lookup", cap=None, fn=None):
        calls = []

        def default_fn(**kw):
            calls.append(kw)
            return f"{name} result"
        t = Tool(name, f"the {name} tool", {"type": "object",
                 "properties": {"q": {"type": "string"}}, "required": []},
                 fn or default_fn, cap=cap)
        self.recorded_calls = calls      # __slots__ Tool can't hold test state
        return t

    def _events(self, kind=None):
        ev = [json.loads(l) for l in self.logbuf.getvalue().splitlines()]
        return [e for e in ev if kind is None or e["event"] == kind]


class NoToolsTest(AgentHarness):
    def test_no_tools_is_a_single_plain_completion(self):
        t = FakeTransport(llm_reply="plain answer")
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [], CAPS, logger, role="gaffer")
        self.assertIsInstance(res, AgentResult)
        self.assertEqual(res.reply, "plain answer")
        self.assertEqual(res.turns, 1)
        self.assertEqual(res.tool_calls, {})
        self.assertEqual(res.status, "ok")
        self.assertEqual(len(t.llm_requests), 1)
        self.assertNotIn("tools", t.llm_requests[0])
        # role reaches the ledger exactly as llm.complete would log it.
        self.assertEqual({c["role"] for c in self._events("llm_call")}, {"gaffer"})

    def test_none_tools_behaves_like_empty(self):
        t = FakeTransport(llm_reply="x")
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        None, CAPS, logger, role="gaffer")
        self.assertEqual(res.reply, "x")
        self.assertEqual(len(t.llm_requests), 1)


class ToolLoopTest(AgentHarness):
    def test_one_tool_call_then_a_final_answer(self):
        tool = self._tool("lookup")
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {"q": "haaland"}, "c1"),
            "final answer"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [tool], CAPS, logger, role="gaffer")
        self.assertEqual(res.reply, "final answer")
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.turns, 2)
        self.assertEqual(res.tool_calls, {"lookup": 1})
        self.assertEqual(self.recorded_calls, [{"q": "haaland"}])
        # The offered schema is the Tool's own name/description/parameters.
        self.assertEqual(t.llm_requests[0]["tools"][0]["function"]["name"], "lookup")
        # The tool result rode back as a tool turn after the echoed assistant msg.
        msgs = t.llm_requests[-1]["messages"]
        self.assertEqual([m["role"] for m in msgs][-2:], ["assistant", "tool"])
        self.assertIn("lookup result", msgs[-1]["content"])

    def test_unknown_tool_gets_error_text_and_the_loop_continues(self):
        t = FakeTransport(llm_replies=[
            tool_call_message("rm", {"path": "/"}, "c1"), "recovered"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], CAPS, logger, role="gaffer")
        self.assertEqual(res.reply, "recovered")
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("unknown tool", tool_msg["content"])

    def test_a_tool_that_raises_is_caught_and_reported(self):
        def boom(**kw):
            raise RuntimeError("kaboom")
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"), "after"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup", fn=boom)], CAPS, logger, role="gaffer")
        self.assertEqual(res.reply, "after")
        self.assertEqual(res.status, "ok")
        tool_msg = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("kaboom", tool_msg["content"])


class PerToolCapTest(AgentHarness):
    def test_over_cap_returns_a_fixed_result_counted_and_never_calls_fn(self):
        tool = self._tool("lookup", cap=1)
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {"q": "a"}, "c1"),
            tool_call_message("lookup", {"q": "b"}, "c2"),
            "done"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [tool], CAPS, logger, role="gaffer")
        self.assertEqual(res.reply, "done")
        # fn ran once; the second call is over cap -> fixed result, still counted.
        self.assertEqual(self.recorded_calls, [{"q": "a"}])
        self.assertEqual(res.tool_calls, {"lookup": 2})
        tool_msgs = [m for m in t.llm_requests[-1]["messages"] if m["role"] == "tool"]
        self.assertIn("cap", tool_msgs[-1]["content"].lower())


class CapTest(AgentHarness):
    def test_turns_cap_stops_the_loop_with_last_text(self):
        # A tool call every turn: the loop never gets a final answer, so the
        # turns cap ends it and the last assistant text is the reply.
        replies = [tool_call_message("lookup", {}, f"c{i}") for i in range(10)]
        t = FakeTransport(llm_replies=replies)
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=3, minutes=6, cost_usd=1.0),
                        logger, role="gaffer")
        self.assertEqual(res.status, "cap_hit:turns")
        self.assertEqual(res.turns, 3)
        self.assertEqual(len(t.llm_requests), 3)

    def test_minutes_cap_stops_before_the_next_call(self):
        replies = [tool_call_message("lookup", {}, f"c{i}") for i in range(10)]
        t = FakeTransport(llm_replies=replies)
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=99, minutes=6, cost_usd=1.0),
                        logger, role="gaffer", clock=_Clock(step_seconds=4 * 60))
        self.assertEqual(res.status, "cap_hit:minutes")

    def test_cost_cap_stops_the_loop(self):
        replies = [tool_call_message("lookup", {}, f"c{i}") for i in range(10)]
        t = FakeTransport(llm_replies=replies,
                          usage={"prompt_tokens": 1_000_000, "completion_tokens": 0})
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=99, minutes=99, cost_usd=1.0),
                        logger, role="gaffer")
        self.assertEqual(res.status, "cap_hit:cost")
        self.assertGreater(res.cost_usd, 0)


class StopHookTest(AgentHarness):
    def test_stop_ends_the_loop_before_the_next_call(self):
        # `stop()` flips true after the first turn: the loop must end with status
        # `stopped` and NOT consume the queued second tool call (spec §4 engineer
        # hard-stop on a spent fix budget).
        state = {"turns": 0, "done": False}

        def bump(**kw):
            state["done"] = True     # the tool run flags "stop next time"
            return "ran"
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"),
            tool_call_message("lookup", {}, "c2"), "unreached"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup", fn=bump)], CAPS, logger, role="gaffer",
                        stop=lambda: state["done"])
        self.assertEqual(res.status, "stopped")
        self.assertEqual(res.turns, 1)                 # stopped before the 2nd call
        self.assertEqual(len(t.llm_requests), 1)


class ErrorTest(AgentHarness):
    def test_llm_error_never_raises_and_sets_error_status(self):
        class Down:
            requests = []

            def request(self, *a):
                raise OSError("openrouter down")
        llm, logger = self._llm(Down())
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], CAPS, logger, role="gaffer")
        self.assertEqual(res.status, "error")
        self.assertTrue(res.reply)                       # a fixed line, never blank
        self.assertEqual(len(self._events("agent_error")), 1)


if __name__ == "__main__":
    unittest.main()


class CapLogTest(AgentHarness):
    def test_a_cap_ends_the_loop_with_an_agent_cap_hit_event(self):
        replies = [tool_call_message("lookup", {}, f"c{i}") for i in range(10)]
        t = FakeTransport(llm_replies=replies)
        llm, logger = self._llm(t)
        run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                  [self._tool("lookup")], Caps(turns=2, minutes=6, cost_usd=1.0),
                  logger, role="gaffer")
        ev = self._events("agent_cap_hit")
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["role"], ev[0]["status"], ev[0]["turns"]),
                         ("gaffer", "cap_hit:turns", 2))
        self.assertIn("cost_usd", ev[0])

    def test_a_clean_finish_logs_no_cap_event(self):
        t = FakeTransport(llm_replies=[tool_call_message("lookup", {}, "c1"), "done"])
        llm, logger = self._llm(t)
        run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                  [self._tool("lookup")], CAPS, logger, role="gaffer")
        self.assertEqual(self._events("agent_cap_hit"), [])


class FinishOnCapTest(AgentHarness):
    """Spec §2: with `finish_on_cap` set, a cap after tool turns earns ONE more
    toolless call whose text is the reply; status keeps the cap name."""

    def test_final_toolless_turn_answers_from_what_was_gathered(self):
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"),
            tool_call_message("lookup", {}, "c2"),
            "summary from gathered facts"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=2, minutes=6, cost_usd=1.0),
                        logger, role="gaffer", finish_on_cap="answer now, no tools")
        self.assertEqual(res.reply, "summary from gathered facts")
        self.assertEqual(res.status, "cap_hit:turns")
        self.assertEqual(res.turns, 3)
        self.assertEqual(len(t.llm_requests), 3)
        final = t.llm_requests[-1]
        self.assertNotIn("tools", final)                       # no tools offered
        self.assertEqual(final["messages"][-1]["role"], "user")
        self.assertIn("answer now", final["messages"][-1]["content"])
        self.assertEqual(final["messages"][-2]["role"], "tool")   # evidence kept

    def test_without_finish_on_cap_no_extra_call_is_made(self):
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"),
            tool_call_message("lookup", {}, "c2"), "unreached"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=2, minutes=6, cost_usd=1.0),
                        logger, role="gaffer")
        self.assertEqual(len(t.llm_requests), 2)
        self.assertIn("reached a limit", res.reply)

    def test_a_failed_final_turn_falls_back_to_the_placeholder(self):
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"),
            tool_call_message("lookup", {}, "c2"), ""])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=2, minutes=6, cost_usd=1.0),
                        logger, role="gaffer", finish_on_cap="answer now")
        self.assertIn("reached a limit", res.reply)
        self.assertEqual(res.status, "cap_hit:turns")

    def test_an_llm_error_after_a_tool_turn_also_earns_the_final_turn(self):
        # Spec §2: "ends on cap_hit:* or error". The 2nd call blows up (a
        # drained per-model queue raises inside the transport), the 3rd answers.
        class Flaky(FakeTransport):
            def request(self, method, url, headers=None, body=None):
                if "chat/completions" in url and len(self.llm_requests) == 1:
                    self.llm_requests.append({"boom": True})
                    raise RuntimeError("502 from upstream")
                return super().request(method, url, headers, body)
        t = Flaky(llm_replies=[tool_call_message("lookup", {}, "c1"), "salvaged"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], CAPS, logger, role="gaffer",
                        finish_on_cap="answer now")
        self.assertEqual(res.status, "error")
        self.assertEqual(res.reply, "salvaged")

    def test_the_cap_event_counts_the_final_turn_spend(self):
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1"),
            tool_call_message("lookup", {}, "c2"), "summary"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=2, minutes=6, cost_usd=1.0),
                        logger, role="gaffer", finish_on_cap="answer now")
        ev = self._events("agent_cap_hit")[0]
        self.assertEqual(ev["turns"], 3)
        self.assertAlmostEqual(ev["cost_usd"], res.cost_usd, places=6)

    def test_a_cap_before_any_tool_turn_earns_no_final_turn(self):
        # turns=0 cap: nothing gathered, nothing to summarise from.
        t = FakeTransport(llm_replies=["unreached"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], Caps(turns=0, minutes=6, cost_usd=1.0),
                        logger, role="gaffer", finish_on_cap="answer now")
        self.assertEqual(len(t.llm_requests), 0)
        self.assertIn("reached a limit", res.reply)

    def test_a_stop_earns_no_final_turn(self):
        # The engineer's `stop` does its own finish (spec §4); no extra call here.
        t = FakeTransport(llm_replies=[tool_call_message("lookup", {}, "c1"), "unreached"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], CAPS, logger, role="gaffer",
                        stop=lambda: len(t.llm_requests) > 0, finish_on_cap="answer now")
        self.assertEqual(res.status, "stopped")
        self.assertEqual(len(t.llm_requests), 1)


class ProgressTest(AgentHarness):
    """Spec §3: `progress(text)` hears the model thinking aloud (text riding
    with tool calls) and a Tool's own start/done notes, in order."""

    def _noting_tool(self):
        def note(phase, arguments, result):
            if phase == "start":
                return f"⏳ looking up {arguments.get('q')}"
            return f"✅ lookup done — {result}"
        tool = self._tool("lookup")
        tool.progress = note
        return tool

    def test_think_aloud_and_tool_notes_arrive_in_order(self):
        heard = []
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {"q": "shaw"}, "c1", content="Checking Shaw first."),
            "final"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._noting_tool()], CAPS, logger, role="gaffer",
                        progress=heard.append)
        self.assertEqual(res.reply, "final")
        self.assertEqual(heard, ["Checking Shaw first.", "⏳ looking up shaw",
                                 "✅ lookup done — lookup result"])

    def test_a_final_answer_is_not_a_progress_note(self):
        heard = []
        t = FakeTransport(llm_replies=["just an answer"])
        llm, logger = self._llm(t)
        run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                  [self._tool("lookup")], CAPS, logger, role="gaffer",
                  progress=heard.append)
        self.assertEqual(heard, [])

    def test_a_tool_without_a_note_and_a_raising_progress_are_both_silent(self):
        def boom(text):
            raise RuntimeError("telegram down")
        t = FakeTransport(llm_replies=[
            tool_call_message("lookup", {}, "c1", content="thinking"), "final"])
        llm, logger = self._llm(t)
        res = run_agent([{"role": "user", "content": "hi"}], llm, llm.model,
                        [self._tool("lookup")], CAPS, logger, role="gaffer",
                        progress=boom)
        self.assertEqual(res.reply, "final")          # a bad ping never breaks the run
        self.assertEqual(res.status, "ok")
