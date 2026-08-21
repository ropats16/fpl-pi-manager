"""Structured JSON logging with a hard secret-redaction guard.

One JSON object per line (jsonl) so wakes, prompts and replies are greppable and
machine-auditable. Redaction is a mechanism, not a prompt: every configured
secret string is scrubbed from the serialized record before it is written, so a
credential can never reach the log even if it lands in a field by mistake
(#10 §3 — redaction is a test-asserted invariant).
"""

import json
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StructuredLogger:
    def __init__(self, stream, secrets=(), clock=_now_iso):
        self._stream = stream
        self._secrets = [s for s in secrets if s]
        self._clock = clock

    def event(self, event, **fields):
        rec = {"ts": self._clock(), "event": event}
        rec.update(fields)
        line = json.dumps(rec, ensure_ascii=False, default=str)
        for secret in self._secrets:
            line = line.replace(secret, "[REDACTED]")
        self._stream.write(line + "\n")
        self._stream.flush()
