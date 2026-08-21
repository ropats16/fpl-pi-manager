"""The wake->reply loop, driven end-to-end through the faked HTTP edge.

Real Telegram + LLM client code runs; only daemon.http.Transport is faked, so
these are the HTTP-edge acceptance tests for #15.
"""

import io
import json
import unittest

from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message


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
