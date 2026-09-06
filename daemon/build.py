"""Commissioning builds — the ```build block, the approval gate, the spawn, and
the tier-1 path ACL (spec §3 / §5, decisions locked 2026-09-04).

The gaffer commissions engineering work the way it proposes a role (#55): it
ends a reply with a fenced ```build block; the daemon opens (or reuses) a GitHub
issue for it, records it as the single `pending_build`, and waits for Rohit's
explicit `build #N` in Telegram to spawn the on-Pi engineer (a fresh
`python3 -m daemon build N` process — the engineer itself lands in PR 3). The
build-approval token is never a bare `yes` (that approves a plan, plan.py); one
build pends and one runs at a time; merge is never automatic.

Block format (header lines, `---`, then the spec markdown the engineer works to):

    ```build
    ticket: new | <number>
    title: <short imperative>
    ---
    <spec: goal, expected files, acceptance criteria, tests to add>
    ```

State lives in the shared `ApprovalStore` (`pending_build`, `running_build`), so
the reply loop, a `daemon build` child and a post-reload recovery all read one
file. A pull-reload restart that kills a running build is a known limit: on the
next daemon start `recover_builds` clears the dead pid and pings Rohit to retry.
"""

import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone

# The single `⚠` line each degrade path appends to the (stripped) reply.
NO_HOST_REPLY = "⚠ builds need the GitHub token on this box"

BUILD_HINT = (
    "To commission a build, end your reply with ONE fenced ```build block: "
    "header lines `ticket: new` (or `ticket: <number>` to reuse an open issue) "
    "and `title: <short imperative>`, a `---` line, then the spec markdown — "
    "goal, expected files, acceptance criteria, tests to add. The daemon opens a "
    "GitHub issue and queues it; nothing runs until Rohit says `build #N`. "
    "Delegate the actual coding to the build — do not write the code yourself.")

_BUILD_BLOCK = re.compile(r"```build\b[ \t]*\r?\n(.*?)```", re.DOTALL)
_BUILD_KEYS = ("ticket", "title")

# Only an explicit prefix asks for the hint — never a conversational "build me a
# lineup". `build #N` / `cancel build` are approval tokens (handled by the gate,
# never here) and start with "build "/"cancel", not "build:".
_BUILD_REQUEST_PREFIXES = ("build:", "ticket:")
_BUILD_TOKEN = re.compile(r"^build(?:\s+#?(\d+))?$")


# --- request parsing ------------------------------------------------------------

class BuildRequest:
    """A parsed ```build block: a new ticket to open, or an existing issue
    number to reuse, plus the title and the spec body the engineer works to."""

    __slots__ = ("is_new", "number", "title", "spec")

    def __init__(self, is_new, number, title, spec):
        self.is_new = is_new
        self.number = number
        self.title = (title or "").strip()
        self.spec = (spec or "").strip()


def parse_build(reply_text, logger=None):
    """(BuildRequest, text_without_block) when the reply carries a well-formed
    ```build block; (None, reply_text) otherwise. Like parse_plan / parse_proposal
    a block that cannot be read is left in place (so the human sees what the
    gaffer wrote and nothing half-parsed becomes an issue) and, when a `logger`
    is given, logged as `build_malformed`."""
    text = reply_text or ""
    m = _BUILD_BLOCK.search(text)
    if not m:
        return None, reply_text
    head, sep, body = m.group(1).partition("\n---")

    def bad(reason):
        if logger is not None:
            logger.event("build_malformed", reason=reason)
        return None, reply_text

    if not sep:
        return bad("no --- separator")
    fields = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        k = k.strip().casefold()
        if k in _BUILD_KEYS:
            fields[k] = v.strip()
    body = body.lstrip("-").lstrip("\r\n")
    ticket, title = fields.get("ticket", ""), fields.get("title", "")
    if not ticket or not title or not body.strip():
        return bad("missing ticket/title/spec")
    if ticket.casefold() == "new":
        is_new, number = True, None
    else:
        try:
            number = int(ticket.lstrip("#"))
        except ValueError:
            return bad(f"bad ticket {ticket!r}")
        is_new = False
    stripped = (text[:m.start()] + text[m.end():]).strip()
    return BuildRequest(is_new, number, title, body), stripped


def is_build_request(text):
    """True iff the message explicitly asks for a capability/code change
    (prefixes `build:` / `ticket:`) — the one case the user turn earns
    BUILD_HINT. Conservative on purpose: an unrelated `build` verb never
    triggers it, so the hint is not appended to every message."""
    t = (text or "").strip().casefold()
    return any(t.startswith(p) for p in _BUILD_REQUEST_PREFIXES)


# --- approval tokens ------------------------------------------------------------

def is_build_approval(text):
    """The `build #N` / `build` start token. Returns the number for `build #N`,
    0 for a bare `build` (start the single pending one), or None when the message
    is not a start token. A bare `yes` is deliberately NOT one — that approves a
    plan (plan.is_approval)."""
    m = _BUILD_TOKEN.match((text or "").strip().casefold())
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 0


def is_build_cancel(text):
    """True iff the whole trimmed message is `cancel build` (case-insensitive)."""
    return (text or "").strip().casefold() == "cancel build"


# --- path ACL (spec §5) ---------------------------------------------------------
# Writable: the code, tests, playbooks, docs, plans, README/AGENTS, root *.py and
# role markdown (but never the engineer's own role file). Everything else is
# denied. `path_allowed` is the authority (default-deny); DENIED is documentation
# of the tier-1 paths §5 calls out. Symlink escapes are checked by the caller
# against the workspace root (a lexical check cannot see a symlink).

WRITABLE_DIRS = ("daemon/", "tests/", "agent/roles/", "agent/playbooks/",
                 "docs/", "plans/")
WRITABLE_FILES = ("README.md", "AGENTS.md")
DENIED_FILES = ("agent/roles/engineer.md",)
DENIED = ("deploy/", ".github/", "season-state.json", "agent/memory/",
          "agent/reports/", "agent/roles/engineer.md", "data/", "fixtures/")


def path_allowed(rel):
    """True iff `rel` is a tier-1-writable repo path the engineer may write.
    Denies absolutes, `..`, dotfiles/dotdirs (`.github/` included), the engineer
    role file, and anything outside the writable set (deploy/, data/, fixtures/,
    season-state.json, agent/memory/, agent/reports/, …)."""
    if not rel or os.path.isabs(rel) or "\\" in rel:
        return False
    parts = rel.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return False
    if os.path.normpath(rel) != rel:
        return False
    if rel in DENIED_FILES:
        return False
    if any(rel.startswith(d) for d in WRITABLE_DIRS):
        return True
    if rel in WRITABLE_FILES:
        return True
    return len(parts) == 1 and rel.endswith(".py")   # root *.py


# --- spawn / pid ----------------------------------------------------------------

def spawn_build(n, data_dir, argv0=None, popen=None):
    """Spawn `python3 -m daemon build N` detached (its own session, so a
    `cancel build` can signal the whole group) with stdout+stderr → the
    gitignored `data/work/build-N.log`. Returns the child pid. `argv0` and
    `popen` are injectable so a test can assert the argv without forking."""
    argv0 = sys.executable if argv0 is None else argv0
    popen = subprocess.Popen if popen is None else popen
    work = os.path.join(data_dir, "work")
    os.makedirs(work, exist_ok=True)
    logpath = os.path.join(work, f"build-{n}.log")
    argv = [argv0, "-m", "daemon", "build", str(n)]
    # The `with` closes the parent's copy of the fd right after fork; the child
    # keeps its own dup — no ResourceWarning under `-W error::ResourceWarning`.
    with open(logpath, "ab") as logf:
        p = popen(argv, start_new_session=True, stdout=logf,
                  stderr=subprocess.STDOUT, env=os.environ.copy())
    return p.pid


def pid_alive(pid):
    """True iff a process with `pid` is alive (signal 0 probe). A pid we do not
    own (EPERM) is alive; no such process (ESRCH) is dead; a falsy pid is dead."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --- the gate handle + operations ----------------------------------------------

class BuildGate:
    """What the reply loop is wired with to commission builds (spec §3): the
    shared ApprovalStore (build state lives beside the plan state), the git host
    that opens issues (None → a "no token" reply), the data dir the engineer's
    log is spawned into, and an injectable spawner for tests."""

    __slots__ = ("store", "host", "data_dir", "spawn", "logger")

    def __init__(self, store, host, data_dir, spawn=None, logger=None):
        self.store = store
        self.host = host
        self.data_dir = data_dir
        self.spawn = spawn or spawn_build
        self.logger = logger


def commission_build(builds, request, logger, now=None):
    """Turn a parsed BuildRequest into the single pending build and return the
    Telegram line to append (the caller has already stripped the block). Opens a
    GitHub issue for a `ticket: new`; reuses the given number otherwise. Refuses
    a second build while one is pending; degrades (never raises) with a fixed
    line when no host is wired or the issue open fails."""
    store = builds.store
    if builds.host is None:
        logger.event("build_dropped", reason="no github token", title=request.title)
        return NO_HOST_REPLY
    if store.pending_build:
        n = store.pending_build["issue"]
        logger.event("build_dropped", reason="already pending", pending=n)
        return f"⛔ a build is already pending (#{n})"
    now = now or datetime.now(timezone.utc)
    try:
        if request.is_new:
            number, _url = builds.host.open_issue(
                request.title, request.spec, labels=["gaffer", "build"])
        else:
            number = request.number
    except Exception as e:            # noqa: BLE001 — a build must not break the wake
        logger.event("build_failed", reason=f"{type(e).__name__}: {e}",
                     title=request.title)
        return f"⚠ could not open the build issue: {type(e).__name__}"
    store.queue_build({"issue": number, "title": request.title,
                       "spec": request.spec,
                       "queued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    logger.event("build_queued", issue=number, title=request.title)
    return f'🔧 build #{number} queued — say "build #{number}" to start'


def start_pending_build(builds, telegram, chat_id, logger, now=None):
    """The `build` / `build #N` gate: spawn the single pending build, or refuse
    while one is already running. Returns True when it replied, None when there
    is nothing pending (the caller falls the message through to the model)."""
    store = builds.store
    if store.running_build:
        m = store.running_build["issue"]
        telegram.send_message(chat_id, f'⛔ build #{m} running — wait or "cancel build"')
        return True
    pending = store.pending_build
    if not pending:
        return None
    num = pending["issue"]
    now = now or datetime.now(timezone.utc)
    pid = builds.spawn(num, builds.data_dir)
    store.run_build({"issue": num, "pid": pid,
                     "started_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    logger.event("build_started", issue=num, pid=pid)
    telegram.send_message(chat_id, f"🔧 build #{num} started")
    return True


def cancel_pending_build(builds, telegram, chat_id, logger):
    """The `cancel build` gate: kill a running build's whole process group and
    clear both slots. Returns True when something was cancelled, None when there
    was nothing to cancel (falls through)."""
    store = builds.store
    pending, running = store.pending_build, store.running_build
    if not pending and not running:
        return None
    num = (running or pending)["issue"]
    if running and pid_alive(running["pid"]):
        try:
            os.killpg(running["pid"], signal.SIGTERM)
        except OSError as e:          # noqa: BLE001 — a race with exit is fine
            logger.event("build_kill_error", issue=num, detail=str(e))
    store.cancel_build()
    logger.event("build_cancelled", issue=num)
    telegram.send_message(chat_id, f"⏹ build #{num} cancelled")
    return True


def recover_builds(store, telegram, allowlist, logger):
    """Dead-pid recovery at daemon start (spec §3 known limit): a pull-reload
    restart kills a running build. If `running_build`'s pid is gone, clear it and
    ping every allowlisted chat to retry. Returns the recovered issue number or
    None. Never raises — a lost ping is logged, not fatal to startup."""
    store.load()
    rb = store.running_build
    if not rb or pid_alive(rb.get("pid")):
        return None
    n = rb.get("issue")
    store.clear_running_build()
    logger.event("build_recovered", issue=n)
    msg = f'⚠ build #{n} died with the daemon restart — say "build #{n}" to retry'
    for chat_id in sorted(allowlist):
        try:
            telegram.send_message(chat_id, msg)
        except Exception as e:        # noqa: BLE001 — a lost ping never fails startup
            logger.event("build_recover_ping_error", chat_id=chat_id, detail=str(e))
    return n
