"""`daemon propose "<name>" --role <file.md> [--evidence ...]` (#55): a drafted
role file on disk through the one propose path + a Telegram ping."""

import io
import json
import os
import tempfile
import unittest

from daemon.__main__ import run_propose_cmd
from daemon.propose import FakeGitHost
from tests.fakes import FakeTransport


class ProposeCmdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="propose-cmd-")
        self.role = os.path.join(self.tmp, "chips.md")
        with open(self.role, "w") as f:
            f.write("# Chips analyst\n\nOwn chip timing.\n")
        self.env = {"GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "TT",
                    "OPENROUTER_API_KEY": "KK", "GITHUB_TOKEN": "ghp_SECRET"}
        self.out = io.StringIO()
        self.host = FakeGitHost()

    def _run(self, args, host="fake"):
        fake = FakeTransport()
        rc = run_propose_cmd(args, env=self.env, transport=fake, out=self.out,
                             host=self.host if host == "fake" else host)
        return rc, fake

    def test_opens_the_pr_pings_telegram_and_prints_the_line(self):
        rc, fake = self._run(["Chips analyst", "--role", self.role,
                              "--evidence", "cap_hit on availability 3 GWs running"])
        self.assertEqual(rc, 0)
        (pr,) = self.host.proposals
        self.assertEqual(pr["branch"], "gaffer/chips-analyst")
        self.assertIn("cap_hit", pr["body"])
        self.assertIn("trigger: cli", pr["files"]["agent/roles/chips-analyst.evidence.md"])
        self.assertEqual(fake.sent[0]["chat_id"], 42)
        self.assertIn("https://github.com/x/y/pull/1", fake.sent[0]["text"])
        line = [l for l in self.out.getvalue().splitlines() if l.startswith("propose:")][0]
        self.assertIn("status=ok", line)
        self.assertIn("url=https://github.com/x/y/pull/1", line)
        self.assertNotIn("ghp_SECRET", self.out.getvalue())

    def test_bad_invocation_is_exit_2_and_touches_nothing(self):
        self.assertEqual(self._run([])[0], 2)
        self.assertEqual(self._run(["x", "--role"])[0], 2)
        self.assertEqual(self._run(["x", "--role", "/nope/missing.md"])[0], 2)
        self.assertEqual(self.host.proposals, [])

    def test_no_token_is_a_reported_failure_not_a_crash(self):
        del self.env["GITHUB_TOKEN"]
        rc, fake = self._run(["Chips analyst", "--role", self.role], host=None)
        self.assertEqual(rc, 0)
        self.assertIn("status=failed", self.out.getvalue())
        self.assertIn("token", fake.sent[0]["text"])
        events = [json.loads(l) for l in self.out.getvalue().splitlines() if l.startswith("{")]
        self.assertIn("propose_failed", [e["event"] for e in events])


if __name__ == "__main__":
    unittest.main()
