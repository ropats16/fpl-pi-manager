# Gaffer tooling + engineer helper (spec, 2026-09-04)

Decided with Rohit 2026-09-04 (this chat). Goal: the gaffer works like a real
manager — reads data, asks a staff member a question, commissions work, checks
progress — and an on-Pi **engineer** helper (glm-5.3-flash) turns an approved
ticket into a PR. Merge stays human (Rohit + Claude). Nothing here widens the
gaffer's write rights to daemon code, config, allowlist or credentials (#10 tiers).

## 0. Decisions (locked)

- Builder = on-Pi flash helper inside the daemon, ≤2 test-fix turns, red → draft PR.
- Gaffer gets tools in chat, incl. search/fetch (same allowlist/scrub as analysts),
  told to delegate first.
- Build trigger is event-driven: Rohit's `build #N` in Telegram spawns the job
  immediately. No polling.
- Build approval token is never a bare `yes` (that approves a plan).
- One pending build, one running build at a time. Merge is never automatic.

## 1. Shared tool-loop core — `daemon/agent.py` (PR 1)

Generalise `helper.run_helper`'s tool loop so chat, helpers and the engineer share it.

```
class Tool:              # one callable the model may invoke
    name, description, parameters (JSON-schema dict), fn(**kwargs) -> str,
    cap: int | None      # max calls per run; over cap -> fixed "cap hit" tool result, counted
class Caps: turns, minutes, cost_usd
class AgentResult: reply (str), turns, tool_calls {name: n}, cost_usd, started, finished,
                   status in {"ok", "cap_hit:turns", "cap_hit:minutes", "cap_hit:cost", "error"}
run_agent(messages, llm, model, tools, caps, logger, role, clock=None) -> AgentResult
```
- `messages` = pre-assembled list (system + user…); the loop appends assistant/tool turns.
- No tools → plain `llm.complete`, single turn (today's chat path, unchanged behaviour).
- Never raises; on cap/error the last assistant text (or a fixed line) is the reply.
- Every LLM call logs `llm_call` with `role` as today; cost is ledger-counted via `llm.cost_usd`.
- `run_helper` is refactored onto `run_agent` with **HelperResult and all helper tests unchanged**.

## 2. Gaffer chat tools — `daemon/gaffer_tools.py` (PR 1)

`build_gaffer_tools(cfg, workspace_root, state_path, reports_dir, projections_path, gw,
fetcher, searcher, helper_runner, host) -> list[Tool]`

| tool | args | does | cap/wake |
|---|---|---|---|
| `ask_helper` | role ∈ HELPER_ROLES−{engineer}, question | one flash turn of that role with `task=question`; returns its text; also appends `### <ts> — <role> (asked)` to the role's GW report | 2 |
| `read_report` | role, gw? | the report file text (head-capped 1500 tok) | 6 |
| `read_projections` | name | rows for that player from projections.csv (all GWs) | 6 |
| `fpl_lookup` | kind ∈ {player, team, fixtures}, name | structured from public FPL API via fetcher (bootstrap cached per wake) | 6 |
| `search` | query | Exa, as analysts | 3 |
| `fetch` | url | allowlisted fetch, as analysts | 5 |
| `open_ticket` | title, body | `host.open_issue(title, body, labels=["gaffer"])` → "#N url" | 1 |
| `ticket_status` | number | `host.issue_status(n)` (state, title, labels, last comment) | 4 |
| `pr_status` | number | `host.pr_status(n)` (state, draft, checks, mergeable) | 4 |

Chat caps (config, tier-1): `GAFFER_CHAT_MAX_TURNS=12`, `GAFFER_CHAT_MAX_MINUTES=6`,
`GAFFER_CHAT_MAX_COST_USD=0.40`. Tools absent (no host / no key) are simply not offered.
`loop.process_message`: `reply = llm.complete(messages)` becomes
`run_agent(messages, …, tools=gaffer_tools, caps=chat_caps).reply` when tools are wired;
plan / learnings / propose / build post-processing parse that final reply exactly as today.
GAFFER.md gains a "Your tools" section: delegate first, search only when no seat covers it.

## 3. Commissioning + approval gate — `daemon/build.py` (PR 2)

Build block, at the end of a gaffer reply (stripped before Telegram, like ```propose):
```
```build
ticket: new | <number>
title: <short imperative>
---
<spec markdown: goal, expected files, acceptance criteria, tests to add>
```
```
Daemon on block: `ticket: new` → `host.open_issue(title, spec, labels=["gaffer","build"])`;
store `pending_build = {issue, title, spec, queued_at}` in approval-state (`ApprovalStore`
gains `pending_build`, `running_build`; both `None` in `_IDLE`); reply line
`🔧 build #N queued — say "build #N" to start`. An unrequested second block while one is
pending is dropped with `⛔ a build is already pending (#N)`.

Deterministic gate in `process_message`, **after** the plan gate, no model call:
- `build #N` / `build` (when exactly one pending) → `spawn_build(N)`; `running_build =
  {issue, pid, started_at}`; reply `🔧 build #N started`.
- `cancel build` → clears pending (and kills a running pid) → `⏹ build #N cancelled`.
- `build #N` with a running build → `⛔ build #M running — wait or "cancel build"`.

`spawn_build(N)`: `subprocess.Popen([sys.executable, "-m", "daemon", "build", str(N)],
start_new_session=True, stdout/stderr → data/work/build-N.log, env=os.environ)`. Same
user, same env file, same systemd sandbox (child of the service). Known limit: a
pull-reload restart kills a running build; on daemon start a `running_build` whose pid is
dead is cleared with a Telegram line `⚠ build #N died with the daemon restart — say "build #N"
to retry`.

`daemon build N` command (`__main__.run_build_cmd`): loads config, fetches the issue body
via host, runs the engineer (PR 3), sends the Telegram receipt, exits 0/1. In PR 2 the
engineer is a stub that fails cleanly (`status=error reason=engineer not wired`).

## 4. Engineer helper — `daemon/engineer.py` + `agent/roles/engineer.md` (PR 3)

- Workspace: `host.clone(dest=data/work/build-N/)` (fresh clone of origin/main, branch
  `gaffer/build-N`). Directory kept for post-mortem; `prune_work(days=7)` runs at job start.
- System prompt: role file + `AGENTS.md` head + repo rules (stdlib only, TDD, test command)
  + the issue title/body. User task: "Implement issue #N. Add tests first."
- Tools (all rooted at the workspace, all ACL-checked):
  `list_files(glob)`, `read_file(path)`, `grep(pattern, glob)`, `write_file(path, content)`,
  `run_tests(paths=None)` → `python3 -W error::ResourceWarning -m unittest …`, 10-min
  timeout, returns tail 60 lines + pass/fail. Suite is ~2 s on the Pi (measured
  2026-09-04), so the full suite runs on every `run_tests()` call with no paths.
- Loop: `run_agent` with caps `GAFFER_BUILD_MAX_TURNS=40`, `GAFFER_BUILD_MAX_MINUTES=25`,
  `GAFFER_BUILD_MAX_COST_USD=0.60`; the engineer may call `run_tests` and fix at most
  `GAFFER_BUILD_FIX_TURNS=2` times after a red run (3rd red ends the loop).
- Finish: diff re-checked against the ACL; `host.push_branch(workdir, branch, message)`;
  `host.create_pr(branch, title, body, draft=not green)`. PR body = spec + test tail +
  turns/cost + `Closes #N` (green only). Telegram: `✅ build #N → PR <url>` or
  `🟥 build #N red → draft PR <url>` or `❌ build #N failed: <reason>`.
- Events: `build_start`, `build_tests` (green/red, n), `build_pr`, `build_fail`. Ledger role
  `engineer`. Model: `GAFFER_HELPER_MODEL_ENGINEER` (default `HELPER_MODEL`), `engineer`
  added to `HELPER_ROLES` (the fan-out uses `fanout.ANALYSTS`, so it is not run weekly).
- Selftest gains `engineer=PASS` (fake host + fake LLM, one write + one green test run).

## 5. Path ACL (tier-1, `daemon/build.py`)

Writable: `daemon/`, `tests/`, `agent/roles/` (except `engineer.md`), `agent/playbooks/`,
`docs/`, `plans/`, `README.md`, `AGENTS.md`, root `*.py`.
Denied: `deploy/`, `.github/`, `season-state.json`, `agent/memory/`, `agent/reports/`,
`agent/roles/engineer.md`, `data/`, `fixtures/`, any dotfile/dotdir, anything outside
the workspace (`..`, symlinks). `write_file` refuses with a fixed message (counted, never a
cap trip); the PR step refuses to push if the diff touches a denied path.

## 6. Git host additions (`daemon/propose.py`, PR 2 + PR 3)

`GhGitHost` / `FakeGitHost` both gain: `open_issue(title, body, labels) -> (number, url)`,
`issue_status(n) -> str`, `issue_body(n) -> (title, body)`, `pr_status(n) -> str`,
`clone(dest, branch) -> None`, `push_branch(workdir, branch, message) -> None`,
`create_pr(branch, title, body, draft=False) -> url`. All via `gh`/`git` subprocesses with
the token only in the child env, scrubbed from logs; `SUBPROCESS_TIMEOUT` as today.

## 7. Step 0 — tests must not read the tracked root `season-state.json` (PR 0)

On the Pi worktree (state rolled to GW3) 7 tests fail: `test_prompt.SeasonSnapshotTest` ×2,
`test_sync.SeasonSyncTest` ×3, `test_helper_cmd` ×1, `test_scout_cmd` ×1. Each must take
its state from a fixture/tmp file. No production code change.

## 8. Tests (all PRs)

Fake LLM with scripted tool_calls, `FakeGitHost`, fake fetcher/searcher. Cover: run_agent
caps + status; helper tests unchanged after refactor; each gaffer tool + per-wake caps;
build block parse/strip; `build #N` vs plan `yes` separation; pending/running state
machine incl. dead-pid recovery; spawn argv; ACL refusals incl. `..`; red→draft, green→PR
with `Closes #N`; fix-turn cap; selftest `engineer=PASS`.

## 9. Rollout

PR 0 (fixtures) ∥ PR 1 (agent core + chat tools) ∥ PR 2 (build block, gate, host
issue/PR ops, build cmd stub) → PR 3 (engineer) → deploy → first real job: "re-run the
projection pipeline before each brief/review wake" (Pi's `projections.csv` is dated
2026-08-22) → second job: TC window model (`fpl_tc_window.py`, Poisson from odds + xG,
player share, P(60+ min), GW3–19 table).

## Unresolved

- Build job dies on pull-reload restart: accept for v1 (retry by hand) or gate the pull
  timer while `running_build` is set?
- `ask_helper` appends to the role's GW report (write-once file today) — append section ok?
