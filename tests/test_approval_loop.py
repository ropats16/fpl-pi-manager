"""HTTP-edge harness for the #18 approval reply loop (style of test_assembly_loop).

Drives the real wake->reply loop through the faked transport with the approval
gate wired, then inspects the wire: an exact `yes` approves in daemon code with
ZERO LLM packets; a qualified `yes but…` spends an LLM round-trip (debate) and
stays awaiting; a debate reply carrying a fresh plan block iterates; and the
assembled debate prompt is grounded on the pending plan.
"""

import io
import json
import os
import tempfile
import unittest

from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.plan import ApprovalGate, ApprovalStore
from daemon.prompt import Assembler
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(HERE, "season-state.json")
PROJ = os.path.join(HERE, "fixtures", "projections-sample.csv")


def _plan(**over):
    base = {"transfers_in": [], "transfers_out": [], "hits": 0,
            "starting_xi": ["Raya", "Saka"], "captain": "Haaland",
            "vice": "Salah", "chip": None, "contingencies": []}
    base.update(over)
    return base


def _block(plan):
    return "Revised: (C) now Salah.\n\n```plan\n" + json.dumps(plan) + "\n```\n"


def _workspace():
    root = tempfile.mkdtemp(prefix="gaffer-ws-")
    os.makedirs(os.path.join(root, "playbooks"))
    os.makedirs(os.path.join(root, "memory"))
    with open(os.path.join(root, "GAFFER.md"), "w") as f:
        f.write("PERSONA: the gaffer.\n")
    with open(os.path.join(root, "memory", "MEMORY.md"), "w") as f:
        f.write("- note\n")
    for pb in ("squad-review", "deadline-brief"):
        with open(os.path.join(root, "playbooks", f"{pb}.md"), "w") as f:
            f.write("Ground the answer in the snapshot.\n")
    return root


def _cfg():
    return Config(allowlist={42}, telegram_token="TT", openrouter_key="KK",
                  model="moonshotai/kimi-k2.5", base_url=DEFAULT_BASE_URL,
                  system_prompt="static")


class ApprovalLoopHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.approval_path = os.path.join(self._tmp.name, "approval-state.json")
        self.log = io.StringIO()

    def seed_pending(self, plan):
        ApprovalStore(self.approval_path).set_pending(2, plan)

    def run_text(self, text, llm_reply="debate reply"):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text=text)]],
            llm_reply=llm_reply)
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, self.log)
        assembler = Assembler(_workspace(), STATE, projections_path=PROJ, gw=2,
                              approval_store_path=self.approval_path)
        gate = ApprovalGate(ApprovalStore(self.approval_path))
        poll_once(cfg, tg, llm, log, offset=0, assembler=assembler, approvals=gate)
        return fake

    def store(self):
        return ApprovalStore(self.approval_path).load()

    def kinds(self):
        return [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]


class ApproveTest(ApprovalLoopHarness):
    def test_exact_yes_approves_in_daemon_code_with_no_llm_call(self):
        self.seed_pending(_plan())
        fake = self.run_text("yes")
        self.assertEqual(fake.llm_requests, [])              # NO model call
        self.assertEqual(len(fake.sent), 1)
        self.assertIn("approved", fake.sent[0]["text"])
        self.assertEqual(self.store().phase, "approved")
        self.assertIn("approve", self.kinds())

    def test_qualified_yes_is_debate_not_approval(self):
        self.seed_pending(_plan())
        fake = self.run_text("yes but the captain worries me")
        self.assertEqual(len(fake.llm_requests), 1)          # routed to the model
        self.assertEqual(self.store().phase, "awaiting_approval")
        self.assertNotIn("approve", self.kinds())

    def test_stale_yes_with_no_pending_plan_falls_through_to_llm(self):
        # A draft whose block never parsed leaves pending None; a yes must NOT
        # approve — it is just chat.
        ApprovalStore(self.approval_path).set_pending(2, None)
        fake = self.run_text("yes")
        self.assertEqual(len(fake.llm_requests), 1)
        self.assertNotIn("approve", self.kinds())
        self.assertEqual(self.store().phase, "awaiting_approval")


class GroundingTest(ApprovalLoopHarness):
    def test_debate_prompt_is_grounded_on_the_pending_plan(self):
        self.seed_pending(_plan(captain="Haaland", transfers_in=["Saka"],
                                transfers_out=["Gordon"]))
        fake = self.run_text("why Saka over Gordon?")
        system = fake.llm_requests[0]["messages"][0]["content"]
        self.assertIn("## Plan awaiting approval (GW2)", system)
        self.assertIn("Haaland", system)                     # a real plan fact
        self.assertIn("OUT Gordon → IN Saka", system)
        self.assertNotIn('"captain":', system)               # prose, never raw json


class IterateTest(ApprovalLoopHarness):
    def test_iterate_replaces_pending_and_strips_the_block(self):
        self.seed_pending(_plan(captain="Haaland"))
        fake = self.run_text("change (C) to Salah",
                             llm_reply=_block(_plan(captain="Salah")))
        # New pending, fresh yes required.
        st = self.store()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertEqual(st.pending_plan["captain"], "Salah")
        self.assertIsNone(st.approved_plan)
        # The machine block never reaches Telegram.
        self.assertNotIn("```", fake.sent[0]["text"])
        self.assertIn("Revised", fake.sent[0]["text"])
        self.assertIn("iterate", self.kinds())


class StopTest(ApprovalLoopHarness):
    def test_stop_on_a_locked_plan_holds_and_awaits_fresh_yes(self):
        s = ApprovalStore(self.approval_path)
        s.set_pending(2, _plan(captain="Haaland"))
        s.approve()
        s.phase = "locked"
        s.save()
        fake = self.run_text("stop")
        self.assertEqual(fake.llm_requests, [])              # deterministic, no LLM
        self.assertIn("hold", fake.sent[0]["text"])
        st = self.store()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertEqual(st.pending_plan["captain"], "Haaland")
        self.assertIsNone(st.approved_plan)
        self.assertIn("stop", self.kinds())


if __name__ == "__main__":
    unittest.main()
