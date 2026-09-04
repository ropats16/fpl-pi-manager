"""Ledger — MTD estimated-spend rails (#56/#51 ④): persist, rollover, mode."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.ledger import Ledger


def _clock(dt):
    return lambda: dt


SEP = datetime(2026, 9, 4, 4, 30, 0, tzinfo=timezone.utc)
AUG = datetime(2026, 8, 31, 23, 0, 0, tzinfo=timezone.utc)


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "ledger.json")

    def test_add_persists_and_reads_back(self):
        led = Ledger(self.path, clock=_clock(SEP))
        self.assertEqual(led.add(1.25), 1.25)
        self.assertAlmostEqual(led.add(0.75), 2.0)
        # a fresh instance reads the same file
        self.assertAlmostEqual(Ledger(self.path, clock=_clock(SEP)).total(), 2.0)

    def test_month_key(self):
        self.assertEqual(Ledger(self.path).month_key(now=SEP), "2026-09")

    def test_month_rollover_on_add(self):
        led = Ledger(self.path, clock=_clock(AUG))
        led.add(3.0)  # lands in 2026-08
        # adding in September resets to just this wake's spend
        self.assertAlmostEqual(led.add(0.5, now=SEP), 0.5)
        self.assertAlmostEqual(led.total(now=SEP), 0.5)

    def test_stored_other_month_reads_as_zero(self):
        Ledger(self.path, clock=_clock(AUG)).add(3.0)
        self.assertEqual(Ledger(self.path, clock=_clock(SEP)).total(), 0.0)

    def test_corrupt_file_treated_as_empty_then_overwritten(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        led = Ledger(self.path, clock=_clock(SEP))
        self.assertEqual(led.total(), 0.0)
        self.assertAlmostEqual(led.add(1.0), 1.0)
        with open(self.path) as f:
            self.assertEqual(json.load(f)["month"], "2026-09")

    def test_missing_file_is_zero(self):
        self.assertEqual(Ledger(self.path, clock=_clock(SEP)).total(), 0.0)

    def test_negative_and_zero_add_ignored(self):
        led = Ledger(self.path, clock=_clock(SEP))
        led.add(2.0)
        self.assertAlmostEqual(led.add(0), 2.0)
        self.assertAlmostEqual(led.add(-5), 2.0)
        self.assertAlmostEqual(led.total(), 2.0)

    def test_mode_thresholds_at_boundaries(self):
        led = Ledger(self.path, clock=_clock(SEP))
        led.add(3.99)
        self.assertEqual(led.mode(), "full")
        led.add(0.01)  # 4.00
        self.assertEqual(led.mode(), "search_off")
        led.add(0.75)  # 4.75
        self.assertEqual(led.mode(), "helpers_off")

    def test_custom_thresholds(self):
        led = Ledger(self.path, thresholds={"search_off_usd": 1.0,
                                             "helpers_off_usd": 2.0},
                     clock=_clock(SEP))
        led.add(1.5)
        self.assertEqual(led.mode(), "search_off")

    def test_unwritable_path_returns_total_without_raising(self):
        # a file where a directory is expected -> makedirs/replace fail
        blocker = os.path.join(self.dir, "blocker")
        with open(blocker, "w") as f:
            f.write("x")
        bad = os.path.join(blocker, "ledger.json")
        led = Ledger(bad, clock=_clock(SEP))
        self.assertAlmostEqual(led.add(1.0), 1.0)  # in-memory total, no raise
        self.assertEqual(led.total(), 0.0)         # nothing persisted

    def test_snapshot_shape(self):
        led = Ledger(self.path, clock=_clock(SEP))
        led.add(4.0)
        snap = led.snapshot()
        self.assertEqual(set(snap), {"month", "total_usd", "mode",
                                     "search_off_usd", "helpers_off_usd"})
        self.assertEqual(snap["month"], "2026-09")
        self.assertEqual(snap["total_usd"], 4.0)
        self.assertEqual(snap["mode"], "search_off")
        self.assertEqual(snap["search_off_usd"], 4.0)
        self.assertEqual(snap["helpers_off_usd"], 4.75)

    def test_source_arg_accepted(self):
        led = Ledger(self.path, clock=_clock(SEP))
        self.assertAlmostEqual(led.add(1.0, source="selftest"), 1.0)

    def test_null_ledger_via_none_path(self):
        led = Ledger(None)
        self.assertEqual(led.total(), 0.0)
        self.assertEqual(led.add(9.0), 0.0)   # never persists, never accumulates
        self.assertEqual(led.total(), 0.0)
        self.assertEqual(led.mode(), "full")
        snap = led.snapshot()
        self.assertEqual(snap["mode"], "full")
        self.assertEqual(snap["total_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
