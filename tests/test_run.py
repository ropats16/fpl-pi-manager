"""The resident run() loop — startup log, message processing, error backoff."""

import io
import json
import unittest

from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import run
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message


def _cfg():
    return Config(allowlist={42}, telegram_token="TT", openrouter_key="KK",
                  model="m", base_url=DEFAULT_BASE_URL, system_prompt="SYS")


def _events(buf):
    return [json.loads(l) for l in buf.getvalue().splitlines()]


def _stop_after(n):
    state = {"i": 0}

    def cont():
        state["i"] += 1
        return state["i"] <= n
    return cont


class RunTest(unittest.TestCase):
    def test_logs_startup_and_processes_a_message(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="q", update_id=5)]],
            llm_reply="a")
        buf = io.StringIO()
        tg, llm, log = build_stack(_cfg(), fake, buf)

        run(_cfg(), tg, llm, log, should_continue=_stop_after(1), idle_sleep=0)

        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "a"}])
        self.assertIn("startup", [e["event"] for e in _events(buf)])

    def test_poll_error_is_logged_and_loop_survives(self):
        class Boom:
            def request(self, *a, **k):
                raise RuntimeError("net down")

        buf = io.StringIO()
        tg, llm, log = build_stack(_cfg(), Boom(), buf)

        # Two iterations both error; loop must log and keep going, not crash.
        run(_cfg(), tg, llm, log, should_continue=_stop_after(2), idle_sleep=0)

        kinds = [e["event"] for e in _events(buf)]
        self.assertIn("poll_error", kinds)


if __name__ == "__main__":
    unittest.main()
