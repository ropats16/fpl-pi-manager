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

    def test_selftest_demonstrates_one_analyst_tool_loop_offline(self):
        # The #54 acceptance demo: report path, fetch/search counts, cost
        # estimate, and the two boundary facts (one request for a repeated URL,
        # off-allowlist refused before the wire) all printed, and PASS.
        out = io.StringIO()
        rc = run_selftest(out=out)
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("helper: role=availability", text)
        self.assertIn("status=ok", text)
        self.assertIn("report=", text)
        self.assertIn("fetches=3 requests=1 searches=1", text)
        self.assertIn("cost=$0.0", text)
        self.assertIn("one-request=True off-allowlist-refused=True", text)
        self.assertIn("helper=PASS", text)
        # #55: the propose demo — branch, two files, link in the reply, ACL.
        self.assertIn("propose: branch=gaffer/chips-analyst files=2", text)
        self.assertIn("tier1-refused=True", text)
        self.assertIn("propose=PASS", text)
        self.assertIn('"event": "fetch_refused"', text)
        # #56: the draft fan-out demo — six reports, the run order, the AM
        # counter in the Dissent line, prompt under the cap, no rail crossed.
        self.assertIn("fanout: gw=4 reports=6 order=availability>fixtures>quality>market>chips>am",
                      text)
        self.assertIn("am-dissent=True reports-inlined=True", text)
        self.assertIn("rails=none", text)
        self.assertIn("mode=full", text)
        self.assertIn("fanout=PASS", text)
        # #57: the daily Scout demo — two sweeps into one log, newest first,
        # the second one URGENT and flagged.
        self.assertIn("scout: gw=4 entries=2 newest-first=True urgent=True", text)
        self.assertIn("scout=PASS", text)

    def test_selftest_helper_report_never_lands_in_the_repo(self):
        run_selftest(out=io.StringIO())
        self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, "agent", "reports",
                                                     "gw04", "availability.md")))

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
