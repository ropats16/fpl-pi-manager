"""OpenRouter LLM client — one chat-completion round-trip per call (#8)."""

import unittest

from daemon.llm import LLM
from tests.fakes import FakeTransport


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


if __name__ == "__main__":
    unittest.main()
