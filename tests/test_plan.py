"""Unit tests for the deterministic plan/approval primitives (#18).

The write gate lives in this code, so the tokens are tested as hard as the
struct diff: an inexact `yes` must NOT approve, a malformed plan block must NOT
become a snapshot, and a corrupt state file must degrade to idle, never crash.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.plan import (ApprovalStore, APPROVE_TOKENS, is_approval, is_stop,
                         parse_plan, plan_prose, plan_summary, plans_differ,
                         record_decision)


def _plan(**over):
    base = {"transfers_in": [], "transfers_out": [], "hits": 0,
            "starting_xi": [], "captain": None, "vice": None, "chip": None,
            "contingencies": []}
    base.update(over)
    return base


BLOCK = ('Here is the brief.\n\n```plan\n'
         '{"transfers_in": ["Saka"], "transfers_out": ["Gordon"], "hits": 0,\n'
         ' "starting_xi": ["Raya","Saka"], "captain": "Haaland", "vice": "Salah",\n'
         ' "chip": null, "contingencies": ["if Saka out → keep Gordon"]}\n```\n')


# --- token matchers ---------------------------------------------------------


class ApprovalTokenTest(unittest.TestCase):
    def test_exact_tokens_approve_trimmed_and_case_insensitive(self):
        for t in ("yes", "Y ", " LOCK", "approve", "Yes\n"):
            self.assertTrue(is_approval(t), t)
        self.assertEqual(APPROVE_TOKENS, {"yes", "y", "lock", "approve"})

    def test_substring_or_qualified_yes_is_not_approval(self):
        for t in ("yes but…", "yes, and change X", "ok yes", "yesx", "yep", ""):
            self.assertFalse(is_approval(t), t)

    def test_stop_is_exact_case_insensitive(self):
        for t in ("stop", "STOP", " Stop "):
            self.assertTrue(is_stop(t), t)
        for t in ("stop it", "please stop", "", "sto"):
            self.assertFalse(is_stop(t), t)


# --- parse_plan -------------------------------------------------------------


class ParsePlanTest(unittest.TestCase):
    def test_roundtrip_normalizes_keys_and_strips_the_block(self):
        plan, text = parse_plan(BLOCK)
        self.assertEqual(plan["transfers_in"], ["Saka"])
        self.assertEqual(plan["captain"], "Haaland")
        self.assertEqual(plan["chip"], None)
        self.assertEqual(plan["hits"], 0)
        self.assertEqual(text, "Here is the brief.")     # block stripped
        self.assertNotIn("```", text)

    def test_no_block_returns_none_and_original_text(self):
        plan, text = parse_plan("just a chat reply, no block")
        self.assertIsNone(plan)
        self.assertEqual(text, "just a chat reply, no block")

    def test_malformed_json_returns_none_and_original_text_untouched(self):
        raw = "brief\n\n```plan\n{not valid json,,}\n```\n"
        plan, text = parse_plan(raw)
        self.assertIsNone(plan)
        self.assertEqual(text, raw)                      # nothing half-parsed

    def test_missing_keys_are_defaulted(self):
        plan, _ = parse_plan('```plan\n{"captain": "Haaland"}\n```')
        self.assertEqual(plan, _plan(captain="Haaland"))

    def test_non_dict_payload_yields_all_defaults(self):
        plan, _ = parse_plan('```plan\n[1,2,3]\n```')
        self.assertEqual(plan, _plan())


# --- plans_differ -----------------------------------------------------------


class PlansDifferTest(unittest.TestCase):
    def setUp(self):
        self.a = _plan(transfers_in=["Saka"], transfers_out=["Gordon"], hits=4,
                       starting_xi=["Raya", "Saka", "Haaland"],
                       captain="Haaland", vice="Salah", chip=None,
                       contingencies=["if Saka out → keep Gordon"])

    def test_identical_plans_do_not_differ(self):
        self.assertFalse(plans_differ(self.a, dict(self.a)))

    def test_each_field_flips_it(self):
        for field, val in (("transfers_in", ["Palmer"]),
                           ("transfers_out", ["Salah"]),
                           ("hits", 0),
                           ("starting_xi", ["Raya"]),
                           ("captain", "Salah"),
                           ("vice", "Haaland"),
                           ("chip", "bench_boost"),
                           ("contingencies", ["if X → Y"])):
            b = dict(self.a)
            b[field] = val
            self.assertTrue(plans_differ(self.a, b), field)

    def test_list_order_is_irrelevant(self):
        b = dict(self.a)
        b["starting_xi"] = ["Haaland", "Saka", "Raya"]
        self.assertFalse(plans_differ(self.a, b))

    def test_name_case_is_irrelevant(self):
        b = dict(self.a)
        b["captain"] = "haaland"
        b["transfers_in"] = ["saka"]
        self.assertFalse(plans_differ(self.a, b))

    def test_none_on_one_side_differs_two_nones_equal(self):
        self.assertTrue(plans_differ(self.a, None))
        self.assertFalse(plans_differ(None, None))


# --- prose / summary --------------------------------------------------------


class ProseTest(unittest.TestCase):
    def test_prose_is_never_raw_json(self):
        prose = plan_prose(_plan(transfers_in=["Saka"], transfers_out=["Gordon"],
                                 captain="Haaland", vice="Salah"))
        self.assertIn("Haaland", prose)
        self.assertIn("OUT Gordon → IN Saka", prose)
        self.assertNotIn("{", prose)

    def test_summary_one_line(self):
        s = plan_summary(_plan(transfers_in=["Saka"], transfers_out=["Gordon"],
                               captain="Haaland", vice="Salah"))
        self.assertIn("Gordon→Saka", s)
        self.assertIn("(C) Haaland", s)


# --- ApprovalStore ----------------------------------------------------------


class ApprovalStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "state", "approval-state.json")

    def test_missing_file_loads_as_clean_idle(self):
        st = ApprovalStore(self.path).load()
        self.assertEqual(st.phase, "idle")
        self.assertIsNone(st.pending_plan)
        self.assertFalse(st.draft_sent)

    def test_corrupt_file_degrades_to_idle_not_a_crash(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not json")
        st = ApprovalStore(self.path).load()
        self.assertEqual(st.phase, "idle")

    def test_atomic_persistence_roundtrip(self):
        s = ApprovalStore(self.path)
        s.set_pending(12, _plan(captain="Haaland"))
        s.draft_sent = True
        s.save()
        again = ApprovalStore(self.path).load()
        self.assertEqual(again.gw, 12)
        self.assertEqual(again.phase, "awaiting_approval")
        self.assertEqual(again.pending_plan["captain"], "Haaland")
        self.assertTrue(again.draft_sent)

    def test_approve_promotes_pending_to_approved(self):
        s = ApprovalStore(self.path)
        s.set_pending(12, _plan(captain="Haaland"))
        s.approve()
        self.assertEqual(s.phase, "approved")
        self.assertEqual(s.approved_plan["captain"], "Haaland")

    def test_void_carry_clears_approval_and_sets_new_pending(self):
        s = ApprovalStore(self.path)
        s.set_pending(12, _plan(captain="Haaland"))
        s.approve()
        s.void_carry(_plan(captain="Salah"))
        self.assertEqual(s.phase, "awaiting_approval")
        self.assertIsNone(s.approved_plan)             # stale yes can't fire
        self.assertEqual(s.pending_plan["captain"], "Salah")

    def test_reset_for_new_gw_is_clean_idle_bound_to_gw(self):
        s = ApprovalStore(self.path)
        s.set_pending(12, _plan())
        s.draft_sent = True
        s.save()
        s.reset_for(13)
        self.assertEqual((s.gw, s.phase, s.draft_sent), (13, "idle", False))


# --- record_decision --------------------------------------------------------


class RecordDecisionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "season-state.json")
        with open(self.state_path, "w") as f:
            json.dump({"season": "2026-27", "current_gw": 2,
                       "squad": {"picks": []}}, f)

    def test_writes_decision_and_preserves_everything_else(self):
        now = datetime(2026, 8, 29, 9, 30, tzinfo=timezone.utc)
        record_decision(self.state_path, 2, _plan(captain="Haaland"), "locked",
                        now=now)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(state["season"], "2026-27")        # untouched
        dec = state["decisions"]["gw02"]
        self.assertEqual(dec["status"], "locked")
        self.assertEqual(dec["plan"]["captain"], "Haaland")
        self.assertEqual(dec["recorded_at"], "2026-08-29T09:30:00Z")

    def test_missing_state_file_raises(self):
        with self.assertRaises(Exception):
            record_decision(os.path.join(self._tmp.name, "nope.json"), 2,
                            _plan(), "locked")


if __name__ == "__main__":
    unittest.main()
