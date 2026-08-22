"""`python3 -m daemon notify "<text>"` — a proactive push to the allowlist,
used by the deploy path to report a reload / a blocked deploy. Reuses the
daemon's own Telegram client so send logic isn't duplicated."""

import io
import unittest

from daemon.__main__ import run_notify
from daemon.http import FakeTransport


def _env(ids="42"):
    # No OPENROUTER_API_KEY: the deploy path sends notices without ever touching
    # the LLM key (least privilege — the pull unit loads only telegram-token).
    return {"GAFFER_ALLOWLIST_USER_IDS": ids, "TELEGRAM_BOT_TOKEN": "TT"}


class NotifyTest(unittest.TestCase):
    def test_pushes_the_message_to_each_allowlisted_chat(self):
        fake = FakeTransport()
        rc = run_notify(["deployed abc123 — https://gh/pull/42"], env=_env("42 43"),
                        transport=fake, out=io.StringIO())
        self.assertEqual(rc, 0)
        self.assertEqual(fake.sent, [
            {"chat_id": 42, "text": "deployed abc123 — https://gh/pull/42"},
            {"chat_id": 43, "text": "deployed abc123 — https://gh/pull/42"},
        ])

    def test_empty_message_is_refused_without_sending(self):
        fake = FakeTransport()
        rc = run_notify(["   "], env=_env(), transport=fake, out=io.StringIO())
        self.assertEqual(rc, 2)
        self.assertEqual(fake.sent, [])


if __name__ == "__main__":
    unittest.main()
