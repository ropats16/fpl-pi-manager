"""Entrypoint. `python3 -m daemon` runs the resident loop; `... selftest` drives
one full message->reply loop offline with every external faked (no network)."""

import io
import json
import os
import shutil
import sys
import tempfile

import fpl_api
from daemon.actuator import ManualApplyActuator
from daemon.brief import run_brief
from daemon.config import Config, load_config, load_notify_config
from daemon.http import FakeTransport, UrllibTransport
from daemon.learnings import LearningsLog
from daemon.llm import DEFAULT_BASE_URL
from daemon.logging_setup import StructuredLogger
from daemon.loop import poll_once, run
from daemon.plan import ApprovalGate, ApprovalStore
from daemon.prompt import Assembler, estimate_tokens
from daemon.runtime import build_stack
from daemon.telegram import Telegram
from daemon.watch import run_watch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _approval_state_path(env):
    return env.get("GAFFER_APPROVAL_STATE_PATH",
                   os.path.join(REPO_ROOT, "data", "approval-state.json"))


def _reports_dir(env):
    return env.get("GAFFER_REPORTS_DIR",
                   os.path.join(REPO_ROOT, "agent", "reports"))


def _learnings_path(env):
    """The #20 diary. Repo content (unlike the gitignored state files): it is the
    record of what the gaffer learned, so it is committed and reviewed."""
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
    state = env.get("GAFFER_STATE_PATH", os.path.join(REPO_ROOT, "season-state.json"))
    projections = env.get("GAFFER_PROJECTIONS_PATH",
                          os.path.join(REPO_ROOT, "data", "projections.csv"))
    return Assembler(workspace, state, projections_path=projections,
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
    learnings = LearningsLog(
        _learnings_path(env),
        state_path=env.get("GAFFER_STATE_PATH",
                           os.path.join(REPO_ROOT, "season-state.json")))
    run(cfg, telegram, llm, logger, assembler=assembler, approvals=approvals,
        learnings=learnings)
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
    out.write(f"selftest: {'PASS' if ok else 'FAIL'} (events: {sorted(kinds)})\n")
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
        state_path=env.get("GAFFER_STATE_PATH",
                           os.path.join(REPO_ROOT, "season-state.json")),
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
    state_path = env.get("GAFFER_STATE_PATH",
                         os.path.join(REPO_ROOT, "season-state.json"))
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
                     reports_dir=reports_dir, now=now)


def main(argv):
    if len(argv) > 1 and argv[1] == "selftest":
        return run_selftest()
    if len(argv) > 1 and argv[1] == "notify":
        return run_notify(argv[2:])
    if len(argv) > 1 and argv[1] == "watch":
        return run_watch_cmd()
    if len(argv) > 1 and argv[1] == "brief":
        return run_brief_cmd()
    return run_daemon()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
