"""`python3 -m daemon selftest` — offline full message->reply loop, zero network.

Mirrors run_pipeline.sh's offline selftest idiom for the network edge.
"""

import io
import unittest

from daemon.__main__ import run_selftest


class SelftestTest(unittest.TestCase):
    def test_drives_full_loop_offline_and_returns_zero(self):
        out = io.StringIO()
        rc = run_selftest(out=out)
        self.assertEqual(rc, 0)

    def test_selftest_output_shows_a_reply_was_produced(self):
        out = io.StringIO()
        run_selftest(out=out)
        self.assertIn("reply", out.getvalue())

    def test_selftest_demonstrates_a_grounded_prompt(self):
        # The shipped demo assembles the real workspace + season state and checks
        # a squad fact reached the model — the #16 acceptance demo, offline.
        # Assert the demo's own grounding check passed (not the canned reply text).
        out = io.StringIO()
        run_selftest(out=out)
        self.assertIn("grounded=True", out.getvalue())
        self.assertIn("no-raw-json=True", out.getvalue())


if __name__ == "__main__":
    unittest.main()
