"""OpenRouter LLM client — one chat-completion round-trip per call (#8), grown
in #54 to declare tools, read tool calls, feed tool results back, and log the
usage block + estimated cost on every call."""

import io
import json
import unittest

from daemon.llm import LLM, estimate_cost
from daemon.logging_setup import StructuredLogger
from tests.fakes import FakeTransport, tool_call_message

PRICES = {"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25}}


class CompleteTest(unittest.TestCase):
    def test_returns_reply_content(self):
        llm = LLM(api_key="K", model="moonshotai/kimi-k2.5",
                  transport=FakeTransport(llm_reply="the answer"))

        reply = llm.complete([{"role": "user", "content": "q"}])

        self.assertEqual(reply, "the answer")

    def test_sends_model_and_messages_in_body(self):
        fake = FakeTransport(llm_reply="x")
        llm = LLM(api_key="K", model="moonshotai/kimi-k2.5", transport=fake)

        llm.complete([{"role": "user", "content": "q"}])

        body = fake.llm_requests[0]
        self.assertEqual(body["model"], "moonshotai/kimi-k2.5")
        self.assertEqual(body["messages"], [{"role": "user", "content": "q"}])
        self.assertNotIn("tools", body)


TOOLS = [{"type": "function", "function": {
    "name": "fetch", "description": "GET a page",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}},
                   "required": ["url"]}}}]


class ChatToolsTest(unittest.TestCase):
    def test_declares_tools_and_overrides_model_per_call(self):
        fake = FakeTransport(llm_reply="done")
        llm = LLM(api_key="K", model="moonshotai/kimi-k2.5", transport=fake)

        reply = llm.chat([{"role": "user", "content": "q"}], tools=TOOLS,
                         model="z-ai/glm-5.3-flash")

        body = fake.llm_requests[0]
        self.assertEqual(body["model"], "z-ai/glm-5.3-flash")
        self.assertEqual(body["tools"], TOOLS)
        self.assertEqual(reply.content, "done")
        self.assertEqual(reply.tool_calls, [])

    def test_reads_tool_calls_off_the_reply(self):
        fake = FakeTransport(llm_replies=[
            tool_call_message("fetch", {"url": "https://x.test/p"}, call_id="c1")])
        llm = LLM(api_key="K", transport=fake)

        reply = llm.chat([{"role": "user", "content": "q"}], tools=TOOLS)

        self.assertEqual(len(reply.tool_calls), 1)
        call = reply.tool_calls[0]
        self.assertEqual((call.id, call.name, call.arguments),
                         ("c1", "fetch", {"url": "https://x.test/p"}))
        # The raw assistant message is what the loop must echo back before the
        # tool-result turn (OpenAI-compatible protocol).
        self.assertEqual(reply.message["tool_calls"][0]["id"], "c1")

    def test_malformed_tool_arguments_parse_to_empty_dict_not_a_crash(self):
        fake = FakeTransport(llm_replies=[{
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "c9", "type": "function",
                            "function": {"name": "fetch", "arguments": "{not json"}}]}])
        llm = LLM(api_key="K", transport=fake)

        reply = llm.chat([{"role": "user", "content": "q"}], tools=TOOLS)

        self.assertEqual(reply.tool_calls[0].arguments, {})
        self.assertEqual(reply.content, "")

    def test_plugins_ride_on_the_same_request_shape(self):
        fake = FakeTransport(search_reply="1. Isak fit — bbc.co.uk")
        llm = LLM(api_key="K", transport=fake)

        reply = llm.chat([{"role": "user", "content": "isak fit?"}],
                         plugins=[{"id": "web", "engine": "exa", "max_results": 5}])

        self.assertEqual(fake.search_requests[0]["plugins"][0]["engine"], "exa")
        self.assertIn("Isak fit", reply.content)


class UsageAndCostTest(unittest.TestCase):
    def test_estimate_cost_uses_per_million_prices(self):
        cost = estimate_cost("z-ai/glm-5.3-flash",
                             {"prompt_tokens": 1_000_000, "completion_tokens": 2_000_000},
                             PRICES)
        self.assertAlmostEqual(cost, 0.075 + 0.5)

    def test_estimate_cost_unknown_model_is_none(self):
        self.assertIsNone(estimate_cost("nope/model", {"prompt_tokens": 5}, PRICES))

    def test_every_call_logs_usage_and_cost_with_role_and_wake_id(self):
        fake = FakeTransport(llm_reply="x",
                             usage={"prompt_tokens": 2000, "completion_tokens": 400})
        logbuf = io.StringIO()
        logger = StructuredLogger(stream=logbuf)
        llm = LLM(api_key="K", model="z-ai/glm-5.3-flash", transport=fake,
                  logger=logger, prices=PRICES, wake_id="w1")

        reply = llm.chat([{"role": "user", "content": "q"}], role="availability")

        self.assertEqual(reply.usage["prompt_tokens"], 2000)
        events = [json.loads(l) for l in logbuf.getvalue().splitlines()]
        call = [e for e in events if e["event"] == "llm_call"][0]
        self.assertEqual(call["role"], "availability")
        self.assertEqual(call["wake_id"], "w1")
        self.assertEqual(call["model"], "z-ai/glm-5.3-flash")
        self.assertEqual(call["prompt_tokens"], 2000)
        self.assertEqual(call["completion_tokens"], 400)
        self.assertAlmostEqual(call["cost_usd"], 2000 * 0.075e-6 + 400 * 0.25e-6)
        self.assertIn("finish_reason", call)     # "length" = budget ran out, visible
        # Running totals for the wake rails (#56) and the selftest printout.
        self.assertEqual(llm.calls, 1)
        self.assertAlmostEqual(llm.cost_usd, call["cost_usd"])
        self.assertEqual(llm.tokens, 2400)

    def test_complete_also_logs_with_default_gaffer_role(self):
        fake = FakeTransport(llm_reply="x")
        logbuf = io.StringIO()
        llm = LLM(api_key="K", transport=fake, logger=StructuredLogger(stream=logbuf))

        llm.complete([{"role": "user", "content": "q"}])

        call = json.loads(logbuf.getvalue().splitlines()[0])
        self.assertEqual(call["event"], "llm_call")
        self.assertEqual(call["role"], "gaffer")


class PerModelRepliesTest(unittest.TestCase):
    """FakeTransport per-model reply queues (#56): the fan-out drives several
    models through one transport, each needing its own scripted replies."""

    def _q(self, llm, model):
        return llm.chat([{"role": "user", "content": "q"}], model=model).content

    def test_per_model_queue_pops_before_the_shared_fallback(self):
        fake = FakeTransport(llm_reply="SHARED",
                             llm_replies_by_model={"model-a": ["A1", "A2"]})
        llm = LLM(api_key="K", transport=fake)
        self.assertEqual(self._q(llm, "model-a"), "A1")
        self.assertEqual(self._q(llm, "model-a"), "A2")
        self.assertEqual(self._q(llm, "model-b"), "SHARED")   # never in the map
        # A drained per-model queue is loud: an extra call is a test bug, never
        # masked by the shared fallback.
        with self.assertRaises(AssertionError):
            self._q(llm, "model-a")

    def test_absent_model_falls_back_to_shared_llm_replies(self):
        fake = FakeTransport(llm_replies=["S1", "S2"],
                             llm_replies_by_model={"model-a": ["A1"]})
        llm = LLM(api_key="K", transport=fake)
        self.assertEqual(self._q(llm, "model-b"), "S1")
        self.assertEqual(self._q(llm, "model-a"), "A1")
        self.assertEqual(self._q(llm, "model-b"), "S2")

    def test_model_is_recorded_in_llm_requests(self):
        fake = FakeTransport(llm_replies_by_model={"model-a": ["A1"]})
        llm = LLM(api_key="K", transport=fake)
        self._q(llm, "model-a")
        self.assertEqual(fake.llm_requests[-1]["model"], "model-a")

    def test_plugin_search_call_ignores_the_per_model_map(self):
        fake = FakeTransport(search_reply="1. Isak fit — bbc.co.uk",
                             llm_replies_by_model={"z-ai/glm-5.3-flash": ["SHOULD-NOT-USE"]})
        llm = LLM(api_key="K", transport=fake)
        reply = llm.chat([{"role": "user", "content": "isak?"}], model="z-ai/glm-5.3-flash",
                         plugins=[{"id": "web", "engine": "exa", "max_results": 5}])
        self.assertIn("Isak fit", reply.content)
        self.assertEqual(fake.llm_replies_by_model["z-ai/glm-5.3-flash"], ["SHOULD-NOT-USE"])


if __name__ == "__main__":
    unittest.main()
