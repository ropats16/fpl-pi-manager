"""The two trigger surfaces of the #55 propose path through the chat loop:
`propose role: <name>` in chat, and a reply that carries a ```propose block —
asserted at the edges (user turn sent to the model, Telegram text, the fake
runner's record). The approval `yes` gate is untouched."""

import io
import json
import os
import tempfile
import unittest

from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.plan import ApprovalGate, ApprovalStore
from daemon.propose import FakeGitHost, GhGitHost, make_proposer
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message

ROLE_MD = "# Chips analyst\n\nOwn chip timing.\n"
BLOCK = ("On it.\n\n```propose\nname: Chips analyst\nevidence: no seat covers chips\n"
         "---\n" + ROLE_MD + "```")
PLAN = {"transfers_in": [], "transfers_out": [], "hits": 0, "starting_xi": ["Raya"],
        "captain": "Haaland", "vice": "Salah", "chip": None, "contingencies": []}


def _cfg():
    return Config(allowlist={42}, telegram_token="TT", openrouter_key="KK",
                  model="m", base_url=DEFAULT_BASE_URL, system_prompt="static",
                  github_token="ghp_SECRET")


class ProposeLoopTest(unittest.TestCase):
    def setUp(self):
        self.log = io.StringIO()
        self.host = FakeGitHost()

    def run_text(self, text, llm_reply, proposer=True, approvals=None):
        fake = FakeTransport(updates_batches=[[private_message(from_id=42, text=text)]],
                             llm_reply=llm_reply)
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, self.log)
        poll_once(cfg, tg, llm, log, 0, approvals=approvals,
                  proposer=make_proposer(self.host, log) if proposer else None)
        return fake

    def test_chat_request_carries_the_block_format_and_opens_the_pr(self):
        fake = self.run_text("propose role: chips analyst", BLOCK)
        user = fake.llm_requests[0]["messages"][-1]["content"]
        self.assertTrue(user.startswith("propose role: chips analyst"))
        self.assertIn("```propose", user)
        (pr,) = self.host.proposals
        self.assertEqual(pr["branch"], "gaffer/chips-analyst")
        self.assertEqual(sorted(pr["files"]), ["agent/roles/chips-analyst.evidence.md",
                                               "agent/roles/chips-analyst.md"])
        sent = fake.sent[0]["text"]
        self.assertNotIn("```propose", sent)
        self.assertIn("https://github.com/x/y/pull/1", sent)
        self.assertIn("On it.", sent)
        self.assertNotIn("ghp_SECRET", self.log.getvalue())

    def test_plain_chat_does_not_get_the_hint(self):
        fake = self.run_text("how's my team?", "fine")
        self.assertNotIn("```propose", fake.llm_requests[0]["messages"][-1]["content"])
        self.assertEqual(self.host.proposals, [])

    def test_block_naming_a_tier1_path_is_refused_in_the_reply(self):
        bad = BLOCK.replace("evidence:", "path: daemon/evil.py\nevidence:")
        fake = self.run_text("propose role: chips analyst", bad)
        self.assertEqual(self.host.proposals, [])
        self.assertIn("refused", fake.sent[0]["text"])
        self.assertIn("daemon/evil.py", fake.sent[0]["text"])
        kinds = [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]
        self.assertIn("propose_refused", kinds)

    def test_no_token_answers_without_a_model_call(self):
        fake = self.run_text("propose role: chips analyst", BLOCK, proposer=False)
        self.assertEqual(fake.llm_requests, [])
        self.assertIn("GitHub token", fake.sent[0]["text"])
        self.assertEqual(self.host.proposals, [])
        self.assertIsNone(make_proposer(None, None))

    def test_unrequested_block_in_plain_chat_is_dropped_not_a_pr(self):
        fake = self.run_text("how's my team?", BLOCK)
        self.assertEqual(self.host.proposals, [])
        sent = fake.sent[0]["text"]
        self.assertNotIn("name: Chips analyst", sent)              # stripped
        self.assertIn("dropped", sent)
        kinds = [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]
        self.assertIn("propose_ignored", kinds)

    def test_the_requested_name_wins_over_the_models_header(self):
        fake = self.run_text("propose role: Set-piece analyst", BLOCK)
        (pr,) = self.host.proposals
        self.assertEqual(pr["branch"], "gaffer/set-piece-analyst")
        self.assertIn("agent/roles/set-piece-analyst.md", pr["files"])
        self.assertIn("Set-piece analyst", pr["title"])
        self.assertIn("set-piece analyst", fake.sent[0]["text"].casefold())

    def test_token_never_reaches_model_context_telegram_or_log_even_when_git_echoes_it(self):
        # The real runner over a subprocess fake whose push FAILS and echoes the
        # credential in stderr (what GIT_TRACE-style leaks look like).
        def run(argv, env, cwd):
            if "push" in argv:
                return 1, "", f"fatal: auth failed for token ghp_SECRET in {argv[-2]}"
            return 0, "", ""
        host = GhGitHost(tempfile.mkdtemp(prefix="repo-"), "ghp_SECRET", run=run)
        fake = FakeTransport(updates_batches=[[private_message(from_id=42,
                                                               text="propose role: chips analyst")]],
                             llm_reply=BLOCK)
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, self.log)
        poll_once(cfg, tg, llm, log, 0, proposer=make_proposer(host, log))
        self.assertIn("failed", fake.sent[0]["text"])
        self.assertNotIn("ghp_SECRET", fake.sent[0]["text"])
        self.assertNotIn("ghp_SECRET", json.dumps(fake.llm_requests))
        self.assertNotIn("ghp_SECRET", self.log.getvalue())

    def test_yes_still_approves_in_daemon_code_with_no_llm_call(self):
        tmp = tempfile.mkdtemp(prefix="propose-loop-")
        store = ApprovalStore(os.path.join(tmp, "approval-state.json"))
        store.set_pending(2, PLAN)
        fake = self.run_text("yes", "never", approvals=ApprovalGate(store))
        self.assertEqual(fake.llm_requests, [])
        self.assertIn("approved", fake.sent[0]["text"])
        self.assertEqual(self.host.proposals, [])


if __name__ == "__main__":
    unittest.main()
