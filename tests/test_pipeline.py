"""The #78 projection refresh: `daemon/pipeline.py` re-runs the math pipeline
(fetch -> csv -> projections, never the optimizer) when `data/projections.csv`
is older than 12h, so every brief/review wake grounds on current numbers — the
Pi's copy had gone pre-season stale (2026-08-22, "Haaland 4.4 pts" in GW3) with
nothing to re-run it. The runner is an injectable subprocess.run-shaped seam:
this suite never forks a real process or touches the network.

The cmd tests assert the wiring the entrypoint owns: `daemon brief` and
`daemon review` refresh BEFORE the wake's first LLM call, and `daemon refresh`
prints the one status line.
"""

import io
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.__main__ import run_brief_cmd, run_refresh_cmd, run_review_cmd
from daemon.logging_setup import StructuredLogger
from daemon.pipeline import refresh_projections
from tests.fakes import FakeTransport

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(HERE, "fixtures", "projections-sample.csv")
NOW = 1_800_000_000.0                      # fixed epoch the injected clock returns
HEADER = "player,pos,gw,proj\n"


def _dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class _Res:
    """subprocess.run-shaped result: just the fields refresh_projections reads."""

    def __init__(self, rc, stderr=""):
        self.returncode = rc
        self.stderr = stderr
        self.stdout = ""


class FakeRunner:
    """subprocess.run-shaped fake: records every (argv, cwd, timeout) and
    answers with the next scripted (rc, stderr) pair (the last one repeats).
    `effect(n)` runs after call n so the fake can emulate the real pipeline's
    side effect of writing a fresh projections.csv."""

    def __init__(self, results=((0, ""),), effect=None, raise_exc=None):
        self.calls = []
        self._results = list(results)
        self._effect = effect
        self._raise = raise_exc

    def __call__(self, argv, cwd=None, timeout=None):
        self.calls.append({"argv": list(argv), "cwd": cwd, "timeout": timeout})
        if self._raise is not None:
            raise self._raise
        rc, err = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if self._effect is not None:
            self._effect(len(self.calls))
        return _Res(rc, err)


class _Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.data = os.path.join(self.root, "data")
        os.makedirs(self.data, exist_ok=True)
        self.log = io.StringIO()
        self.logger = StructuredLogger(stream=self.log)

    # --- file helpers ---------------------------------------------------------

    def write_csv(self, rows=3, mtime=None):
        path = os.path.join(self.data, "projections.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(HEADER + "".join(f"p{i},MID,{i},7.5\n" for i in range(rows)))
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def write_snap(self, prefix, name, mtime):
        path = os.path.join(self.data, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"kind": prefix}, f)
        os.utime(path, (mtime, mtime))
        return path

    def csv_text(self):
        with open(os.path.join(self.data, "projections.csv"), encoding="utf-8") as f:
            return f.read()

    # --- helpers --------------------------------------------------------------

    def events(self):
        return [json.loads(l) for l in self.log.getvalue().splitlines()
                if l.startswith("{")]

    def refresh(self, runner=None, **over):
        return refresh_projections(self.root, self.data, self.logger,
                                   runner=runner, clock=lambda: NOW, **over)


class FreshCsvTest(_Harness):
    """A young projections.csv costs nothing: no subprocess, status fresh."""

    def test_fresh_file_runs_no_subprocess(self):
        self.write_csv(rows=3, mtime=NOW - 3600)          # 1h old < 12h
        runner = FakeRunner()
        res = self.refresh(runner=runner)
        self.assertEqual(res["status"], "fresh")
        self.assertEqual(runner.calls, [])
        self.assertAlmostEqual(res["age_hours"], 1.0, places=2)
        self.assertEqual(res["rows"], 3)

    def test_at_the_boundary_is_stale(self):
        # Exactly max_age_hours old is NOT "younger than" it -> refresh.
        self.write_csv(rows=3, mtime=NOW - 12 * 3600)
        runner = FakeRunner()
        res = self.refresh(runner=runner, max_age_hours=12)
        self.assertEqual(res["status"], "refreshed")
        self.assertEqual(len(runner.calls), 4)

    def test_fresh_logs_no_event(self):
        self.write_csv(rows=3, mtime=NOW - 3600)
        self.refresh(runner=FakeRunner())
        self.assertEqual(self.events(), [])


class StaleRefreshTest(_Harness):
    """A stale projections.csv re-runs the pipeline's four steps, in order,
    in repo_root, 10-minute timeout each — and never the optimizer."""

    def setUp(self):
        super().setUp()
        self.old = NOW - 13 * 3600                        # 13h old -> stale
        self.write_csv(rows=3, mtime=self.old)
        self.boot = self.write_snap("bootstrap", "bootstrap-20260822-0900.json",
                                    self.old)
        self.boot_new = self.write_snap("bootstrap", "bootstrap-20260823-0900.json",
                                        self.old + 60)
        self.fix = self.write_snap("fixtures", "fixtures-20260822-0900.json",
                                   self.old)

    def _writer(self, rows=5):
        def effect(n):
            if n == 4:                                    # the projections step
                self.write_csv(rows=rows, mtime=NOW)
        return effect

    def test_four_calls_in_run_pipeline_sh_order(self):
        runner = FakeRunner(effect=self._writer())
        res = self.refresh(runner=runner)
        self.assertEqual(res["status"], "refreshed")
        self.assertEqual(len(runner.calls), 4)
        d = self.data
        self.assertEqual(runner.calls[0]["argv"],
                         ["python3", "fpl_api.py", "fetch", "--out", d])
        # The NEWEST bootstrap snapshot (run_pipeline.sh: `ls -t | head -1`).
        self.assertEqual(runner.calls[1]["argv"],
                         ["python3", "fpl_api.py", "csv", self.boot_new,
                          "--out", d])
        self.assertEqual(runner.calls[2]["argv"],
                         ["python3", "fpl_api.py", "csv", self.fix, "--out", d])
        self.assertEqual(runner.calls[3]["argv"], ["python3", "fpl_projections.py"])
        for call in runner.calls:                         # every step, same bounds
            self.assertEqual(call["cwd"], self.root)
            self.assertEqual(call["timeout"], 600)

    def test_rows_are_the_new_csv_data_lines(self):
        runner = FakeRunner(effect=self._writer(rows=7))
        res = self.refresh(runner=runner)
        self.assertEqual(res["rows"], 7)

    def test_refreshed_is_logged_with_rows_and_age(self):
        runner = FakeRunner(effect=self._writer(rows=5))
        self.refresh(runner=runner)
        ev = [e for e in self.events() if e["event"] == "projections_refreshed"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["rows"], 5)
        self.assertAlmostEqual(ev[0]["age_hours"], 13.0, places=2)

    def test_missing_csv_is_stale_not_fatal(self):
        os.remove(os.path.join(self.data, "projections.csv"))
        runner = FakeRunner(effect=self._writer())
        res = self.refresh(runner=runner)
        self.assertEqual(res["status"], "refreshed")
        self.assertIsNone(res["age_hours"])
        self.assertEqual(len(runner.calls), 4)


class FailingStepTest(_Harness):
    """A failing step is a logged, returned error — the old CSV is never
    touched and no later step runs."""

    def setUp(self):
        super().setUp()
        self.old = NOW - 13 * 3600
        self.write_csv(rows=3, mtime=self.old)
        self.boot = self.write_snap("bootstrap", "bootstrap-20260822-0900.json",
                                    self.old)
        self.fix = self.write_snap("fixtures", "fixtures-20260822-0900.json",
                                   self.old)

    def _assert_error(self, res, runner, step):
        self.assertEqual(res["status"], "error")
        self.assertIn(step, res["reason"])
        ev = [e for e in self.events()
              if e["event"] == "projections_refresh_error"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["step"], step)

    def test_fetch_fails(self):
        runner = FakeRunner(results=((1, "boom: bad snapshot"),))
        res = self.refresh(runner=runner)
        self._assert_error(res, runner, "fetch")
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("boom", res["reason"])

    def test_csv_step_fails_after_a_good_fetch(self):
        runner = FakeRunner(results=((0, ""), (3, "distill failed")))
        res = self.refresh(runner=runner)
        self._assert_error(res, runner, "csv_bootstrap")
        self.assertEqual(len(runner.calls), 2)

    def test_projections_step_fails_last(self):
        runner = FakeRunner(results=((0, ""), (0, ""), (0, ""), (2, "pulp gone")))
        res = self.refresh(runner=runner)
        self._assert_error(res, runner, "projections")
        self.assertEqual(len(runner.calls), 4)

    def test_fetch_producing_no_snapshots_is_an_error(self):
        os.remove(self.boot)
        os.remove(self.fix)
        runner = FakeRunner()
        res = self.refresh(runner=runner)
        self._assert_error(res, runner, "snapshots")
        self.assertEqual(len(runner.calls), 1)

    def test_old_csv_untouched_on_error(self):
        before = self.csv_text()
        runner = FakeRunner(results=((1, "boom"),))
        self.refresh(runner=runner)
        self.assertEqual(self.csv_text(), before)

    def test_timeout_is_this_steps_error(self):
        runner = FakeRunner(raise_exc=subprocess.TimeoutExpired(cmd="python3",
                                                               timeout=600))
        res = self.refresh(runner=runner)
        self._assert_error(res, runner, "fetch")
        self.assertIn("TimeoutExpired", res["reason"])


# --- the `daemon refresh` subcommand ------------------------------------------

class _CmdHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = self._tmp.name
        self.data = os.path.join(self.d, "data")
        os.makedirs(self.data, exist_ok=True)

    def env(self, **over):
        e = {"GAFFER_ALLOWLIST_USER_IDS": "42",
             "TELEGRAM_BOT_TOKEN": "TT",
             "OPENROUTER_API_KEY": "KK",
             "GAFFER_DATA_DIR": self.data}
        e.update(over)
        return e

    def run_refresh(self, runner=None, clock=None, **env_over):
        out = io.StringIO()
        rc = run_refresh_cmd([], env=self.env(**env_over), transport=FakeTransport(),
                             out=out, runner=runner, clock=clock)
        line = next((l for l in out.getvalue().splitlines()
                     if l.startswith("refresh: ")), "")
        return rc, line, out


class RefreshCmdTest(_CmdHarness):
    """`daemon refresh` prints the one status line; exit 1 on error."""

    def _write(self, rows):
        path = os.path.join(self.data, "projections.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(HEADER + "".join(f"p{i},MID,{i},7.5\n" for i in range(rows)))
        return path

    def _snap(self, name):
        with open(os.path.join(self.data, name), "w", encoding="utf-8") as f:
            json.dump({"kind": "x"}, f)

    def test_fresh_line(self):
        self._write(3)                                    # just written -> fresh
        rc, line, _ = self.run_refresh(runner=FakeRunner())   # runner must not run
        self.assertEqual(rc, 0)
        self.assertEqual(line, "refresh: status=fresh age=0.0h rows=3")

    def test_refreshed_line(self):
        path = self._write(1)
        os.utime(path, (NOW - 13 * 3600,) * 2)
        self._snap("bootstrap-20260822-0900.json")
        self._snap("fixtures-20260822-0900.json")

        def effect(n):
            if n == 4:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(HEADER + "".join(f"p{i},MID,{i},7.5\n"
                                             for i in range(5)))

        rc, line, _ = self.run_refresh(runner=FakeRunner(effect=effect),
                                       clock=lambda: NOW)
        self.assertEqual(rc, 0)
        self.assertEqual(line, "refresh: status=refreshed age=13.0h rows=5")

    def test_error_line_and_rc(self):
        path = self._write(1)
        os.utime(path, (NOW - 13 * 3600,) * 2)
        rc, line, out = self.run_refresh(runner=FakeRunner(results=((1, "boom"),)),
                                         clock=lambda: NOW)
        self.assertEqual(rc, 1)
        self.assertTrue(line.startswith("refresh: status=error "))
        self.assertIn("projections_refresh_error", out.getvalue())


# --- the wake wiring: refresh runs before the wake's first LLM call -----------

EVENTS = [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z", "finished": True,
           "is_next": False},
          {"id": 2, "deadline_time": "2026-08-29T11:00:00Z", "finished": False,
           "is_next": True},
          {"id": 3, "deadline_time": "2026-09-04T17:30:00Z", "finished": False,
           "is_next": False}]

_PLAN = {"transfers_in": ["Saka"], "transfers_out": ["Gordon"], "hits": 0,
         "starting_xi": ["Raya", "Saka"], "captain": "Haaland", "vice": "Salah",
         "chip": None, "contingencies": []}
_DRAFT_REPLY = ("GW2 brief — roll FT, (C) Haaland.\n\n```plan\n"
                + json.dumps(_PLAN) + "\n```")


class _WakeHarness(_CmdHarness):
    """Env + minimal workspace for the brief/review cmd factories (same shape
    as test_review_cmd's harness)."""

    def setUp(self):
        super().setUp()
        self.state_path = os.path.join(self.d, "season-state.json")
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"season": "2026-27", "current_gw": 2,
                       "entry_id": None, "squad": {"picks": []}}, f)
        ws = os.path.join(self.d, "agent")
        for sub in ("playbooks", "memory"):
            os.makedirs(os.path.join(ws, sub), exist_ok=True)
        with open(os.path.join(ws, "GAFFER.md"), "w", encoding="utf-8") as f:
            f.write("PERSONA\n")
        for pb in ("deadline-brief", "deadline-final", "post-gw-review",
                   "analysis", "squad-review"):
            with open(os.path.join(ws, "playbooks", f"{pb}.md"), "w",
                      encoding="utf-8") as f:
                f.write(f"{pb} playbook\n")
        self.ws = ws

    def env(self, **over):
        e = super().env(**over)
        e.update({"GAFFER_STATE_PATH": self.state_path,
                  "GAFFER_REPORTS_DIR": os.path.join(self.d, "reports"),
                  "GAFFER_LEARNINGS_PATH": os.path.join(self.d, "learnings.md"),
                  "GAFFER_WORKSPACE_DIR": self.ws,
                  "GAFFER_APPROVAL_STATE_PATH": os.path.join(self.d, "approval.json"),
                  "GAFFER_PROJECTIONS_PATH": PROJ,
                  # Keep the brief's fan-out stubbed: the wake must still THINK
                  # (LLM calls) but the helpers add no calls of their own.
                  "GAFFER_LEDGER_SEARCH_OFF_USD": "0",
                  "GAFFER_LEDGER_HELPERS_OFF_USD": "0"})
        return e


class BriefCmdRefreshTest(_WakeHarness):
    """`daemon brief`: the refresh fires once, before the draft's first LLM
    call — a stale CSV must never reach the model."""

    def test_refresh_precedes_the_first_llm_call(self):
        transport = FakeTransport(llm_replies=[
            "internal plan (SELFTEST)", "AM: fine (SELFTEST)", _DRAFT_REPLY])
        at_refresh = []

        def refresh():
            at_refresh.append(len(transport.llm_requests))
            return {"status": "fresh", "age_hours": 1.0, "rows": 9, "reason": "test"}

        rc = run_brief_cmd(env=self.env(), transport=transport, out=io.StringIO(),
                           fetch=lambda: EVENTS, now=_dt("2026-08-28T12:00:00Z"),
                           sync=lambda gw: {"status": "current"}, refresh=refresh)
        self.assertEqual(rc, 0)
        self.assertEqual(at_refresh, [0])         # ran once, zero LLM calls so far
        self.assertTrue(transport.llm_requests)   # ...and the wake did think
        self.assertTrue(any("/sendMessage" in url for _, url in transport.requests))


class ReviewCmdRefreshTest(_WakeHarness):
    """`daemon review`: same ordering guarantee on the scoring wake."""

    def test_refresh_precedes_the_first_llm_call(self):
        transport = FakeTransport(llm_replies=[
            "GW2 review — decent.\n\n```learnings\n"
            '{"specific": [], "general": []}\n```'])
        at_refresh = []

        def refresh():
            at_refresh.append(len(transport.llm_requests))
            return {"status": "fresh", "age_hours": 1.0, "rows": 9, "reason": "test"}

        def fetch_actuals(gw):
            return {"live": {}, "picks": None, "players": {}}

        rc = run_review_cmd(env=self.env(), transport=transport,
                            out=io.StringIO(),
                            fetch_events=lambda: [dict(e, finished=e["id"] <= 2,
                                                       data_checked=e["id"] <= 2)
                                                  for e in EVENTS],
                            fetch_actuals=fetch_actuals, refresh=refresh)
        self.assertEqual(rc, 0)
        self.assertEqual(at_refresh, [0])
        self.assertTrue(transport.llm_requests)


if __name__ == "__main__":
    unittest.main()
