"""Unit tests for the manual-apply actuator (#18).

Until the real FPL write (#13/#14/#19) is proven, `apply` only produces
instructions and records the call — the record is what the brief harness asserts
to prove the gate held. No network, no mutation, ever.
"""

import unittest

from daemon.actuator import ManualApplyActuator


def _plan(**over):
    base = {"transfers_in": [], "transfers_out": [], "hits": 0,
            "starting_xi": [], "captain": None, "vice": None, "chip": None,
            "contingencies": []}
    base.update(over)
    return base


class ManualApplyActuatorTest(unittest.TestCase):
    def test_transfer_plan_lists_out_in_hit_captain_and_xi(self):
        act = ManualApplyActuator()
        text = act.apply(_plan(transfers_in=["Saka"], transfers_out=["Gordon"],
                               hits=4, captain="Haaland", vice="Salah",
                               starting_xi=["Raya", "Saka", "Haaland"]), 12)
        self.assertIn("Apply in the FPL app before the deadline:", text)
        self.assertIn("OUT Gordon → IN Saka", text)
        self.assertIn("(−4 hit)", text)
        self.assertIn("Captain: Haaland, Vice: Salah", text)
        self.assertIn("XI: Raya, Saka, Haaland", text)

    def test_no_transfer_plan_says_confirm_unchanged(self):
        act = ManualApplyActuator()
        text = act.apply(_plan(captain="Haaland", vice="Salah"), 12)
        self.assertIn("no transfers — confirm XI/(C) unchanged", text)

    def test_chip_line_only_present_when_a_chip_is_set(self):
        act = ManualApplyActuator()
        without = act.apply(_plan(captain="Haaland"), 12)
        self.assertNotIn("Chip:", without)
        with_chip = act.apply(_plan(captain="Haaland", chip="bench_boost"), 12)
        self.assertIn("Chip: bench_boost", with_chip)

    def test_every_call_is_recorded_for_the_harness(self):
        act = ManualApplyActuator()
        self.assertEqual(act.applied, [])
        act.apply(_plan(captain="Haaland"), 12)
        self.assertEqual(len(act.applied), 1)
        self.assertEqual(act.applied[0], {"gw": 12, "plan": _plan(captain="Haaland")})

    def test_hit_omitted_when_zero(self):
        act = ManualApplyActuator()
        text = act.apply(_plan(transfers_in=["Saka"], transfers_out=["Gordon"],
                               hits=0), 12)
        self.assertIn("OUT Gordon → IN Saka", text)
        self.assertNotIn("hit)", text)


if __name__ == "__main__":
    unittest.main()
