"""`python3 -m daemon selftest` — offline full message->reply loop, zero network.

Mirrors run_pipeline.sh's offline selftest idiom for the network edge.
"""

import hashlib
import io
import os
import unittest

from daemon.__main__ import REPO_ROOT, run_selftest

LEARNINGS = os.path.join(REPO_ROOT, "agent", "memory", "learnings.md")


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

    def test_selftest_demonstrates_the_learnings_loop(self):
        # The #20 acceptance demo, offline: turn 1 records a lesson, turn 2's
        # prompt recalls it, and the machine block never reached the human.
        out = io.StringIO()
        run_selftest(out=out)
        self.assertIn("recorded=2", out.getvalue())
        self.assertIn("recalled=True", out.getvalue())
        self.assertIn("block-stripped=True", out.getvalue())

    def test_selftest_never_writes_the_committed_learnings_log(self):
        # The diary is append-only repo content; a demo run must not grow it.
        # The selftest works on a tempdir copy — this is the guard on that.
        def digest():
            with open(LEARNINGS, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        before = digest()
        run_selftest(out=io.StringIO())
        self.assertEqual(digest(), before)


if __name__ == "__main__":
    unittest.main()
