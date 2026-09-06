"""`daemon build <N>` (spec §3/§4): the command wires the issue body into
`daemon.engineer.run_build` and turns its BuildResult into the exact Telegram
receipt, the summary line and the exit code. `run_build` is injected so the
receipts/exit codes are asserted without a real build (the suite never forks a
real subprocess); the engineer's own seams are in tests/test_engineer.py."""

import io
import os
import tempfile
import unittest

from daemon import engineer
from daemon.__main__ import run_build_cmd
from daemon.plan import ApprovalStore
from daemon.propose import FakeGitHost
from tests.fakes import FakeTransport

ENV = {"GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "T",
       "OPENROUTER_API_KEY": "K"}


def _fake_build(result):
    def run_build(issue, host, llm, model, caps, fix_turns, data_dir, repo_rules,
                  logger, clock=None, test_runner=None):
        return result
    return run_build


class RunBuildCmdTest(unittest.TestCase):
    def _run(self, result, host=None):
        host = FakeGitHost() if host is None else host
        n, _ = host.open_issue("TC window", "the spec body", labels=["gaffer", "build"])
        fake = FakeTransport()
        out = io.StringIO()
        rc = run_build_cmd([str(n)], env=ENV, transport=fake, out=out, host=host,
                           run_build=_fake_build(result))
        return rc, out.getvalue(), fake.sent, n

    def test_green_sends_pr_receipt_and_exits_0(self):
        res = engineer.BuildResult(status="green", pr_url="https://x/pull/5",
                                   turns=6, cost_usd=0.02)
        rc, out, sent, n = self._run(res)
        self.assertEqual(rc, 0)
        self.assertIn("status=green", out)
        self.assertIn("pr=https://x/pull/5", out)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["text"], f"✅ build #{n} → PR https://x/pull/5")

    def test_red_sends_draft_receipt_and_exits_0(self):
        res = engineer.BuildResult(status="red", pr_url="https://x/pull/6",
                                   turns=9, cost_usd=0.05)
        rc, out, sent, n = self._run(res)
        self.assertEqual(rc, 0)
        self.assertIn("status=red", out)
        self.assertEqual(sent[0]["text"], f"🟥 build #{n} red → draft PR https://x/pull/6")

    def test_error_sends_failure_receipt_and_exits_1(self):
        res = engineer.BuildResult(status="error", reason="no changes")
        rc, out, sent, n = self._run(res)
        self.assertEqual(rc, 1)
        self.assertIn("status=error", out)
        self.assertIn("reason=no changes", out)
        self.assertEqual(sent[0]["text"], f"❌ build #{n} failed: no changes")

    def test_bad_invocation_is_exit_2(self):
        out = io.StringIO()
        self.assertEqual(run_build_cmd([], env=ENV, transport=FakeTransport(),
                                       out=out, host=FakeGitHost()), 2)
        self.assertEqual(run_build_cmd(["notanumber"], env=ENV,
                                       transport=FakeTransport(), out=out,
                                       host=FakeGitHost()), 2)

    def test_unfetchable_issue_is_exit_1(self):
        out = io.StringIO()
        rc = run_build_cmd(["99"], env=ENV, transport=FakeTransport(), out=out,
                           host=FakeGitHost())
        self.assertEqual(rc, 1)
        self.assertIn("cannot fetch issue #99", out.getvalue())

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
        run_build_cmd([str(n)], env=env, transport=FakeTransport(), out=io.StringIO(),
                      host=host, run_build=_fake_build(
                          engineer.BuildResult(status="green", pr_url="u")))
        self.assertIsNone(ApprovalStore(env["GAFFER_APPROVAL_STATE_PATH"])
                          .load().running_build)


if __name__ == "__main__":
    unittest.main()
