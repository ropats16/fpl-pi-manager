"""Month-to-date estimated-spend ledger (#56, #51 ④).

A tiny advisory json file that accumulates estimated USD spend across wakes so
the fan-out can throttle itself as the month's bill climbs: at `search_off_usd`
helpers keep running but lose web search, at `helpers_off_usd` the helpers are
skipped entirely (the gaffer + AM still run). The month rolls over on read — a
stored prior month reads as 0.0 — so no cron reset is needed.

The ledger is advisory, never load-bearing: a missing, corrupt, or unreadable
file is treated as empty (total 0.0) and never raises, and a write failure is
swallowed too — a wake must never die because the spend file could not be
written. `Ledger(None)` is the null ledger for callers with no path wired: it
never persists, always totals 0.0, and always reports mode "full".

File shape (kept small — no per-call history):
    {"month": "2026-09", "total_usd": 1.2345,
     "updated": "2026-09-04T04:30:00Z", "entries": 3}
"""

import json
import os
from datetime import datetime, timezone

from daemon.config import DEFAULT_LEDGER_THRESHOLDS
from daemon.plan import _atomic_write_json


class Ledger:
    """MTD estimated-spend ledger. `path=None` -> null ledger (never persists).
    `clock()` returns an aware UTC datetime; a per-call `now` overrides it."""

    def __init__(self, path, thresholds=None, clock=None):
        self.path = path
        self.thresholds = (dict(DEFAULT_LEDGER_THRESHOLDS) if thresholds is None
                           else dict(thresholds))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self, now):
        return now if now is not None else self._clock()

    def month_key(self, now=None):
        """The "YYYY-MM" bucket for `now` (or the clock)."""
        return self._now(now).strftime("%Y-%m")

    def _read(self):
        """The stored record, or None if absent/corrupt/unreadable (advisory)."""
        if self.path is None:
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return None

    def total(self, now=None):
        """MTD USD for the current month. A stored prior month reads as 0.0
        (rollover on read); missing/corrupt reads as 0.0."""
        data = self._read()
        if not data or data.get("month") != self.month_key(now):
            return 0.0
        try:
            return float(data.get("total_usd", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def add(self, usd, now=None, source="wake"):
        """Add `usd` (<=0 ignored) to the MTD total and persist atomically;
        return the new MTD total. Rolls the month over when the stored month
        differs (resets to just this wake's spend). Null ledger / write failure
        returns the in-memory total without raising."""
        try:
            usd = float(usd)
        except (TypeError, ValueError):
            usd = 0.0
        month = self.month_key(now)
        base = self.total(now)  # 0.0 on rollover / missing / corrupt
        if usd <= 0:
            return base
        data = self._read()
        entries = 0
        if data and data.get("month") == month:
            try:
                entries = int(data.get("entries", 0))
            except (TypeError, ValueError):
                entries = 0
        new_total = base + usd
        if self.path is None:
            return 0.0  # null ledger never persists nor accumulates
        record = {
            "month": month,
            "total_usd": round(new_total, 10),
            "updated": self._now(now).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "entries": entries + 1,
        }
        try:
            _atomic_write_json(self.path, record)
        except OSError:
            pass  # advisory: a wake never dies on the spend file
        return new_total

    def mode(self, now=None):
        """"helpers_off" >= helpers_off_usd, else "search_off" >= search_off_usd,
        else "full"."""
        t = self.total(now)
        if t >= self.thresholds["helpers_off_usd"]:
            return "helpers_off"
        if t >= self.thresholds["search_off_usd"]:
            return "search_off"
        return "full"

    def snapshot(self, now=None):
        """A flat dict for logs / selftest."""
        return {
            "month": self.month_key(now),
            "total_usd": round(self.total(now), 4),
            "mode": self.mode(now),
            "search_off_usd": self.thresholds["search_off_usd"],
            "helpers_off_usd": self.thresholds["helpers_off_usd"],
        }
