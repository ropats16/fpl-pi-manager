"""Commissioning builds through the chat loop (spec §3): a ```build block in the
reply opens an issue and queues; `build #N` spawns via an injected spawner;
`cancel build` clears; the BUILD_HINT rides an explicit `build:` message; and a
bare `yes` still only ever approves a plan. Asserted at the edges — the user turn
sent to the model, Telegram text, the injected spawner and the git host."""

import io
import json
import os
import tempfile
import unittest

from daemon.build import BuildGate
from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.plan import ApprovalGate, ApprovalStore
from daemon.propose import FakeGitHost
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message

SPEC = "Goal: TC window model.\nFiles: fpl_tc_window.py\nTests: test_tc.py"
BLOCK = ("On it.\n\n```build\nticket: new\ntitle: TC window model\n---\n"
         + SPEC + "\n```")
PLAN = {"transfers_in": [], "transfers_out": [], "hits": 0, "starting_xi": ["Raya"],
        "captain": "Haaland", "vice": "Salah", "chip": None, "contingencies": []}


def _cfg():
    return Config(allowlist={42}, telegram_token="TT", openrouter_key="KK",
                  model="m", base_url=DEFAULT_BASE_URL, system_prompt="static")


class BuildLoopTest(unittest.TestCase):
    def setUp(self):
        self.log = io.StringIO()
        self.tmp = tempfile.mkdtemp(prefix="build-loop-")
        self.store = ApprovalStore(os.path.join(self.tmp, "approval-state.json"))
        self.host = FakeGitHost()
        self.spawned = []

    def _builds(self, host="default"):
        host = self.host if host == "default" else host
        return BuildGate(self.store, host, self.tmp,
                         spawn=lambda n, d: (self.spawned.append((n, d)), 4321)[1])

    def _run(self, text, llm_reply, builds=None, approvals=None):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text=text)]],
            llm_reply=llm_reply)
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, self.log)
        poll_once(cfg, tg, llm, log, 0, approvals=approvals, builds=builds)
        return fake

    def _events(self):
        return [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]

    def test_build_block_opens_issue_queues_and_strips(self):
        fake = self._run("build: add a TC model", BLOCK, builds=self._builds())
        (issue,) = self.host.issues.values()
        self.assertEqual(issue["labels"], ["gaffer", "build"])
        sent = fake.sent[0]["text"]
        self.assertNotIn("```build", sent)                 # stripped
        self.assertIn("On it.", sent)
        self.assertIn('build #1 queued', sent)
        self.assertEqual(self.store.load().pending_build["issue"], 1)

    def test_explicit_build_request_gets_the_hint(self):
        fake = self._run("build: a TC window model", "sure", builds=self._builds())
        user = fake.llm_requests[0]["messages"][-1]["content"]
        self.assertIn("```build", user)

    def test_plain_chat_does_not_get_the_hint(self):
        fake = self._run("how's my team?", "fine", builds=self._builds())
        self.assertNotIn("```build", fake.llm_requests[0]["messages"][-1]["content"])

    def test_no_host_drops_the_block_with_a_fixed_line(self):
        fake = self._run("build: x", BLOCK, builds=self._builds(host=None))
        sent = fake.sent[0]["text"]
        self.assertNotIn("```build", sent)
        self.assertIn("GitHub token", sent)
        self.assertIsNone(self.store.load().pending_build)

    def test_build_start_token_spawns_with_no_model_call(self):
        self.store.queue_build({"issue": 1, "title": "t", "spec": "s", "queued_at": "x"})
        fake = self._run("build #1", "never", builds=self._builds())
        self.assertEqual(fake.llm_requests, [])            # no token spend
        self.assertEqual(self.spawned, [(1, self.tmp)])
        self.assertIn("build #1 started", fake.sent[0]["text"])
        self.assertEqual(self.store.load().running_build["pid"], 4321)

    def test_bare_build_starts_the_single_pending(self):
        self.store.queue_build({"issue": 7, "title": "t", "spec": "s", "queued_at": "x"})
        fake = self._run("build", "never", builds=self._builds())
        self.assertEqual(self.spawned, [(7, self.tmp)])
        self.assertIn("build #7 started", fake.sent[0]["text"])

    def test_build_while_running_refuses(self):
        self.store.run_build({"issue": 3, "pid": os.getpid(), "started_at": "x"})
        fake = self._run("build #3", "never", builds=self._builds())
        self.assertEqual(self.spawned, [])
        self.assertIn("running — wait", fake.sent[0]["text"])

    def test_cancel_build_clears_pending(self):
        self.store.queue_build({"issue": 2, "title": "t", "spec": "s", "queued_at": "x"})
        fake = self._run("cancel build", "never", builds=self._builds())
        self.assertEqual(fake.llm_requests, [])
        self.assertIn("build #2 cancelled", fake.sent[0]["text"])
        self.assertIsNone(self.store.load().pending_build)

    def test_build_token_with_nothing_pending_falls_through_to_model(self):
        fake = self._run("build", "just chatting", builds=self._builds())
        self.assertEqual(len(fake.llm_requests), 1)        # reached the model
        self.assertEqual(fake.sent[0]["text"], "just chatting")
        self.assertEqual(self.spawned, [])

    def test_bare_yes_only_approves_a_plan_never_a_build(self):
        # A pending build AND a pending plan: `yes` must approve the plan and
        # leave the build untouched (build approval is never a bare yes).
        self.store.set_pending(2, PLAN)
        self.store.queue_build({"issue": 9, "title": "t", "spec": "s", "queued_at": "x"})
        approvals = ApprovalGate(self.store)
        fake = self._run("yes", "never", builds=self._builds(), approvals=approvals)
        self.assertEqual(fake.llm_requests, [])
        self.assertIn("approved", fake.sent[0]["text"])
        self.assertEqual(self.spawned, [])                 # no build spawned
        st = self.store.load()
        self.assertEqual(st.phase, "approved")
        self.assertEqual(st.pending_build["issue"], 9)     # build still queued


if __name__ == "__main__":
    unittest.main()
