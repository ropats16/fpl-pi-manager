"""Structured JSON logging with a test-asserted secret-redaction invariant (#10 §3)."""

import io
import json
import unittest

from daemon.logging_setup import StructuredLogger


class StructuredLoggerTest(unittest.TestCase):
    def test_emits_one_json_line_per_event(self):
        buf = io.StringIO()
        log = StructuredLogger(stream=buf, secrets=[])

        log.event("wake", from_id=42, text="hi")

        line = buf.getvalue().strip()
        rec = json.loads(line)
        self.assertEqual(rec["event"], "wake")
        self.assertEqual(rec["from_id"], 42)
        self.assertEqual(rec["text"], "hi")
        self.assertIn("ts", rec)

    def test_redacts_secret_values_anywhere_in_fields(self):
        buf = io.StringIO()
        log = StructuredLogger(stream=buf, secrets=["SUPERSECRET", "botTOKEN"])

        log.event("reply", prompt="use SUPERSECRET now", note="botTOKEN")

        out = buf.getvalue()
        self.assertNotIn("SUPERSECRET", out)
        self.assertNotIn("botTOKEN", out)
        self.assertIn("[REDACTED]", out)

    def test_ignores_empty_secrets(self):
        buf = io.StringIO()
        log = StructuredLogger(stream=buf, secrets=["", None])

        log.event("wake", text="hello")

        self.assertIn("hello", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
