"""The #18 deadline-brief wake: cheap clock check -> draft / final / act, every
external edge injected so the whole path runs offline (mirrors test_watch.py).

The act tests are where the load-bearing acceptance line is asserted: an
unapproved deadline makes ZERO actuator calls (the gate held) and records a loud
no-write; an approved one records to season state with a manual-apply status.
"""

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.actuator import ManualApplyActuator
from daemon.brief import decide_wake, next_deadline, run_brief
from daemon.logging_setup import StructuredLogger
from daemon.plan import ApprovalStore

DEADLINE = "2026-08-29T11:00:00Z"          # Sat 16:30 IST
EVENTS = [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z", "finished": True,
           "is_next": False},
          {"id": 2, "deadline_time": DEADLINE, "finished": False, "is_next": True},
          {"id": 3, "deadline_time": "2026-09-04T17:30:00Z", "finished": False,
           "is_next": False}]


def _dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _plan(**over):
    base = {"transfers_in": [], "transfers_out": [], "hits": 0,
            "starting_xi": ["Raya", "Saka"], "captain": "Haaland",
            "vice": "Salah", "chip": None, "contingencies": []}
    base.update(over)
    return base


def _brief_with_block(plan, prose="GW2 brief — roll FT, (C) Haaland."):
    return prose + "\n\n```plan\n" + json.dumps(plan) + "\n```\n"


class _Recorder:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send_message(self, chat_id, text):
        if self.fail:
            raise RuntimeError("sendMessage failed")
        self.sent.append({"chat_id": chat_id, "text": text})


class _Assembler:
    def build_messages(self, user_text):
        return [{"role": "system", "content": "SYS"},
                {"role": "user", "content": user_text}]


# --- next_deadline / decide_wake units --------------------------------------


class NextDeadlineTest(unittest.TestCase):
    def test_picks_earliest_unfinished_future_deadline(self):
        gw, dl = next_deadline(EVENTS, _dt("2026-08-28T00:00:00Z"))
        self.assertEqual(gw, 2)
        self.assertEqual(dl, _dt(DEADLINE))

    def test_none_when_no_future_deadline(self):
        self.assertIsNone(next_deadline(EVENTS, _dt("2026-09-05T00:00:00Z")))


class _St:
    def __init__(self, phase="idle", draft_sent=False, final_sent=False):
        self.phase = phase
        self.draft_sent = draft_sent
        self.final_sent = final_sent


class DecideWakeTest(unittest.TestCase):
    def setUp(self):
        self.dl = _dt(DEADLINE)

    def d(self, now, st=None):
        return decide_wake(_dt(now), self.dl, st or _St())

    def test_within_48h_evening_ist_fires_draft(self):
        # 2026-08-27T14:00Z = 19:30 IST, 45h out (>24h) -> the evening branch.
        self.assertEqual(self.d("2026-08-27T14:00:00Z"), "draft")

    def test_beyond_48h_even_in_the_evening_is_quiet(self):
        # 2026-08-26T14:00Z = 19:30 IST but 69h out -> outside the 48h bound.
        self.assertIsNone(self.d("2026-08-26T14:00:00Z"))

    def test_within_24h_non_evening_fires_draft_fallback(self):
        # 2026-08-28T12:00Z = 17:30 IST (not evening) but 23h out -> fallback.
        self.assertEqual(self.d("2026-08-28T12:00:00Z"), "draft")

    def test_draft_not_repeated_once_sent(self):
        self.assertIsNone(self.d("2026-08-28T12:00:00Z", _St(draft_sent=True)))

    def test_final_window_fires_final(self):
        self.assertEqual(self.d("2026-08-29T09:00:00Z", _St(draft_sent=True)),
                         "final")

    def test_final_not_repeated_once_sent(self):
        self.assertIsNone(self.d("2026-08-29T09:00:00Z",
                                 _St(draft_sent=True, final_sent=True)))

    def test_act_window_fires_act(self):
        self.assertEqual(self.d("2026-08-29T10:35:00Z", _St(phase="approved")),
                         "act")

    def test_act_not_repeated_once_acted(self):
        self.assertIsNone(self.d("2026-08-29T10:35:00Z", _St(phase="acted")))

    def test_after_deadline_is_quiet(self):
        self.assertIsNone(self.d("2026-08-29T11:30:00Z", _St(phase="approved")))


# --- run_brief flow harness -------------------------------------------------


class BriefHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = self._tmp.name
        self.approval_path = os.path.join(d, "data", "approval-state.json")
        self.state_path = os.path.join(d, "season-state.json")
        self.reports_dir = os.path.join(d, "reports")
        with open(self.state_path, "w") as f:
            json.dump({"season": "2026-27", "current_gw": 2,
                       "squad": {"picks": []}}, f)
        self.store = ApprovalStore(self.approval_path)
        self.actuator = ManualApplyActuator()
        self.log = io.StringIO()
        self.logger = StructuredLogger(stream=self.log)

    def run_at(self, now, replies, telegram=None, allowlist=(42,)):
        telegram = _Recorder() if telegram is None else telegram
        pending = list(replies)

        def llm_complete(messages):
            return pending.pop(0)

        rc = run_brief(fetch=lambda: EVENTS, llm_complete=llm_complete,
                       assembler_factory=_Assembler, store=self.store,
                       telegram=telegram, allowlist=set(allowlist),
                       logger=self.logger, actuator=self.actuator,
                       state_path=self.state_path, reports_dir=self.reports_dir,
                       now=_dt(now))
        return rc, telegram

    def kinds(self):
        return [json.loads(l)["event"] for l in self.log.getvalue().splitlines()]

    def event(self, name):
        for l in self.log.getvalue().splitlines():
            e = json.loads(l)
            if e["event"] == name:
                return e
        return None

    def decisions(self):
        with open(self.state_path) as f:
            return json.load(f).get("decisions", {})


# --- draft flow -------------------------------------------------------------


class DraftFlowTest(BriefHarness):
    def test_draft_sends_stripped_brief_sets_pending_writes_log_no_actuator(self):
        plan = _plan(transfers_in=["Saka"], transfers_out=["Gordon"])
        reply = _brief_with_block(plan)
        rc, tg = self.run_at("2026-08-28T12:00:00Z", [reply])

        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)
        self.assertNotIn("```", tg.sent[0]["text"])           # block stripped
        self.assertIn("GW2 brief", tg.sent[0]["text"])

        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertEqual(st.pending_plan["transfers_in"], ["Saka"])
        self.assertTrue(st.draft_sent)

        log = os.path.join(self.reports_dir, "gw02", "decision-log.md")
        self.assertTrue(os.path.exists(log))
        with open(log) as f:
            self.assertIn("```plan", f.read())               # FULL reply logged
        self.assertEqual(self.actuator.applied, [])           # gate: no actuator
        self.assertIn("brief_draft_sent", self.kinds())

    def test_missing_plan_block_retries_once_then_succeeds(self):
        good = _brief_with_block(_plan())
        rc, tg = self.run_at("2026-08-28T12:00:00Z",
                             ["brief with no block at all", good])
        self.assertEqual(rc, 0)
        st = ApprovalStore(self.approval_path).load()
        self.assertIsNotNone(st.pending_plan)                 # recovered on retry
        self.assertEqual(self.event("brief_plan_missing")["attempt"], 1)

    def test_still_missing_after_retry_sends_text_but_pending_stays_none(self):
        rc, tg = self.run_at("2026-08-28T12:00:00Z",
                             ["no block", "still no block"])
        self.assertEqual(rc, 0)
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertIsNone(st.pending_plan)                    # a yes can't approve
        self.assertTrue(st.draft_sent)
        self.assertEqual(tg.sent[0]["text"], "still no block")

    def test_send_failure_does_not_mark_draft_sent(self):
        reply = _brief_with_block(_plan())
        rc, tg = self.run_at("2026-08-28T12:00:00Z", [reply],
                             telegram=_Recorder(fail=True))
        self.assertEqual(rc, 1)
        st = ApprovalStore(self.approval_path).load()
        self.assertFalse(st.draft_sent)                       # retries next tick
        self.assertIn("brief_send_error", self.kinds())


# --- final flow -------------------------------------------------------------


class FinalFlowTest(BriefHarness):
    def _approve(self, plan):
        self.store.set_pending(2, plan)
        self.store.approve()
        self.store.draft_sent = True
        self.store.save()

    def test_unchanged_final_locks_with_no_change_message(self):
        p = _plan(transfers_in=["Saka"], transfers_out=["Gordon"])
        self._approve(p)
        rc, tg = self.run_at("2026-08-29T09:00:00Z", [_brief_with_block(dict(p))])
        self.assertEqual(rc, 0)
        self.assertIn("no change since your yes", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "locked")
        self.assertTrue(st.final_sent)
        self.assertFalse(self.event("brief_final_sent")["changed"])

    def test_changed_final_voids_and_demands_fresh_yes(self):
        self._approve(_plan(captain="Haaland"))
        rc, tg = self.run_at("2026-08-29T09:00:00Z",
                             [_brief_with_block(_plan(captain="Salah"))])
        self.assertEqual(rc, 0)
        self.assertIn("CHANGED", tg.sent[0]["text"])
        self.assertIn("fresh yes required", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertIsNone(st.approved_plan)
        self.assertEqual(st.pending_plan["captain"], "Salah")
        self.assertTrue(self.event("brief_final_sent")["changed"])

    def test_final_with_no_plan_block_voids_but_names_the_recovery_path(self):
        # The carry-void diff can't run without a machine plan, so nothing may
        # auto-lock — but the alert must name the recovery (iterate then yes),
        # not demand a `yes` that can't approve a None pending.
        self._approve(_plan())
        rc, tg = self.run_at("2026-08-29T09:00:00Z", ["no block", "still none"])
        self.assertEqual(rc, 0)
        self.assertIn("NOT auto-lock", tg.sent[0]["text"])
        self.assertIn("re-issue the plan", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "awaiting_approval")
        self.assertIsNone(st.approved_plan)
        self.assertIsNone(st.pending_plan)
        self.assertTrue(st.final_sent)
        self.assertFalse(self.event("brief_final_sent")["has_plan"])
        self.assertEqual(self.event("brief_plan_missing")["attempt"], 1)

    def test_chip_plan_needs_fresh_yes_even_when_identical(self):
        p = _plan(chip="bench_boost")
        self._approve(dict(p))
        rc, tg = self.run_at("2026-08-29T09:00:00Z", [_brief_with_block(dict(p))])
        self.assertEqual(rc, 0)
        self.assertIn("chip plan — fresh yes required", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "awaiting_approval")


# --- act flow (the load-bearing acceptance line) ----------------------------


class ActFlowTest(BriefHarness):
    def test_approved_act_calls_actuator_records_locked_and_sends_receipt(self):
        p = _plan(transfers_in=["Saka"], transfers_out=["Gordon"])
        self.store.set_pending(2, p)
        self.store.approve()
        self.store.save()

        rc, tg = self.run_at("2026-08-29T10:35:00Z", [])   # no LLM in act
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.actuator.applied), 1)      # gate opened
        self.assertEqual(self.actuator.applied[0]["gw"], 2)
        self.assertEqual(self.decisions()["gw02"]["status"], "locked")
        self.assertIn("✅ GW2 locked", tg.sent[0]["text"])
        self.assertIn("Apply in the FPL app", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "acted")

    def test_unapproved_act_makes_no_actuator_call_and_no_writes(self):
        # phase awaiting_approval, nothing approved -> the timeout no-write.
        self.store.set_pending(2, _plan())
        self.store.save()

        rc, tg = self.run_at("2026-08-29T10:35:00Z", [])
        self.assertEqual(rc, 0)
        self.assertEqual(self.actuator.applied, [])           # HARD gate assertion
        self.assertEqual(self.decisions()["gw02"]["status"], "no_write")
        self.assertIn("NO changes", tg.sent[0]["text"])
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "no_write")
        self.assertIn("brief_no_write", self.kinds())


# --- fetch failure ----------------------------------------------------------


class FetchFailureTest(BriefHarness):
    def test_fetch_error_logs_and_leaves_state_unchanged(self):
        def boom():
            raise RuntimeError("bootstrap fetch failed")

        rc = run_brief(fetch=boom, llm_complete=lambda m: "x",
                       assembler_factory=_Assembler, store=self.store,
                       telegram=_Recorder(), allowlist={42}, logger=self.logger,
                       actuator=self.actuator, state_path=self.state_path,
                       reports_dir=self.reports_dir,
                       now=_dt("2026-08-28T12:00:00Z"))
        self.assertEqual(rc, 1)
        self.assertIn("brief_error", self.kinds())
        st = ApprovalStore(self.approval_path).load()
        self.assertEqual(st.phase, "idle")                    # never advanced


class QuietTest(BriefHarness):
    def test_outside_any_window_is_quiet_and_spends_no_llm(self):
        calls = []
        rc = run_brief(fetch=lambda: EVENTS,
                       llm_complete=lambda m: calls.append(1),
                       assembler_factory=_Assembler, store=self.store,
                       telegram=_Recorder(), allowlist={42}, logger=self.logger,
                       actuator=self.actuator, state_path=self.state_path,
                       reports_dir=self.reports_dir,
                       now=_dt("2026-08-25T09:00:00Z"))   # ~4 days out
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])
        self.assertIn("brief_quiet", self.kinds())


if __name__ == "__main__":
    unittest.main()
