"""`daemon build <N>` (spec §3): with no daemon.engineer module (PR 3) it is a
clean stub — fetch the issue body via the host, fail `engineer not wired`, ping
the chats, exit 1. Bad invocation is exit 2; an unfetchable issue is exit 1."""

import io
import os
import tempfile
import unittest

from daemon.__main__ import run_build_cmd
from daemon.plan import ApprovalStore
from daemon.propose import FakeGitHost
from tests.fakes import FakeTransport

ENV = {"GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "T",
       "OPENROUTER_API_KEY": "K"}


class RunBuildCmdTest(unittest.TestCase):
    def test_engineer_not_wired_is_a_clean_stub_failure(self):
        host = FakeGitHost()
        n, _ = host.open_issue("TC window", "the spec body", labels=["gaffer", "build"])
        fake = FakeTransport()
        out = io.StringIO()
        rc = run_build_cmd([str(n)], env=ENV, transport=fake, out=out, host=host)
        self.assertEqual(rc, 1)
        self.assertIn("status=error", out.getvalue())
        self.assertIn("engineer not wired", out.getvalue())
        # A Telegram receipt went to the allowlisted chat.
        self.assertEqual(len(fake.sent), 1)
        self.assertIn(f"build #{n} failed", fake.sent[0]["text"])
        self.assertIn("engineer not wired", fake.sent[0]["text"])

    def test_bad_invocation_is_exit_2(self):
        out = io.StringIO()
        self.assertEqual(run_build_cmd([], env=ENV, transport=FakeTransport(),
                                       out=out, host=FakeGitHost()), 2)
        self.assertEqual(run_build_cmd(["notanumber"], env=ENV,
                                       transport=FakeTransport(), out=out,
                                       host=FakeGitHost()), 2)

    def test_running_build_is_cleared_on_exit(self):
        # The gate set running_build before spawning us; the child clears it on
        # the way out (success or failure) so the gate is not stuck refusing the
        # next build even with no chat in between.
        tmp = tempfile.mkdtemp(prefix="build-cmd-")
        env = dict(ENV, GAFFER_APPROVAL_STATE_PATH=os.path.join(tmp, "approval.json"))
        store = ApprovalStore(env["GAFFER_APPROVAL_STATE_PATH"])
        host = FakeGitHost()
        n, _ = host.open_issue("T", "body")
        store.run_build({"issue": n, "pid": 4321, "started_at": "x"})
        run_build_cmd([str(n)], env=env, transport=FakeTransport(),
                      out=io.StringIO(), host=host)          # stub-fails
        self.assertIsNone(ApprovalStore(env["GAFFER_APPROVAL_STATE_PATH"])
                          .load().running_build)

    def test_unfetchable_issue_is_exit_1(self):
        out = io.StringIO()
        rc = run_build_cmd(["99"], env=ENV, transport=FakeTransport(), out=out,
                           host=FakeGitHost())
        self.assertEqual(rc, 1)
        self.assertIn("cannot fetch issue #99", out.getvalue())


if __name__ == "__main__":
    unittest.main()
