"""The on-Pi engineer helper (spec §4–6) — turns an approved ticket into a PR.

`run_build` is the whole job: clone origin/main into a throwaway workspace on a
fresh `gaffer/build-N` branch, run a bounded `run_agent` tool loop (spec §1) that
reads and edits only inside that workspace, run the test suite, and open a PR
Rohit merges by hand — green as a normal PR (`Closes #N`), red as a draft. It
never merges and, like every helper, it never raises: any failure is a clean
`BuildResult(status="error")` with a reason, so a bad build degrades and the gate
recovers, it does not crash the child.

Guardrails (spec §5):
- the five workspace tools are rooted at the workspace; `write_file` is the only
  mutator and is doubly checked — `build.path_allowed` (the tier-1 writable set)
  PLUS a realpath check that the resolved destination stays inside the workspace,
  so neither a `..` nor a symlink already in the tree can escape. A refused write
  is a fixed tool result (counted as a turn, never a cap trip).
- BEFORE the push the REAL tree is re-checked (`host.status_paths`, a
  `git status --porcelain`), not just the files a tool claims to have written: a
  side-effect file (e.g. a test that drops `.github/workflows/x.yml`) that fails
  `path_allowed` aborts the build, and only the ACL-cleared paths are staged
  (`git add -- <paths>`, never a blanket `-A`).
- after a red `run_tests` the engineer may fix at most `fix_turns` times (a "fix"
  is a red run that follows at least one `write_file` since the previous red);
  the next counted red flips a switch that withholds further `write_file` AND
  hard-stops the loop (`run_agent`'s `stop=`), so it goes straight to finish
  instead of spinning to the turns cap.

The test child runs with a minimal explicit env (no service credentials) and its
returned tail is scrubbed of every configured secret before it can reach the
model, `res.tests_tail` or the PR body.

**Accepted risk (spec §5, #10 tiers):** the writable set includes `daemon/`
(so `build.py`'s own ACL lists) and `AGENTS.md` (whose head seeds this prompt) —
a build could open a PR that widens the ACL or rewrites the rules, but it cannot
merge, so a human review catches it before it lands.

Finish (spec §4): nothing changed → `error "no changes"`; the diff is re-checked
against the ACL; a non-*.py file under tests/ → `error "scratch file in tests"`,
a diff touching only tests/ → `error "tests only"` (the live-#78 shape: a
file-dump harness instead of a feature — `read_file` is paged for the same
reason); a final full `run_tests` decides green/red; then
`host.push_branch` + `host.create_pr(draft=not green)`. Events: `build_start`,
`build_tests` (green/red, n), `build_pr`, `build_fail`.
"""

import glob as _glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from datetime import datetime, timezone

from daemon.agent import Tool, run_agent
from daemon.build import (DENIED, REPO_ROOT, WRITABLE_DIRS, WRITABLE_FILES,
                          path_allowed)
from daemon.prompt import char_budget

# The Pi's full suite is ~2s (spec §4); a 10-min ceiling is a runaway guard only.
TEST_TIMEOUT = 600
READ_MAX_TOKENS = 4000          # a read is bounded so one big file can't blow context
READ_MAX_LINES = 200            # …and paged: read_file(path, start_line=, max_lines=)
GREP_MAX_HITS = 60
LIST_MAX = 400
TESTS_TAIL_LINES = 60           # `run_tests` returns pass/fail + this many tail lines

# The writable / denied set, described from build.py's own lists (one source of
# truth — the ACL and the persona can never drift apart).
_WRITABLE_DESC = ", ".join(list(WRITABLE_DIRS) + list(WRITABLE_FILES)
                           + ["root *.py"]) + " (never agent/roles/engineer.md)"
_DENIED_DESC = ", ".join(DENIED) + ", any dotfile, `..`, absolutes"

# The repo rules that ride in the system prompt (spec §4). `run_build_cmd` passes
# these as `repo_rules`; kept here so the persona and the rules live together.
REPO_RULES = (
    "## Repo rules (tier-1, enforced by the daemon)\n\n"
    "- **Stdlib only.** No pip, no third-party imports — this runs on a Pi 4B.\n"
    "- **Tests first (TDD).** Add or extend a failing test under `tests/` BEFORE "
    "the implementation, then make it pass. Every external is faked at the "
    "HTTP/subprocess edge — never hit the network or fork a real subprocess in a "
    "test.\n"
    "- **The whole suite must be green.** Run it with `run_tests()` — that is "
    "`python3 -W error::ResourceWarning -m unittest discover -s tests -t .`.\n"
    "- **Smallest diff** that satisfies the issue. Read a file before you edit it "
    "— `read_file` is paged (`start_line`, `max_lines`); page through a big file, "
    "never copy it anywhere.\n"
    f"- You may write ONLY inside the writable set: {_WRITABLE_DESC}. Every other "
    f"path is denied ({_DENIED_DESC}) and a `write_file` there is refused.\n"
    "- **No scratch files.** Under `tests/` only `*.py` test modules are accepted, "
    "and a test must test the feature — a test that dumps, copies or prints "
    "source is not a test. A build whose diff touches only `tests/` (no "
    "implementation) is refused at the finish line, as is any non-.py file left "
    "under `tests/`.\n"
    "- When the fix budget is spent, stop and summarise — do not keep editing.")

# The fixed tool results (spec §4/§5). Refusals are counted as a turn, never a cap
# trip; the fix-budget line withholds further writes.
_DENIED_MSG = ("write_file refused: {rel} is outside the writable set "
               f"({_WRITABLE_DESC}) — pick a writable path.")
_ESCAPE = "write_file refused: {rel} resolves outside the workspace."
_SCRATCH_MSG = ("write_file refused: {rel} — only *.py test modules may be written "
                "under tests/; no scratch, dump or data files (live build #78 "
                "shipped a tests/_d*.txt file-reading harness instead of code).")
_EXHAUSTED = ("write_file refused: the fix budget is spent — stop and summarise "
              "what you changed and why the tests still fail; no further edits "
              "will be accepted.")

Issue = namedtuple("Issue", "number title body")


def scratch_in_tests(paths):
    """The first path under tests/ that is not a *.py module, or None. A test
    that writes such a file (a source dump, a chunk, a data file) is the live
    build #78 exploit (closed PR #80); the finish line refuses the whole build
    on it. Shape-specific: a dump written as *.py, or under daemon/ or docs/,
    is caught only by the role prompt and the human PR review."""
    for p in sorted(paths):
        if p.startswith("tests/") and not p.endswith(".py"):
            return p
    return None


def tests_only(paths):
    """True when every changed path lives under tests/ — a build with no
    implementation (the live-#78 shape) is refused at the finish line. A
    legitimate test-only ticket is refused too; that trade-off is deliberate
    until one is actually needed."""
    paths = list(paths)
    return bool(paths) and all(p.startswith("tests/") for p in paths)


class BuildResult:
    """The outcome of one `run_build` (spec §4). `status` is green | red | error;
    `pr_url` is set for green/red; `reason` names an error; `tests_tail` is the
    last (scrubbed) lines of the final test run."""

    __slots__ = ("status", "pr_url", "reason", "turns", "cost_usd", "tests_tail")

    def __init__(self, status="error", pr_url=None, reason=None, turns=0,
                 cost_usd=0.0, tests_tail=""):
        self.status = status
        self.pr_url = pr_url
        self.reason = reason
        self.turns = turns
        self.cost_usd = cost_usd
        self.tests_tail = tests_tail


def prune_work(data_dir, days=7, now=None):
    """Delete `data/work/build-*` workspaces older than `days` (spec §4: the
    workspace is kept for post-mortem but pruned at the next job start). Never
    raises — a prune failure must not block a build."""
    work = os.path.join(data_dir, "work")
    if not os.path.isdir(work):
        return
    now = time.time() if now is None else now
    cutoff = now - days * 86400
    for name in os.listdir(work):
        if not name.startswith("build-"):
            continue
        p = os.path.join(work, name)
        try:
            if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def _tail_lines(text, n):
    return "\n".join((text or "").splitlines()[-n:])


def _build_test_env(workspace, home):
    """A minimal, explicit env for the test child (spec §5): PATH, the workspace
    on PYTHONPATH, an ephemeral HOME, and locale — and NOTHING inherited, so no
    GitHub / OpenRouter / Telegram credential ever reaches an engineer-written
    test."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": workspace,
        "HOME": home,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }


def _default_test_runner(workspace, paths):
    """Run the suite (or the given `paths`) in the workspace under
    `-W error::ResourceWarning` with a minimal env (no inherited secrets); return
    (passed, tail-of-output). Injectable so the test suite never forks a real
    subprocess (AGENTS.md rule)."""
    home = tempfile.mkdtemp(prefix="build-home-")
    argv = [sys.executable, "-W", "error::ResourceWarning", "-m", "unittest"]
    argv += list(paths) if paths else ["discover", "-s", "tests", "-t", "."]
    try:
        p = subprocess.run(argv, cwd=workspace, capture_output=True, text=True,
                           timeout=TEST_TIMEOUT, env=_build_test_env(workspace, home))
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, _tail_lines(out, TESTS_TAIL_LINES)
    except subprocess.TimeoutExpired:
        return False, f"run_tests: timed out after {TEST_TIMEOUT}s"
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _read_head(path, max_chars):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            t = f.read()
    except OSError:
        return ""
    return t if len(t) <= max_chars else t[:max_chars] + "\n…(truncated)"


def _system_prompt(issue, repo_rules):
    """Persona + AGENTS.md head + repo rules + the issue (spec §4). The persona
    and conventions are read fresh from the running daemon's own tree (REPO_ROOT)
    — the engineer's role file is not in the origin/main clone until this PR
    lands, so it must not come from the workspace."""
    role = _read_head(os.path.join(REPO_ROOT, "agent", "roles", "engineer.md"), 8000)
    agents = _read_head(os.path.join(REPO_ROOT, "AGENTS.md"), 6000)
    parts = [
        role or "You are the gaffer's engineer: a careful technical assistant.",
        "## AGENTS.md (repo conventions — head)\n\n" + agents,
        repo_rules or REPO_RULES,
        f"## The ticket — issue #{issue.number}: {issue.title}\n\n"
        + (issue.body or "").strip(),
    ]
    return "\n\n".join(p for p in parts if p)


def _pr_body(issue, tests_tail, turns, cost_usd, green):
    """The PR body (spec §4): the spec, the (scrubbed) test tail, turns/cost, and
    `Closes #N` only when green (a draft red PR must not auto-close the issue)."""
    lines = [
        f"Build of issue #{issue.number}: {issue.title}", "",
        "## Spec", "", (issue.body or "").strip(), "",
        "## Test run (final)", "", "```", (tests_tail or "").strip() or "(no output)",
        "```", "",
        f"turns: {turns} · est. cost: ${cost_usd:.4f}", "",
        "Opened by the on-Pi engineer (spec §4). Merge is human — the pull lands it.",
    ]
    if green:
        lines += ["", f"Closes #{issue.number}"]
    return "\n".join(lines)


def _new_state():
    """The per-build tool state shared across the workspace tools: which relpaths
    were written, the run/red counters, whether a write has landed since the last
    red (so a fix is only counted once per real edit), and the fix-budget switch
    (which also hard-stops the loop)."""
    return {"written": set(), "reds": 0, "runs": 0, "wrote_since_red": False,
            "exhausted": False}


def _build_tools(issue, root, state, fix_turns, test_runner, logger, scrub=None):
    """The five workspace tools (spec §4), all rooted at `root` (the realpath of
    the workspace). `scrub` redacts secrets from the test tail before it reaches
    the model."""
    scrub = scrub or (lambda t: t)

    def _resolve(rel):
        """(abspath, None) when `rel` resolves inside the workspace; (None, why)
        otherwise. Catches a `..` and, crucially, a symlink already in the tree
        that a lexical check (path_allowed) cannot see (spec §5)."""
        dest = os.path.realpath(os.path.join(root, rel))
        if dest == root or dest.startswith(root + os.sep):
            return dest, None
        return None, "escapes the workspace"

    def _inside(p):
        rp = os.path.realpath(p)
        return rp == root or rp.startswith(root + os.sep)

    def _iter_files(pattern):
        for p in sorted(_glob.glob(os.path.join(root, pattern), recursive=True)):
            if not (_inside(p) and os.path.isfile(p)):
                continue
            rel = os.path.relpath(os.path.realpath(p), root)
            if rel == ".git" or rel.startswith(".git" + os.sep):
                continue
            yield rel, os.path.realpath(p)

    def list_files(glob=None, **_):
        pattern = (glob or "**/*").strip() or "**/*"
        rels = sorted({rel for rel, _ in _iter_files(pattern)})
        if not rels:
            return f"list_files: no files match {pattern!r}."
        extra = "" if len(rels) <= LIST_MAX else f"\n…(+{len(rels) - LIST_MAX} more)"
        return "\n".join(rels[:LIST_MAX]) + extra

    def read_file(path=None, start_line=None, max_lines=None, **_):
        rel = (path or "").strip()
        if not rel:
            return "read_file: give a path."
        try:
            start = max(1, int(start_line or 1))
            span = max(1, min(int(max_lines or READ_MAX_LINES), READ_MAX_LINES))
        except (TypeError, ValueError):
            return "read_file: start_line and max_lines must be integers."
        dest, why = _resolve(rel)
        if why:
            return f"read_file refused: {rel} {why}."
        rel_real = os.path.relpath(dest, root)
        if rel_real == ".git" or rel_real.startswith(".git" + os.sep):
            return f"read_file refused: {rel} is inside .git."
        if not os.path.isfile(dest):
            return f"read_file: no file at {rel}."
        try:
            with open(dest, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            return f"read_file: {type(e).__name__}: {e}"
        total = len(lines)
        if total == 0:
            return f"read_file: {rel} is empty (0 lines)."
        if start > total:
            return f"read_file: start_line={start} is past the end ({total} lines)."
        # Emit whole lines up to the page span AND the token budget, so the
        # trailer's range is exactly what was shown — a budget-cut page must
        # not claim lines it never emitted (the next start_line would skip them).
        budget = char_budget(READ_MAX_TOKENS)
        out, used, end = [], 0, start - 1
        for line in lines[start - 1:start - 1 + span]:
            if out and used + len(line) > budget:
                break
            out.append(line[:budget] if len(line) > budget else line)
            used += len(out[-1])
            end += 1
        page = "".join(out)
        if start == 1 and end == total:
            return page                                   # the whole file, no noise
        hint = (f"\n…(lines {start}–{end} of {total}; call read_file(path, "
                f"start_line={end + 1}) for the next page)" if end < total
                else f"\n…(lines {start}–{end} of {total}; end of file)")
        return page + hint

    def grep(pattern=None, glob=None, **_):
        pat = (pattern or "").strip()
        if not pat:
            return "grep: give a pattern."
        try:
            rx = re.compile(pat)
        except re.error as e:
            return f"grep: bad pattern: {e}"
        g = (glob or "**/*.py").strip() or "**/*.py"
        hits = []
        for rel, real in _iter_files(g):
            try:
                with open(real, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            hits.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                            if len(hits) >= GREP_MAX_HITS:
                                return "\n".join(hits) + "\n…(truncated)"
            except OSError:
                continue
        return "\n".join(hits) if hits else f"grep: no matches for {pat!r} in {g}."

    def write_file(path=None, content=None, **_):
        rel = (path or "").strip()
        if not rel:
            return "write_file: give a path."
        if state["exhausted"]:
            return _EXHAUSTED
        if not path_allowed(rel):
            return _DENIED_MSG.format(rel=rel)
        if scratch_in_tests([rel]):
            return _SCRATCH_MSG.format(rel=rel)
        dest, why = _resolve(rel)
        if why:
            return _ESCAPE.format(rel=rel)
        try:
            os.makedirs(os.path.dirname(dest) or root, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content or "")
        except OSError as e:
            return f"write_file: {type(e).__name__}: {e}"
        state["written"].add(rel)
        state["wrote_since_red"] = True     # a red run after this counts as a fix
        return f"wrote {rel} ({len(content or '')} bytes)."

    def run_tests(paths=None, **_):
        plist = _norm_paths(paths)
        passed, tail = test_runner(root, plist)
        tail = scrub(tail)
        state["runs"] += 1
        logger.event("build_tests", issue=issue.number,
                     result="green" if passed else "red", n=state["runs"])
        if passed:
            return "run_tests: GREEN — all tests passed.\n\n" + tail
        if not state["wrote_since_red"]:
            # A red run with no intervening edit is the same failure — do not spend
            # a fix on it; tell the engineer to actually change something.
            return ("run_tests: RED (no file changed since the last run — edit a "
                    "file, then re-run).\n\n" + tail)
        state["reds"] += 1
        state["wrote_since_red"] = False
        if state["reds"] > fix_turns:
            state["exhausted"] = True       # withholds writes AND hard-stops the loop
            return (f"run_tests: RED. The fix budget ({fix_turns}) is spent — stop "
                    "and summarise; no further edits will be accepted.\n\n" + tail)
        return (f"run_tests: RED (fix {state['reds']} of {fix_turns} — read the "
                "failure, make the smallest fix, and re-run).\n\n" + tail)

    return [
        Tool("list_files", "List workspace files matching a glob (e.g. 'daemon/*.py', "
             "'**/*.py'). Defaults to everything.",
             {"type": "object", "properties": {"glob": {"type": "string"}},
              "required": []}, list_files),
        Tool("read_file", "Read one file in the workspace, paged: up to "
             f"{READ_MAX_LINES} lines per call from start_line (default 1). A big "
             "file tells you the next start_line — page through it, never copy it.",
             {"type": "object", "properties": {
                 "path": {"type": "string"},
                 "start_line": {"type": "integer"},
                 "max_lines": {"type": "integer"}},
              "required": ["path"]}, read_file),
        Tool("grep", "Search workspace files (glob defaults to '**/*.py') for a regex; "
             "returns matching path:line: text.",
             {"type": "object", "properties": {
                 "pattern": {"type": "string"}, "glob": {"type": "string"}},
              "required": ["pattern"]}, grep),
        Tool("write_file", "Create or overwrite a file in the workspace, whole content "
             "at once. Only writable-set paths are accepted (see the repo rules).",
             {"type": "object", "properties": {
                 "path": {"type": "string"}, "content": {"type": "string"}},
              "required": ["path", "content"]}, write_file),
        Tool("run_tests", "Run the suite (or the given space-separated paths) under "
             "-W error::ResourceWarning; returns pass/fail and the last lines. Add "
             "tests first, then make them pass.",
             {"type": "object", "properties": {"paths": {"type": "string"}},
              "required": []}, run_tests),
    ]


def _norm_paths(paths):
    if not paths:
        return None
    parts = paths.split() if isinstance(paths, str) else [str(p) for p in paths]
    return [p for p in parts if p] or None


def run_build(issue, host, llm, model, caps, fix_turns, data_dir, repo_rules,
              logger, clock=None, test_runner=None):
    """Build issue #N end to end (spec §4). Returns a BuildResult; never raises."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    test_runner = test_runner or _default_test_runner
    scrub = getattr(logger, "scrub", None) or (lambda t: t)
    res = BuildResult()
    n = issue.number
    branch = f"gaffer/build-{n}"
    workspace = os.path.join(data_dir, "work", f"build-{n}")
    logger.event("build_start", issue=n, branch=branch, model=model)

    def fail(reason):
        res.status = "error"
        res.reason = reason
        logger.event("build_fail", issue=n, reason=reason[:300])
        return res

    try:
        prune_work(data_dir)

        # A fresh workspace: drop any stale dir from a prior attempt, then clone.
        try:
            if os.path.exists(workspace):
                shutil.rmtree(workspace, ignore_errors=True)
            os.makedirs(os.path.dirname(workspace), exist_ok=True)
            host.clone(workspace, branch)
        except Exception as e:              # noqa: BLE001 — a clone fail is a clean error
            return fail(f"clone failed: {type(e).__name__}: {e}")

        root = os.path.realpath(workspace)
        state = _new_state()
        tools = _build_tools(issue, root, state, fix_turns, test_runner, logger,
                             scrub=scrub)
        messages = [
            {"role": "system", "content": _system_prompt(issue, repo_rules)},
            {"role": "user", "content": f"Implement issue #{n}. Add tests first."},
        ]
        # The spent fix budget hard-stops the loop (spec §4): no read/grep/run_tests
        # spinning on to the turns cap once there is nothing left to write.
        agent = run_agent(messages, llm, model, tools, caps, logger,
                          role="engineer", clock=clock,
                          stop=lambda: state["exhausted"])
        res.turns = agent.turns
        res.cost_usd = agent.cost_usd

        # Re-check the REAL worktree against the ACL, not just tool-claimed writes:
        # a side-effect file the tools never saw must not ride to the branch.
        try:
            tree = host.status_paths(workspace)
        except Exception as e:              # noqa: BLE001 — a status fail is a clean error
            return fail(f"status check failed: {type(e).__name__}: {e}")
        if not tree:
            return fail("no changes")
        denied = sorted(p for p in tree if not path_allowed(p))
        if denied:
            return fail(f"denied path in tree: {denied[0]}")
        # The #80 shape: a harness instead of a feature. No implementation, or a
        # non-.py file under tests/ (a dump a test left behind), never ships.
        scratch = scratch_in_tests(tree)
        if scratch:
            return fail(f"scratch file in tests: {scratch}")
        if tests_only(tree):
            return fail("tests only — no implementation in the diff")

        # A final full-suite run decides green vs red.
        try:
            passed, tail = test_runner(root, None)
        except Exception as e:              # noqa: BLE001 — a runner blow-up is a clean error
            return fail(f"final run_tests failed: {type(e).__name__}: {e}")
        tail = scrub(tail)
        res.tests_tail = tail
        logger.event("build_tests", issue=n, result="green" if passed else "red",
                     n=state["runs"] + 1, final=True)

        title = issue.title
        body = _pr_body(issue, tail, agent.turns, agent.cost_usd, green=passed)
        try:
            host.push_branch(workspace, branch, f"{title} (#{n})", paths=tree)
            pr_url = host.create_pr(branch, title, body, draft=not passed)
        except Exception as e:              # noqa: BLE001 — a push/PR fail is a clean error
            return fail(f"push/PR failed: {type(e).__name__}: {e}")

        res.status = "green" if passed else "red"
        res.pr_url = pr_url
        logger.event("build_pr", issue=n, status=res.status, url=pr_url,
                     draft=not passed)
        return res
    except Exception as e:                  # noqa: BLE001 — a build never crashes the child
        return fail(f"unexpected: {type(e).__name__}: {e}")
