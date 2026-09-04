"""Entrypoint. `python3 -m daemon` runs the resident loop; `... selftest` drives
one full message->reply loop offline with every external faked (no network)."""

import io
import json
import os
import shutil
import sys
import tempfile

import fpl_api
from datetime import datetime, timezone

from daemon.actuator import ManualApplyActuator
from daemon.brief import next_deadline, run_brief
from daemon.config import Config, load_config, load_notify_config
from daemon.helper import REPORT_CAP_TOKENS, ROLE_FILES, run_helper
from daemon.http import FakeTransport, UrllibTransport, tool_call_message
from daemon.learnings import LearningsLog
from daemon.llm import DEFAULT_BASE_URL
from daemon.logging_setup import StructuredLogger
from daemon.loop import poll_once, run
from daemon.plan import ApprovalGate, ApprovalStore
from daemon.prompt import Assembler, estimate_tokens
from daemon.propose import FakeGitHost, Proposal, make_proposer, run_propose
from daemon.reports import ReportWriter
from daemon.review import ReviewStore, run_review
from daemon.runtime import build_git_host, build_helper_tools, build_stack
from daemon.telegram import Telegram
from daemon.watch import run_watch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _approval_state_path(env):
    return env.get("GAFFER_APPROVAL_STATE_PATH",
                   os.path.join(REPO_ROOT, "data", "approval-state.json"))


def _state_path(env):
    return env.get("GAFFER_STATE_PATH",
                   os.path.join(REPO_ROOT, "season-state.json"))


def _reports_dir(env):
    return env.get("GAFFER_REPORTS_DIR",
                   os.path.join(REPO_ROOT, "agent", "reports"))


def _data_dir(env):
    """The gitignored machine-state dir: watch baseline, approval state, the
    review state + the brief's projection snapshots all live here."""
    return env.get("GAFFER_DATA_DIR", os.path.join(REPO_ROOT, "data"))


def _projections_path(env):
    """The pipeline's long-format projections.csv (gitignored data/)."""
    return env.get("GAFFER_PROJECTIONS_PATH",
                   os.path.join(REPO_ROOT, "data", "projections.csv"))


def _learnings_path(env):
    """The #20 diary. Repo content (unlike the gitignored state files): it is the
    record of what the gaffer learned. Rohit reviews it in the repo; the per-wake
    auto-commit of tier-3 writes is the #11 deploy machinery, not wired yet."""
    return env.get("GAFFER_LEARNINGS_PATH",
                   os.path.join(REPO_ROOT, "agent", "memory", "learnings.md"))


def build_assembler(env=None, approval_store_path=None):
    """Wire the prompt assembler from repo-relative paths (env-overridable so the
    Pi clone can point elsewhere). Context is assembled from these files at
    runtime — a pull that updates the markdown applies on the next wake (#7).
    When `approval_store_path` is set, a live pending/approved plan grounds
    debate replies (#18); the learnings diary feeds the same prompt a bounded
    slice of what past analyses taught (#20)."""
    env = os.environ if env is None else env
    workspace = env.get("GAFFER_WORKSPACE_DIR", os.path.join(REPO_ROOT, "agent"))
    state = _state_path(env)
    return Assembler(workspace, state, projections_path=_projections_path(env),
                     approval_store_path=approval_store_path,
                     learnings_path=_learnings_path(env))


def run_daemon(env=None, out=None):
    out = sys.stderr if out is None else out
    env = os.environ if env is None else env
    cfg = load_config(env)
    telegram, llm, logger = build_stack(cfg, UrllibTransport(), out)
    approval_path = _approval_state_path(env)
    approvals = ApprovalGate(ApprovalStore(approval_path),
                             reports_dir=_reports_dir(env))
    assembler = build_assembler(env, approval_store_path=approval_path)
    # The diary the reply loop appends to (#20) is the same file the assembler
    # reads, so a lesson recorded on one wake is on the table for the next.
    learnings = LearningsLog(_learnings_path(env), state_path=_state_path(env))
    # #55: `propose role: X` in chat -> the one propose path (real git/gh runner
    # when the GitHub token is provisioned; a "no token" reply otherwise).
    proposer = make_proposer(build_git_host(cfg, REPO_ROOT), logger)
    run(cfg, telegram, llm, logger, assembler=assembler, approvals=approvals,
        learnings=learnings, proposer=proposer)
    return 0


def _update(update_id, text):
    return {
        "update_id": update_id,
        "message": {"message_id": update_id, "from": {"id": 42},
                    "chat": {"id": 42, "type": "private"}, "text": text},
    }


# Turn 1 of the selftest: the canned analysis reply ends with the learnings block
# the analysis playbook asks for — one specific, one general (#20).
_SELFTEST_LEARNINGS_REPLY = (
    "Same-club GK+DEF doubles pay only across a soft run — not a value play.\n\n"
    "```learnings\n"
    '{"specific": [{"lesson": "SELFTEST-LESSON an Arsenal GK+DEF double only '
    'clears one premium mid against bottom-six attacks.", "evidence": "selftest '
    'backtest, 2026-09-03 - 12 of 18 clean sheets came in that split."}],\n'
    ' "general": [{"lesson": "A same-club defensive double is a fixture bet, not '
    'a value bet - take it only across a run of soft opponents.", "evidence": '
    '"selftest backtest, 2026-09-03 - held across 38 sampled club-weeks."}]}\n'
    "```")


_SELFTEST_FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
_SELFTEST_REPORT = (
    "**Haaland** — fit, full training (SELFTEST canned FFS team news, 2026-09-03). "
    "Judgment: nailed.\n\n"
    "wanted source: evil.example — a fan blog the search surfaced; not on the allowlist.\n\n"
    "Coverage: checked FPL flags (official API) + FFS team news; searched Gordon, "
    "found nothing.")


def _selftest_helper(cfg):
    """The #54 acceptance demo, offline: one availability analyst runs as a tool
    loop through the fake transport — an allowlisted fetch, the same URL again
    (served from cache), an off-allowlist fetch (refused before any request), a
    web search, then the report — and writes one headed, write-once report into
    a temp GW folder. Prints the report path, fetch/search counts, cost estimate
    and PASS/FAIL. Returns (ok, lines)."""
    tmp = tempfile.mkdtemp(prefix="gaffer-selftest-helper-")
    gw = 4
    transport = FakeTransport(
        llm_replies=[tool_call_message("fetch", {"url": _SELFTEST_FPL}, "c1"),
                     tool_call_message("fetch", {"url": _SELFTEST_FPL}, "c2"),
                     tool_call_message("fetch", {"url": "https://evil.example/x"}, "c3"),
                     tool_call_message("search", {"query": "Gordon knock Newcastle"}, "s1"),
                     _SELFTEST_REPORT],
        pages={_SELFTEST_FPL: '{"elements": [{"web_name": "Haaland", "status": "a"}]}'},
        search_reply="1. Gordon fit — bbc.co.uk/sport/selftest — 2026-09-02",
        usage={"prompt_tokens": 3000, "completion_tokens": 400})
    logbuf = io.StringIO()
    _, llm, logger = build_stack(cfg, transport, logbuf)
    h = cfg.helpers
    fetcher, searcher = build_helper_tools(cfg, transport, llm, logger)
    writer = ReportWriter(os.path.join(tmp, "reports"), gw, logger=logger,
                          cap_tokens=REPORT_CAP_TOKENS["availability"])
    res = run_helper("availability", llm, h.models["availability"],
                     os.path.join(REPO_ROOT, "agent"),
                     os.path.join(REPO_ROOT, "season-state.json"), gw,
                     fetcher, searcher, writer, h.caps, logger,
                     projections_path=os.path.join(REPO_ROOT, "fixtures",
                                                   "projections-sample.csv"))
    events = [json.loads(l) for l in logbuf.getvalue().splitlines()]
    kinds = {e["event"] for e in events}
    gets = [u for m, u in transport.requests if m == "GET"]
    written = bool(res.path) and os.path.exists(res.path)
    text = ""
    if written:
        with open(res.path, encoding="utf-8") as f:
            text = f.read()
    headed = text.startswith("---\nrole: availability\n") and "status: ok" in text
    one_request = gets == [_SELFTEST_FPL]           # cached repeat + refused domain = 1 GET
    refused = not any("evil.example" in u for u in gets)
    searched = len(transport.search_requests) == 1
    costed = res.cost_usd > 0 and all("cost_usd" in e for e in events if e["event"] == "llm_call")
    ok = (res.status == "ok" and written and headed and one_request and refused
          and searched and costed and {"helper_start", "llm_call", "fetch",
                                       "fetch_refused", "search", "report_written",
                                       "helper_done"} <= kinds)
    lines = [json.dumps(e) for e in events]
    lines.append(f"helper: role=availability model={res.model} status={res.status} "
                 f"report={res.path} fetches={res.fetches} requests={res.requests} "
                 f"searches={res.searches} turns={res.turns} cost=${res.cost_usd:.5f} "
                 f"one-request={one_request} off-allowlist-refused={refused}")
    return ok, lines


def run_selftest(out=None):
    """Offline demo of the #16 + #20 acceptance paths in three wakes: a squad
    question is answered from an assembled, grounded prompt; an ad-hoc analysis
    records its learnings (block stripped before Telegram); the next question's
    prompt provably recalls them. The real workspace + season state feed the
    assembler; a committed projections fixture stands in for the pipeline's
    gitignored output, and the committed learnings diary is copied to a tempdir
    so the demo never grows the repo file. Zero network."""
    out = sys.stdout if out is None else out
    cfg = Config(allowlist={42}, telegram_token="fake-token",
                 openrouter_key="fake-key", model="moonshotai/kimi-k2.5",
                 base_url=DEFAULT_BASE_URL, system_prompt="selftest")
    tmp = tempfile.mkdtemp(prefix="gaffer-selftest-")
    learnings_path = os.path.join(tmp, "learnings.md")
    shutil.copyfile(os.path.join(REPO_ROOT, "agent", "memory", "learnings.md"),
                    learnings_path)
    state_path = os.path.join(REPO_ROOT, "season-state.json")
    assembler = Assembler(
        os.path.join(REPO_ROOT, "agent"), state_path,
        projections_path=os.path.join(REPO_ROOT, "fixtures", "projections-sample.csv"),
        gw=1, learnings_path=learnings_path)
    learnings = LearningsLog(learnings_path, state_path=state_path)
    turns = ["how's my team looking?",
             "backtest doubling up on a GK+DEF from the same club",
             "should I double up on the Arsenal defence?"]
    transport = FakeTransport(
        updates_batches=[[_update(i + 1, t)] for i, t in enumerate(turns)],
        llm_replies=["Haaland (C) anchors a solid XI — thin bench the one worry.",
                     _SELFTEST_LEARNINGS_REPLY,
                     "Only across a soft run — the backtest says fixture bet."])
    logbuf = io.StringIO()
    telegram, llm, logger = build_stack(cfg, transport, logbuf)

    before = len(learnings.entries())
    offset = 0
    for _ in turns:
        offset = poll_once(cfg, telegram, llm, logger, offset,
                           assembler=assembler, learnings=learnings)

    events = [json.loads(l) for l in logbuf.getvalue().splitlines()]
    kinds = {e["event"] for e in events}
    system = transport.llm_requests[0]["messages"][0]["content"]
    grounded = "Haaland" in system                       # a real squad fact reached the model
    clean = not any(m in system for m in ('"picks"', "bought_for", "bench_order"))
    bounded = estimate_tokens(system) <= 25000

    recorded = len(learnings.entries()) - before          # turn 2 grew the diary
    recalled = "SELFTEST-LESSON" in transport.llm_requests[2]["messages"][0]["content"]
    stripped = "```learnings" not in transport.sent[1]["text"]
    ok = ({"wake", "reply", "learnings_recorded"} <= kinds and grounded and clean
          and bounded and recorded == 2 and recalled and stripped)

    for e in events:
        out.write(json.dumps(e) + "\n")
    out.write(f"assembled prompt: {estimate_tokens(system)} tokens, "
              f"grounded={grounded}, no-raw-json={clean}, within-25k={bounded}\n")
    out.write(f"learnings: recorded={recorded}, recalled={recalled}, "
              f"block-stripped={stripped}\n")

    # #54: one analyst as a tool loop, offline, into a temp GW folder.
    helper_ok, helper_lines = _selftest_helper(cfg)
    for line in helper_lines:
        out.write(line + "\n")
    ok = ok and helper_ok

    # #55: a role proposal from chat through the fake git-host runner.
    propose_ok, propose_lines = _selftest_propose(cfg)
    for line in propose_lines:
        out.write(line + "\n")
    ok = ok and propose_ok

    out.write(f"selftest: {'PASS' if ok else 'FAIL'} (events: {sorted(kinds)}, "
              f"helper={'PASS' if helper_ok else 'FAIL'}, "
              f"propose={'PASS' if propose_ok else 'FAIL'})\n")
    return 0 if ok else 1


def run_notify(args, env=None, transport=None, out=None):
    """`daemon notify "<text>"` — push a one-off message to every allowlisted
    chat. Used by the deploy path to report a reload or a blocked deploy. Reuses
    the daemon's Telegram client (same token/allowlist config) rather than
    re-implementing sendMessage. A send failure is logged, never raised: a deploy
    notice must not fail the deploy."""
    out = sys.stderr if out is None else out
    text = args[0] if args else ""
    if not text.strip():
        out.write("notify: empty message, nothing sent\n")
        return 2
    allowlist, token = load_notify_config(env)
    transport = UrllibTransport() if transport is None else transport
    telegram = Telegram(token, transport)
    sent = 0
    for chat_id in sorted(allowlist):
        try:
            telegram.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as e:            # noqa: BLE001 — never fail a deploy on a notice
            # This path bypasses the daemon's scrubbing logger; a transport error
            # could stringify the token-bearing URL, so scrub the token by hand.
            detail = str(e).replace(token, "***") if token else str(e)
            out.write(f"notify: send to {chat_id} failed: {detail}\n")
    return 0 if sent else 1


def run_watch_cmd(env=None, transport=None, out=None, fetch=None):
    """`daemon watch` — the timer-driven price/status wake (#17). Deterministic:
    it fetches, diffs, and alerts without ever loading the LLM key (notify-grade
    config only, same least-privilege posture as the deploy notice). Paths are
    env-overridable so the Pi clone can relocate them; the baseline lives under
    the gitignored data/ dir because it is machine state, not repo content."""
    out = sys.stderr if out is None else out
    allowlist, token = load_notify_config(env)
    env = os.environ if env is None else env
    logger = StructuredLogger(stream=out, secrets=[token])
    telegram = Telegram(token, UrllibTransport() if transport is None else transport)
    if fetch is None:
        def fetch():
            return fpl_api.distill_bootstrap(fpl_api.get("/bootstrap-static/"))
    return run_watch(
        fetch=fetch,
        state_path=_state_path(env),
        shortlist_path=env.get("GAFFER_SHORTLIST_PATH",
                               os.path.join(REPO_ROOT, "agent", "memory",
                                            "shortlist.md")),
        baseline_path=env.get("GAFFER_WATCH_BASELINE_PATH",
                              os.path.join(REPO_ROOT, "data", "watch-baseline.json")),
        telegram=telegram, allowlist=allowlist, logger=logger)


def run_brief_cmd(env=None, transport=None, out=None, fetch=None, now=None):
    """`daemon brief` — the hourly deadline-brief wake (#18). Unlike the watch,
    the brief thinks: it loads the full config (the LLM key), assembles a grounded
    prompt, and on a draft/final tick spends one OpenRouter round-trip. Outside a
    window it is a cheap clock check that sends nothing. The approval state lives
    in data/approval-state.json (gitignored, shared with the reply loop)."""
    out = sys.stderr if out is None else out
    env = os.environ if env is None else env
    cfg = load_config(env)
    transport = UrllibTransport() if transport is None else transport
    telegram, llm, logger = build_stack(cfg, transport, out)

    approval_path = _approval_state_path(env)
    reports_dir = _reports_dir(env)
    state_path = _state_path(env)
    store = ApprovalStore(approval_path)
    actuator = ManualApplyActuator()

    def assembler_factory():
        return build_assembler(env, approval_store_path=approval_path)

    if fetch is None:
        def fetch():
            return fpl_api.distill_bootstrap(fpl_api.get("/bootstrap-static/"))["events"]

    return run_brief(fetch=fetch, llm_complete=llm.complete,
                     assembler_factory=assembler_factory, store=store,
                     telegram=telegram, allowlist=cfg.allowlist, logger=logger,
                     actuator=actuator, state_path=state_path,
                     reports_dir=reports_dir,
                     projections_path=_projections_path(env),
                     snapshot_dir=_data_dir(env), now=now)


def _resolve_entry_id(env, state_path):
    """The FPL entry (team) id the review pulls the fielded picks with (#21) —
    public, non-secret. `FPL_ENTRY_ID` env override first, then the season-state
    `entry_id`, else None (the review falls back to the season-state squad).
    Tolerant int parse: any junk — a missing/corrupt state included — resolves to
    None, never raises."""
    raw = env.get("FPL_ENTRY_ID")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raw = None
        try:
            with open(state_path, encoding="utf-8") as f:
                raw = json.load(f).get("entry_id")
        except Exception:                 # noqa: BLE001 — missing/corrupt state -> no id
            raw = None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def run_review_cmd(env=None, transport=None, out=None, fetch_events=None,
                   fetch_actuals=None, now=None):
    """`daemon review` — the timer-driven post-GW review wake (#21). Like the
    brief it thinks (full config incl. the LLM key), but it is even cheaper day
    to day: a bare events check that spends tokens ONCE per finished gameweek and
    is otherwise silent. It grades the settled GW from code-computed numbers (the
    model never scores itself), records a ```learnings block, and appends the
    review to the decision log. Review state lives in data/review-state.json
    (gitignored); the projection snapshots it grades against were written by the
    brief wake into the same data/ dir."""
    out = sys.stderr if out is None else out
    env = os.environ if env is None else env
    cfg = load_config(env)
    transport = UrllibTransport() if transport is None else transport
    telegram, llm, logger = build_stack(cfg, transport, out)

    state_path = _state_path(env)
    reports_dir = _reports_dir(env)
    review_state = env.get("GAFFER_REVIEW_STATE_PATH",
                           os.path.join(_data_dir(env), "review-state.json"))
    store = ReviewStore(review_state)
    learnings = LearningsLog(_learnings_path(env), state_path=state_path)
    entry_id = _resolve_entry_id(env, state_path)

    approval_path = _approval_state_path(env)

    def assembler_factory():
        return build_assembler(env, approval_store_path=approval_path)

    # One bootstrap snapshot per wake, shared by both default fetchers (the events
    # check and — only if a GW settled — the actuals pull) so a quiet wake is a
    # single request and a live one reuses the same snapshot.
    boot = {}

    def _bootstrap():
        if "snap" not in boot:
            boot["snap"] = fpl_api.distill_bootstrap(fpl_api.get("/bootstrap-static/"))
        return boot["snap"]

    if fetch_events is None:
        def fetch_events():
            return _bootstrap()["events"]
    if fetch_actuals is None:
        def fetch_actuals(gw):
            return fpl_api.fetch_actuals(gw, entry_id, bootstrap_snap=_bootstrap())

    return run_review(fetch_events=fetch_events, fetch_actuals=fetch_actuals,
                      llm_complete=llm.complete,
                      assembler_factory=assembler_factory, store=store,
                      telegram=telegram, allowlist=cfg.allowlist, logger=logger,
                      learnings=learnings, state_path=state_path,
                      reports_dir=reports_dir, snapshot_dir=_data_dir(env),
                      now=now,
                      propose=make_proposer(build_git_host(cfg, REPO_ROOT), logger))


def _current_gw(state_path):
    try:
        with open(state_path, encoding="utf-8") as f:
            return int(json.load(f).get("current_gw"))
    except Exception:                     # noqa: BLE001 — missing/corrupt state -> None
        return None


def run_helper_cmd(args, env=None, transport=None, out=None, fetch_events=None,
                   now=None):
    """`daemon helper <role> [--gw N]` — run one helper role by name as a
    bounded tool loop (#54) and write its report into the next gameweek's
    report folder. Thinks (full config incl. the LLM key; the Odds API key if
    provisioned). The GW is the next unfinished FPL deadline (like the brief),
    overridable with --gw; falls back to the season-state current_gw if the
    events fetch fails. A helper failure is a stub report and exit 0 — only a
    bad invocation (unknown role) is non-zero."""
    out = sys.stderr if out is None else out
    env = os.environ if env is None else env
    args = list(args or [])
    role = args[0] if args and not args[0].startswith("--") else ""
    if role not in ROLE_FILES:
        out.write(f"helper: unknown role {role!r}; known roles: "
                  f"{', '.join(ROLE_FILES)}\n")
        return 2
    gw = None
    if "--gw" in args:
        try:
            gw = int(args[args.index("--gw") + 1])
        except (IndexError, ValueError):
            out.write("helper: --gw needs an integer\n")
            return 2

    cfg = load_config(env)
    transport = UrllibTransport() if transport is None else transport
    _, llm, logger = build_stack(cfg, transport, out)
    state_path = _state_path(env)
    now = now or datetime.now(timezone.utc)

    if gw is None:
        if fetch_events is None:
            def fetch_events():
                return fpl_api.distill_bootstrap(fpl_api.get("/bootstrap-static/"))["events"]
        try:
            nd = next_deadline(fetch_events(), now)
            gw = nd[0] if nd else None
        except Exception as e:            # noqa: BLE001 — fall back to season state
            logger.event("helper_events_error", error=type(e).__name__, detail=str(e))
        if gw is None:
            gw = _current_gw(state_path)
    if gw is None:
        out.write("helper: could not determine the gameweek (pass --gw N)\n")
        return 2

    h = cfg.helpers
    writer = ReportWriter(_reports_dir(env), gw, logger=logger,
                          cap_tokens=REPORT_CAP_TOKENS.get(role, 700))
    if writer.exists(role):
        # Write-once: do not spend a run whose report could not be written.
        logger.event("report_refused", gw=gw, reason="exists", path=writer.path_for(role))
        out.write(f"helper: {writer.path_for(role)} already written (write-once); "
                  "nothing run\n")
        return 0
    fetcher, searcher = build_helper_tools(cfg, transport, llm, logger)
    res = run_helper(role, llm, h.models[role],
                     env.get("GAFFER_WORKSPACE_DIR", os.path.join(REPO_ROOT, "agent")),
                     state_path, gw, fetcher, searcher, writer, h.caps, logger,
                     projections_path=_projections_path(env))
    out.write(f"helper: role={role} gw={gw} status={res.status} report={res.path} "
              f"fetches={res.fetches} requests={res.requests} searches={res.searches} "
              f"turns={res.turns} cost=${res.cost_usd:.5f}"
              + (f" cap={res.cap}" if res.cap else "")
              + (f" reason={res.reason}" if res.reason else "") + "\n")
    return 0


def run_propose_cmd(args, env=None, transport=None, out=None, host=None):
    """`daemon propose "<name>" --role <file.md> [--evidence "<why>"]` — the
    #55 propose path from the command line: a drafted role file on disk (no
    LLM call) goes through the same ACL + runner as a chat/review proposal,
    and the outcome line (PR link / refusal) is pushed to every allowlisted
    chat. Exit 2 on a bad invocation; a refused/failed proposal is exit 0
    (reported, never raised)."""
    out = sys.stderr if out is None else out
    env = os.environ if env is None else env
    args = list(args or [])
    name = args[0] if args and not args[0].startswith("--") else ""
    role_path = args[args.index("--role") + 1] if "--role" in args[:-1] else ""
    evidence = args[args.index("--evidence") + 1] if "--evidence" in args[:-1] else ""
    if not name or not role_path:
        out.write('propose: usage: propose "<name>" --role <file.md> [--evidence "<why>"]\n')
        return 2
    try:
        with open(role_path, encoding="utf-8") as f:
            role_body = f.read()
    except OSError as e:
        out.write(f"propose: cannot read role file: {e}\n")
        return 2

    cfg = load_config(env)
    transport = UrllibTransport() if transport is None else transport
    telegram, _, logger = build_stack(cfg, transport, out)
    host = build_git_host(cfg, REPO_ROOT) if host is None else host
    res = run_propose(Proposal(name, evidence, role_body), host, logger, trigger="cli")
    for chat_id in sorted(cfg.allowlist):
        try:
            telegram.send_message(chat_id=chat_id, text=res.summary())
        except Exception as e:            # noqa: BLE001 — the PR is open; a lost ping is logged
            logger.event("propose_ping_error", chat_id=chat_id,
                         error=type(e).__name__, detail=str(e))
    out.write(f"propose: name={name!r} status={res.status} branch={res.proposal.branch}"
              + (f" url={res.url}" if res.url else "")
              + (f" reason={res.reason}" if res.reason else "") + "\n")
    return 0


_SELFTEST_PROPOSE_REPLY = (
    "No seat covers chip timing — proposing one.\n\n```propose\n"
    "name: Chips analyst\n"
    "evidence: SELFTEST — chip timing has no owner across three drafted briefs.\n"
    "---\n# Chips analyst\n\nOwn chip timing: name the GW each chip earns most.\n```")


def _selftest_propose(cfg):
    """The #55 acceptance demo, offline: `propose role: …` in chat -> the block
    format rides in the user turn -> the canned reply's block is stripped ->
    the fake runner records branch + exactly two files under agent/roles/ ->
    the reply carries the PR link. Plus the ACL: a tier-1 path is refused
    before the runner sees it."""
    host = FakeGitHost(url_base="https://github.com/selftest/pull/")
    transport = FakeTransport(
        updates_batches=[[_update(1, "propose role: chips analyst")]],
        llm_replies=[_SELFTEST_PROPOSE_REPLY])
    logbuf = io.StringIO()
    telegram, llm, logger = build_stack(cfg, transport, logbuf)
    poll_once(cfg, telegram, llm, logger, 0, proposer=make_proposer(host, logger))
    hinted = "```propose" in transport.llm_requests[0]["messages"][-1]["content"]
    pr = host.proposals[0] if host.proposals else {}
    files = sorted(pr.get("files", {}))
    sent = transport.sent[0]["text"] if transport.sent else ""
    stripped = "```propose" not in sent
    linked = "https://github.com/selftest/pull/1" in sent
    refused = run_propose(Proposal("evil", "e", "body", path="daemon/evil.py"),
                          host, logger)
    acl = refused.status == "refused" and len(host.proposals) == 1
    ok = (hinted and pr.get("branch") == "gaffer/chips-analyst"
          and files == ["agent/roles/chips-analyst.evidence.md",
                        "agent/roles/chips-analyst.md"]
          and stripped and linked and acl)
    lines = [json.dumps(json.loads(l)) for l in logbuf.getvalue().splitlines()]
    lines.append(f"propose: branch={pr.get('branch')} files={len(files)} "
                 f"pr={pr and 'https://github.com/selftest/pull/1'} hinted={hinted} "
                 f"block-stripped={stripped} link-in-reply={linked} "
                 f"tier1-refused={acl}")
    return ok, lines


def main(argv):
    if len(argv) > 1 and argv[1] == "propose":
        return run_propose_cmd(argv[2:])
    if len(argv) > 1 and argv[1] == "selftest":
        return run_selftest()
    if len(argv) > 1 and argv[1] == "notify":
        return run_notify(argv[2:])
    if len(argv) > 1 and argv[1] == "watch":
        return run_watch_cmd()
    if len(argv) > 1 and argv[1] == "brief":
        return run_brief_cmd()
    if len(argv) > 1 and argv[1] == "review":
        return run_review_cmd()
    if len(argv) > 1 and argv[1] == "helper":
        return run_helper_cmd(argv[2:])
    return run_daemon()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
