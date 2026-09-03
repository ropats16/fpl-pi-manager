"""Wiring harness for `daemon review` (#21) — the cmd factory that builds the
post-GW review wake's component stack and hands it to `daemon.review.run_review`.

The pure grading (`build_scorecard`/`render_scorecard`) and the flow
(`run_review`) are proven in tests/test_review.py against the frozen signatures.
This file only asserts the *wiring*: that the cmd loads the full config, resolves
the entry id from the right places, and stays quiet (zero requests, no LLM) when
no gameweek has settled — the seams the entrypoint owns.

NOTE: the two tests that drive `run_review` to completion (the quiet-path and the
happy-path) fail with NotImplementedError until the concurrent #21 slice lands
`run_review`; they are marked below and assert the post-integration behaviour.
"""

import io
import json
import os
import tempfile
import unittest

from daemon.__main__ import _resolve_entry_id, run_review_cmd
from tests.fakes import FakeTransport

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(HERE, "fixtures", "projections-sample.csv")


def _events(finished_gw=None):
    """Distilled-bootstrap-shaped events; `finished_gw` marks 1..N finished."""
    out = []
    for i in (1, 2, 3):
        fin = finished_gw is not None and i <= finished_gw
        out.append({"id": i, "finished": fin, "data_checked": fin,
                    "deadline_time": f"2026-08-{20 + i:02d}T11:00:00Z"})
    return out


class _Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = self._tmp.name
        self.state_path = os.path.join(self.d, "season-state.json")
        self._write_state(entry_id=None)
        # A minimal workspace so build_assembler (built inside the factory) has
        # its playbooks dir; only reached on the paths that call run_review.
        ws = os.path.join(self.d, "agent")
        for sub in ("playbooks", "memory"):
            os.makedirs(os.path.join(ws, sub), exist_ok=True)
        with open(os.path.join(ws, "GAFFER.md"), "w") as f:
            f.write("PERSONA\n")
        for pb in ("post-gw-review", "analysis", "squad-review"):
            with open(os.path.join(ws, "playbooks", f"{pb}.md"), "w") as f:
                f.write(f"{pb} playbook\n")
        self.ws = ws

    def _write_state(self, entry_id):
        with open(self.state_path, "w") as f:
            json.dump({"season": "2026-27", "current_gw": 2,
                       "entry_id": entry_id, "squad": {"picks": []}}, f)

    def env(self, **over):
        e = {"GAFFER_ALLOWLIST_USER_IDS": "42",
             "TELEGRAM_BOT_TOKEN": "TT",
             "OPENROUTER_API_KEY": "KK",
             "GAFFER_STATE_PATH": self.state_path,
             "GAFFER_DATA_DIR": os.path.join(self.d, "data"),
             "GAFFER_REPORTS_DIR": os.path.join(self.d, "reports"),
             "GAFFER_LEARNINGS_PATH": os.path.join(self.d, "learnings.md"),
             "GAFFER_WORKSPACE_DIR": getattr(self, "ws", ""),
             "GAFFER_APPROVAL_STATE_PATH": os.path.join(self.d, "approval.json"),
             "GAFFER_PROJECTIONS_PATH": PROJ}
        e.update(over)
        return e


class MissingConfigTest(_Harness):
    """The cmd loads the FULL config (LLM key included) up front: a missing
    credential is a ValueError raised BEFORE any fetch fires — no wasted request,
    no half-run wake."""

    def test_missing_key_raises_before_any_fetch(self):
        calls = []

        def spy_events():
            calls.append(1)
            return _events()

        env = self.env()
        env.pop("OPENROUTER_API_KEY")           # brief thinks -> needs the key
        with self.assertRaises(ValueError):
            run_review_cmd(env=env, transport=FakeTransport(),
                           fetch_events=spy_events, out=io.StringIO())
        self.assertEqual(calls, [])              # never reached a fetch


class EntryIdResolutionTest(_Harness):
    """Entry id: FPL_ENTRY_ID env first, then season-state.entry_id, else None
    (the review then falls back to the season-state squad). Tolerant parse — junk
    resolves to None, never raises."""

    def test_env_wins_over_state(self):
        self._write_state(entry_id=222)
        self.assertEqual(_resolve_entry_id({"FPL_ENTRY_ID": "111"},
                                           self.state_path), 111)

    def test_state_used_when_env_absent(self):
        self._write_state(entry_id=333)
        self.assertEqual(_resolve_entry_id({}, self.state_path), 333)

    def test_blank_env_falls_through_to_state(self):
        self._write_state(entry_id=444)
        self.assertEqual(_resolve_entry_id({"FPL_ENTRY_ID": "  "},
                                           self.state_path), 444)

    def test_none_when_neither_present(self):
        self._write_state(entry_id=None)
        self.assertIsNone(_resolve_entry_id({}, self.state_path))

    def test_junk_env_resolves_to_none(self):
        self.assertIsNone(_resolve_entry_id({"FPL_ENTRY_ID": "not-an-int"},
                                            self.state_path))

    def test_missing_state_file_resolves_to_none(self):
        self.assertIsNone(_resolve_entry_id({}, os.path.join(self.d, "nope.json")))


class QuietWhenNoFinishedGwTest(_Harness):
    """No settled gameweek -> the wake is silent: rc 0, zero transport requests,
    no LLM. (Drives run_review's quiet branch; fails with NotImplementedError
    until the concurrent #21 slice lands run_review.)"""

    def test_no_finished_gw_is_quiet(self):
        transport = FakeTransport()

        def fetch_events():
            return _events(finished_gw=None)

        def fetch_actuals(gw):               # must never be called on a quiet wake
            raise AssertionError("fetch_actuals should not run when nothing settled")

        rc = run_review_cmd(env=self.env(), transport=transport,
                            fetch_events=fetch_events, fetch_actuals=fetch_actuals,
                            out=io.StringIO())
        self.assertEqual(rc, 0)
        self.assertEqual(transport.requests, [])     # no network at all


class HappyPathTest(_Harness):
    """A settled GW 2 with a fielded squad -> the wake grades it, sends the
    review, and marks the GW reviewed. (Fails ONLY with NotImplementedError until
    the concurrent #21 slice lands run_review; asserts post-integration
    behaviour — one /sendMessage request.)"""

    def test_settled_gw_sends_a_review(self):
        transport = FakeTransport(
            llm_replies=["GW2 review — decent.\n\n```learnings\n"
                         '{"specific": [], "general": []}\n```'])

        def fetch_events():
            return _events(finished_gw=2)

        def fetch_actuals(gw):
            live = {113: {"minutes": 90, "total_points": 13, "goals_scored": 2,
                          "assists": 1, "clean_sheets": 0, "bonus": 3}}
            picks = {"picks": [{"id": 113, "position": 1, "multiplier": 2,
                                "is_captain": True, "is_vice_captain": False}],
                     "entry_history": {"points": 26, "points_on_bench": 4,
                                       "rank": 100, "overall_rank": 3_100_000,
                                       "event_transfers": 0,
                                       "event_transfers_cost": 0, "bank": 5}}
            players = {113: {"web_name": "Haaland", "pos": "FWD", "team": "MCI"}}
            return {"live": live, "picks": picks, "players": players}

        rc = run_review_cmd(env=self.env(), transport=transport,
                            fetch_events=fetch_events, fetch_actuals=fetch_actuals,
                            out=io.StringIO())
        self.assertEqual(rc, 0)
        self.assertTrue(any("/sendMessage" in url for _, url in transport.requests))


if __name__ == "__main__":
    unittest.main()
