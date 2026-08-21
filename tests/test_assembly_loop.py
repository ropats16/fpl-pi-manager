"""HTTP-edge harness for #16: an assembled, grounded prompt reaches the LLM.

Drives the real wake->reply loop through the faked transport with an Assembler
wired in, then inspects the exact request body the model would have received —
this is where the acceptance criteria are asserted (prompt contents, size bound,
no raw snapshot JSON).
"""

import io
import json
import os
import tempfile
import unittest

from daemon.config import Config
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once
from daemon.prompt import Assembler, estimate_tokens
from daemon.runtime import build_stack
from tests.fakes import FakeTransport, private_message

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(HERE, "season-state.json")
PROJ = os.path.join(HERE, "fixtures", "projections-sample.csv")


def _workspace():
    root = tempfile.mkdtemp(prefix="gaffer-ws-")
    os.makedirs(os.path.join(root, "playbooks"))
    os.makedirs(os.path.join(root, "memory"))
    with open(os.path.join(root, "GAFFER.md"), "w") as f:
        f.write("PERSONA-MARKER: I am the gaffer, Rohit's FPL manager.\n")
    with open(os.path.join(root, "memory", "MEMORY.md"), "w") as f:
        f.write("- GW1 is an initial build.\n")
    with open(os.path.join(root, "playbooks", "squad-review.md"), "w") as f:
        f.write("Summarise the squad grounded in the snapshot.\n")
    return root


def _cfg():
    return Config(allowlist={42}, telegram_token="TT", openrouter_key="KK",
                  model="moonshotai/kimi-k2.5", base_url=DEFAULT_BASE_URL,
                  system_prompt="unused when an assembler is wired")


class GroundedAnswerHarnessTest(unittest.TestCase):
    def _run(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="how's my team looking?")]],
            llm_reply="Haaland leads the line; solid XI.")
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, io.StringIO())
        assembler = Assembler(_workspace(), STATE, projections_path=PROJ, gw=1)
        poll_once(cfg, tg, llm, log, offset=0, assembler=assembler)
        return fake

    def test_reply_is_sent_and_llm_called_once(self):
        fake = self._run()
        self.assertEqual(len(fake.llm_requests), 1)
        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "Haaland leads the line; solid XI."}])

    def test_assembled_system_prompt_carries_squad_and_persona_facts(self):
        system = self._run().llm_requests[0]["messages"][0]
        self.assertEqual(system["role"], "system")
        self.assertIn("PERSONA-MARKER", system["content"])
        self.assertIn("Haaland", system["content"])      # traceable to state
        self.assertIn("7.9", system["content"])          # traceable to current projections

    def test_user_question_is_the_final_turn(self):
        msgs = self._run().llm_requests[0]["messages"]
        self.assertEqual(msgs[-1], {"role": "user", "content": "how's my team looking?"})

    def test_no_raw_snapshot_json_enters_the_prompt(self):
        system = self._run().llm_requests[0]["messages"][0]["content"]
        for marker in ('"picks"', "bought_for", "bench_order", '"starting"'):
            self.assertNotIn(marker, system)

    def test_prompt_stays_within_the_25k_token_bound(self):
        system = self._run().llm_requests[0]["messages"][0]["content"]
        self.assertLessEqual(estimate_tokens(system), 25000)


class AssemblerFailureFallbackTest(unittest.TestCase):
    """A broken workspace/state must not mute the bot — assembly failure falls
    back to the static system prompt so the wake still gets a reply."""

    class _BoomAssembler:
        def build_messages(self, user_text):
            raise RuntimeError("state file corrupt")

    def test_reply_still_sent_when_assembler_raises(self):
        fake = FakeTransport(
            updates_batches=[[private_message(from_id=42, text="hi")]],
            llm_reply="fallback reply")
        cfg = _cfg()
        tg, llm, log = build_stack(cfg, fake, io.StringIO())
        from daemon.loop import poll_once as _poll
        _poll(cfg, tg, llm, log, offset=0, assembler=self._BoomAssembler())
        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "fallback reply"}])
        system = fake.llm_requests[0]["messages"][0]["content"]
        self.assertEqual(system, cfg.system_prompt)   # degraded to static prompt


if __name__ == "__main__":
    unittest.main()
