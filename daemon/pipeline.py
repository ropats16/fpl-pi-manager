"""Projection refresh (#78) — keep `data/projections.csv` young enough that
every gaffer wake reasons on current numbers, not pre-season ones.

Nothing in the daemon re-ran the math pipeline, so the Pi's projections.csv
went stale (dated 2026-08-22, pre-GW1: "Haaland 4.4 pts" in GW3). This module
re-runs the fetch -> csv -> projections steps of `run_pipeline.sh fetch` (never
the optimizer) and is called at the top of the two thinking wakes (`daemon
brief`, `daemon review`) before any LLM call. A fresh file costs nothing; a
stale one costs four subprocesses. The runner is an injectable
subprocess.run-shaped seam, so tests never fork a real process, and the whole
thing never raises — a failed refresh leaves the old CSV in place and the wake
proceeds on it.
"""

import glob
import os
import subprocess
import time

# A CSV younger than this is `fresh`; older (or missing) is worth a re-run.
MAX_AGE_HOURS = 12
# Each pipeline step gets 10 minutes: a hung fetch must not eat the wake.
STEP_TIMEOUT_S = 600


def _age_hours(path, now):
    """Hours since `path`'s mtime per the injected clock, or None if missing."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    return max((now() - mtime) / 3600.0, 0.0)


def _rows(path):
    """Data lines in a projections.csv (header excluded); None if unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            n = sum(1 for line in f if line.strip())
    except OSError:
        return None
    return max(n - 1, 0)


def _newest(paths):
    """The newest of a glob's hits (run_pipeline.sh's `ls -t | head -1`), or
    None when the glob matched nothing."""
    if not paths:
        return None
    return max(paths, key=lambda p: (os.path.getmtime(p), p))


def _tail(text, chars=200):
    """The last `chars` of a step's output, flattened to one log-safe line."""
    flat = " ".join((text or "").split())
    return flat[-chars:] if flat else "no output"


def _default_runner(argv, cwd, timeout):
    """The real subprocess.run, output captured so a failure can be named."""
    return subprocess.run(argv, cwd=cwd, timeout=timeout,
                          capture_output=True, text=True)


def _run_step(runner, repo_root, argv, step):
    """One pipeline step: None when it passed, else (step, reason)."""
    try:
        p = runner(argv, cwd=repo_root, timeout=STEP_TIMEOUT_S)
    except Exception as e:               # noqa: BLE001 — timeout/OSError is this step's failure
        return step, f"{step}: {type(e).__name__}: {e}"
    rc = getattr(p, "returncode", None)
    if rc != 0:
        out = getattr(p, "stderr", None) or getattr(p, "stdout", None) or ""
        return step, f"{step}: rc={rc}: {_tail(out)}"
    return None


def refresh_projections(repo_root, data_dir, logger, runner=None,
                        max_age_hours=MAX_AGE_HOURS, clock=None):
    """Refresh `data_dir/projections.csv` when it went stale; never raises.

    Returns {"status": "fresh" | "refreshed" | "error", "age_hours", "rows",
    "reason"}. `age_hours` is the CSV's age at the check (pre-refresh — the
    staleness that motivated the run; None when there was no file), `rows` the
    data-line count of the CSV on disk at return time.

    - `fresh`:    the CSV's mtime is younger than `max_age_hours` — no
                  subprocess runs.
    - `refreshed`: four steps ran in `repo_root` (run_pipeline.sh's fetch case):
                  `python3 fpl_api.py fetch --out <data_dir>`, then
                  `python3 fpl_api.py csv <snapshot> --out <data_dir>` for the
                  two newest snapshot JSONs the fetch produced, then
                  `python3 fpl_projections.py`. Never the optimizer.
    - `error`:    a step failed (or the fetch produced no snapshots); logged as
                  `projections_refresh_error` (step, reason), the old CSV left
                  untouched.

    `runner` is a subprocess.run-shaped seam (argv, cwd=, timeout=); `clock`
    returns epoch seconds. Logs `projections_refreshed` (rows, age_hours) on
    success — nothing on the fresh path — and never lets an error climb to the
    wake.
    """
    runner = _default_runner if runner is None else runner
    now = time.time if clock is None else clock
    proj = os.path.join(data_dir, "projections.csv")
    age = None
    try:
        age = _age_hours(proj, now)
        if age is not None and age < max_age_hours:
            return {"status": "fresh", "age_hours": age, "rows": _rows(proj),
                    "reason": f"projections.csv is {age:.1f}h old "
                              f"(max {max_age_hours:g}h)"}

        def settled(failure):
            """Close a failed refresh: log it, keep the old CSV, say why."""
            if failure is None:
                return None
            step, reason = failure
            logger.event("projections_refresh_error", step=step, reason=reason)
            return {"status": "error", "age_hours": age, "rows": _rows(proj),
                    "reason": reason}

        res = settled(_run_step(runner, repo_root,
                                ["python3", "fpl_api.py", "fetch", "--out", data_dir],
                                "fetch"))
        if res is None:
            boot = _newest(glob.glob(os.path.join(data_dir, "bootstrap-*.json")))
            fix = _newest(glob.glob(os.path.join(data_dir, "fixtures-*.json")))
            if boot is None or fix is None:
                res = settled(("snapshots", "fetch produced no bootstrap/fixtures "
                                           "snapshot json"))
        if res is None:
            res = settled(_run_step(runner, repo_root,
                                    ["python3", "fpl_api.py", "csv", boot,
                                     "--out", data_dir], "csv_bootstrap"))
        if res is None:
            res = settled(_run_step(runner, repo_root,
                                    ["python3", "fpl_api.py", "csv", fix,
                                     "--out", data_dir], "csv_fixtures"))
        if res is None:
            res = settled(_run_step(runner, repo_root,
                                    ["python3", "fpl_projections.py"],
                                    "projections"))
        if res is not None:
            return res

        rows = _rows(proj)
        logger.event("projections_refreshed", rows=rows, age_hours=age)
        return {"status": "refreshed", "age_hours": age, "rows": rows,
                "reason": f"stale {age:.1f}h >= {max_age_hours:g}h; "
                          "re-ran fetch, csv, projections"}
    except Exception as e:               # noqa: BLE001 — a refresh must never kill a wake
        reason = f"refresh: {type(e).__name__}: {e}"
        try:
            logger.event("projections_refresh_error", step="refresh", reason=reason)
        except Exception:                # noqa: BLE001 — logging must not raise either
            pass
        return {"status": "error", "age_hours": age, "rows": None, "reason": reason}
