"""The wake->reply loop, driven end-to-end through the faked HTTP edge.

Real Telegram + LLM client code runs; only daemon.http.Transport is faked, so
these are the HTTP-edge acceptance tests for #15.
"""

import io
import json
import unittest

from daemon.agent import Tool
from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.runtime import build_stack
from tests.fakes import (FakeTransport, callback_query, private_message,
                         tool_call_message)


def _cfg(allowlist):
    return Config(allowlist=set(allowlist), telegram_token="TT", openrouter_key="KK",
                  model="moonshotai/kimi-k2.5", base_url=DEFAULT_BASE_URL,
                  system_prompt="SYS")


def _wire(fake, cfg, logbuf):
    return build_stack(cfg, fake, logbuf)


def _events(logbuf):
    return [json.loads(l) for l in logbuf.getvalue().splitlines()]


class AllowlistedFlowTest(unittest.TestCase):
    def test_allowlisted_message_gets_llm_reply(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="who plays?", update_id=5)]],
            llm_reply="Haaland captain")
        cfg = _cfg({42})
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, cfg, logbuf)

        poll_once(cfg, tg, llm, log, offset=0)

        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "Haaland captain"}])
        self.assertEqual(len(fake.llm_requests), 1)

    def test_logs_wake_prompt_and_reply(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_reply="a")
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0)

        events = _events(logbuf)
        kinds = [e["event"] for e in events]
        self.assertIn("wake", kinds)
        reply_ev = next(e for e in events if e["event"] == "reply")
        self.assertEqual(reply_ev["prompt"], "q")
        self.assertEqual(reply_ev["reply"], "a")


class ChatToolsTest(unittest.TestCase):
    def test_wired_tools_route_the_reply_through_run_agent(self):
        # A gaffer tool wired in: the model calls it, then answers; the final
        # assistant text is what reaches Telegram (spec §4).
        seen = []
        tool = Tool("lookup", "d", {"type": "object", "properties": {}, "required": []},
                    lambda **kw: seen.append(kw) or "TOOL-RESULT")
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="who's fit?", update_id=5)]],
            llm_replies=[tool_call_message("lookup", {}, "c1"), "final gaffer answer"])
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0, tools_factory=lambda: [tool])

        self.assertEqual(seen, [{}])                       # the tool ran
        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "final gaffer answer"}])
        self.assertEqual(len(fake.llm_requests), 2)        # tool turn + answer

    def test_chat_wake_spend_is_recorded_under_gaffer_chat(self):
        class RecLedger:
            def __init__(self):
                self.adds = []

            def add(self, usd, now=None, source="wake"):
                self.adds.append((usd, source))
        tool = Tool("noop", "d", {"type": "object", "properties": {}, "required": []},
                    lambda **kw: "x")
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_replies=["answer"])
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)
        ledger = RecLedger()

        poll_once(_cfg({42}), tg, llm, log, offset=0,
                  tools_factory=lambda: [tool], ledger=ledger)

        self.assertEqual(len(ledger.adds), 1)
        self.assertEqual(ledger.adds[0][1], "gaffer-chat")

    def test_chat_wake_shows_typing_and_relays_progress_notes(self):
        # Spec §3: the typing indicator runs through the model/tool phase and a
        # tool's start/done notes reach the chat BEFORE the final reply.
        tool = Tool("lookup", "d", {"type": "object", "properties": {}, "required": []},
                    lambda **kw: "TOOL-RESULT",
                    progress=lambda phase, args, result: (
                        "⏳ looking" if phase == "start" else "✅ looked"))
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_replies=[tool_call_message("lookup", {}, "c1", content="Checking."),
                         "final answer"])
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0, tools_factory=lambda: [tool])

        self.assertEqual([s["text"] for s in fake.sent],
                         ["Checking.", "⏳ looking", "✅ looked", "final answer"])
        self.assertIn({"chat_id": 42, "action": "typing"}, fake.actions)
        notes = [e for e in _events(logbuf) if e["event"] == "progress"]
        self.assertEqual([e["text"] for e in notes], ["Checking.", "⏳ looking", "✅ looked"])

    def test_a_machine_block_riding_with_a_tool_call_never_reaches_the_chat(self):
        # §3② "the block never reaches the human": think-aloud text is sent as
        # a progress note, so any fenced block in it is stripped first.
        tool = Tool("lookup", "d", {"type": "object", "properties": {}, "required": []},
                    lambda **kw: "TOOL-RESULT")
        aloud = "Leaning Salah.\n\n```plan\n{\"captain\": \"Salah\"}\n```\n\nChecking."
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_replies=[tool_call_message("lookup", {}, "c1", content=aloud), "final"])
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0, tools_factory=lambda: [tool])

        self.assertEqual([s["text"] for s in fake.sent], ["Leaning Salah.\n\nChecking.", "final"])

    def test_a_toolless_chat_wake_also_shows_typing(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_reply="plain")
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)
        poll_once(_cfg({42}), tg, llm, log, offset=0)
        self.assertIn({"chat_id": 42, "action": "typing"}, fake.actions)

    def test_a_capped_chat_gets_a_final_toolless_answer(self):
        # Spec §2: the chat wake passes the finish prompt, so a cap no longer
        # sends the placeholder line when there is evidence to answer from.
        tool = Tool("lookup", "d", {"type": "object", "properties": {}, "required": []},
                    lambda **kw: "TOOL-RESULT")
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_replies=[tool_call_message("lookup", {}, "c1"),
                         tool_call_message("lookup", {}, "c2"),
                         "best answer from what I have"])
        logbuf = io.StringIO()
        cfg = _cfg({42})
        cfg.chat_caps.turns = 2
        tg, llm, log = _wire(fake, cfg, logbuf)

        poll_once(cfg, tg, llm, log, offset=0, tools_factory=lambda: [tool])

        self.assertEqual(fake.sent[-1]["text"], "best answer from what I have")
        final_prompt = fake.llm_requests[-1]["messages"][-1]["content"]
        self.assertIn("no more tools", final_prompt)
        self.assertIn("cap_hit:turns", final_prompt)           # names the cap it hit
        self.assertIn("agent_cap_hit", [e["event"] for e in _events(logbuf)])

    def test_no_factory_is_byte_identical_single_completion(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_reply="plain")
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0)

        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "plain"}])
        self.assertEqual(len(fake.llm_requests), 1)
        self.assertNotIn("tools", fake.llm_requests[0])


class AllowlistDenialTest(unittest.TestCase):
    def test_non_allowlisted_sender_gets_no_action(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=999, text="hi", update_id=5)]],
            llm_reply="should not happen")
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        poll_once(_cfg({42}), tg, llm, log, offset=0)

        self.assertEqual(fake.sent, [])           # no reply
        self.assertEqual(fake.llm_requests, [])   # no token spend
        kinds = [e["event"] for e in _events(logbuf)]
        self.assertIn("drop", kinds)
        self.assertNotIn("wake", kinds)


class OffsetTest(unittest.TestCase):
    def test_offset_advances_past_processed_update(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]])
        logbuf = io.StringIO()
        tg, llm, log = _wire(fake, _cfg({42}), logbuf)

        new_offset = poll_once(_cfg({42}), tg, llm, log, offset=0)

        self.assertEqual(new_offset, 6)


if __name__ == "__main__":
    unittest.main()
