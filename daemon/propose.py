"""Role proposal via auto-PR (#55, spec #52, decisions #51/#11).

The gaffer can propose a new (or changed) helper role as a pull request. It
never writes to the repo directly: it emits one fenced ```propose block (a
short header + the role markdown), the daemon checks the change set against
the roles-directory ACL, and one injectable git-host runner puts exactly the
role file + an evidence note on a fresh `gaffer/<slug>` branch off
origin/main, pushes, and opens the PR with the evidence as the body. Rohit
merges by hand; the pull lands it.

Two runners share one interface: `GhGitHost` (real: `git` + `gh`
subprocesses on the Pi, the token only ever in the subprocess environment)
and `FakeGitHost` (records branch, files, PR title/body) so the whole path is
tested offline. The GitHub token is the 4th wired credential and a logger
secret: it is never in model context, argv, a URL, or a log line.

Block format (header lines, `---`, then the role file body):

    ```propose
    name: chips analyst
    evidence: cap_hit on availability three GWs running; no seat covers chip timing
    path: agent/roles/analyst-chips.md      (optional; defaults from the name)
    ---
    # Chips analyst
    ...role markdown...
    ```
"""

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

ROLES_DIR = "agent/roles"
BRANCH_PREFIX = "gaffer/"
DEFAULT_BASE = "main"
DEFAULT_REPO = "ropats16/fpl-pi-manager"
SUBPROCESS_TIMEOUT = 180

_BLOCK = re.compile(r"```propose\b[ \t]*\r?\n(.*?)```", re.DOTALL)
_HEADER_KEYS = ("name", "evidence", "path")

PROPOSE_HINT = (
    "To propose a new helper role, end your reply with ONE fenced ```propose "
    "block: header lines `name: <role name>` and `evidence: <why, citing what "
    "you saw>`, a `---` line, then the full role markdown (persona, sources, "
    "contract). The daemon opens a PR from it; Rohit merges by hand. Only a "
    f"file under {ROLES_DIR}/ can be proposed."
)


PROPOSE_REQUEST_PREFIX = "propose role:"
REVIEW_PROPOSE_HINT = (
    "Roster gap in this review (a helper cap_hit across gameweeks, an axis no "
    "seat covers)? " + PROPOSE_HINT + " Otherwise no block.")


class GitHostError(RuntimeError):
    pass


def is_propose_request(text):
    """True iff the chat message is Rohit asking for a role: `propose role: X`."""
    return (text or "").strip().casefold().startswith(PROPOSE_REQUEST_PREFIX)


def make_proposer(host, logger):
    """The one callable both triggers (chat reply, review reply) hand a parsed
    Proposal to: (proposal, trigger) -> ProposeResult."""
    def propose(proposal, trigger):
        return run_propose(proposal, host, logger, trigger=trigger)
    return propose


def slugify(name):
    """`Chips analyst!` -> `chips-analyst` (ASCII letters/digits/hyphens,
    max 40 chars). '' when nothing survives."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").casefold()).strip("-")
    return s[:40].strip("-")


class Proposal:
    __slots__ = ("name", "slug", "evidence", "role_body", "path")

    def __init__(self, name, evidence, role_body, path=None):
        self.name = (name or "").strip()
        self.slug = slugify(self.name)
        self.evidence = (evidence or "").strip()
        self.role_body = (role_body or "").strip()
        self.path = (path or "").strip() or f"{ROLES_DIR}/{self.slug}.md"

    @property
    def branch(self):
        return BRANCH_PREFIX + self.slug

    @property
    def note_path(self):
        return f"{ROLES_DIR}/{self.slug}.evidence.md"

    @property
    def title(self):
        return f"Propose role: {self.name} (gaffer)"


def parse_proposal(reply_text):
    """(Proposal, text_without_block) when the reply carries a ```propose
    block; (None, reply_text) otherwise. Like parse_plan: a block that cannot
    be read (no `---`, no name) is left in place so the human sees what the
    gaffer wrote and nothing half-parsed becomes a branch."""
    text = reply_text or ""
    m = _BLOCK.search(text)
    if not m:
        return None, reply_text
    head, sep, body = m.group(1).partition("\n---")
    if not sep:
        return None, reply_text
    fields = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        k = k.strip().casefold()
        if k in _HEADER_KEYS:
            fields[k] = v.strip()
    body = body.lstrip("-").lstrip("\r\n")
    if not fields.get("name"):
        return None, reply_text
    stripped = (text[:m.start()] + text[m.end():]).strip()
    return Proposal(fields["name"], fields.get("evidence"), body,
                    path=fields.get("path")), stripped


def path_violation(rel):
    """Why `rel` may not be in a proposal change set, or None when it is a
    markdown file under the roles directory. Absolute paths, `..`, hidden
    segments and anything outside ROLES_DIR (which is every tier-1 path:
    daemon/, deploy/, .github/ …) are refused."""
    if not rel or os.path.isabs(rel) or "\\" in rel:
        return "not a relative path"
    parts = rel.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return "path escapes or hides"
    if os.path.normpath(rel) != rel:
        return "path not normalised"
    if not rel.startswith(ROLES_DIR + "/"):
        return f"outside {ROLES_DIR}/"
    if not rel.endswith(".md"):
        return "not a markdown file"
    return None


def render_note(proposal, trigger, now):
    return (f"# Proposal: {proposal.name}\n\n"
            f"opened: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"branch: {proposal.branch}\n"
            f"trigger: {trigger}\n"
            f"role file: {proposal.path}\n\n"
            f"## Evidence\n\n{proposal.evidence or '(none given)'}\n")


def render_pr_body(proposal, trigger):
    return (f"## Evidence\n\n{proposal.evidence or '(none given)'}\n\n"
            f"Role file: `{proposal.path}` · note: `{proposal.note_path}` · "
            f"trigger: {trigger}.\n\n"
            "Opened by the gaffer from the Pi (#55). Merge by hand; the pull "
            "lands it next wake.\n")


class ProposeResult:
    __slots__ = ("status", "proposal", "url", "reason")

    def __init__(self, status, proposal, url=None, reason=None):
        self.status = status          # ok | refused | failed
        self.proposal = proposal
        self.url = url
        self.reason = reason

    def summary(self):
        name = self.proposal.name if self.proposal else "?"
        if self.status == "ok":
            return f"📎 Proposed role `{name}` → {self.url}"
        if self.status == "refused":
            return f"⛔ Role proposal `{name}` refused: {self.reason}"
        return f"⚠️ Role proposal `{name}` failed: {self.reason}"


def run_propose(proposal, host, logger, trigger="chat", now=None):
    """The one propose path. ACL first (a violation is refused + logged and
    the runner is never called), then write-once on the branch name, then the
    runner. Any runner error is a `failed` result, never an exception — a
    proposal must not break the wake that raised it."""
    now = now or datetime.now(timezone.utc)
    name = proposal.name if proposal else ""

    def refuse(reason, **extra):
        logger.event("propose_refused", name=name, reason=reason, **extra)
        return ProposeResult("refused", proposal, reason=reason)

    if not proposal or not proposal.slug:
        return refuse("no usable role name")
    if not proposal.role_body:
        return refuse("empty role file")
    files = {proposal.path: proposal.role_body + "\n",
             proposal.note_path: render_note(proposal, trigger, now)}
    for rel in files:
        why = path_violation(rel)
        if why:
            return refuse(f"{rel}: {why}", path=rel)
    if host is None:
        logger.event("propose_failed", name=name, reason="no github token")
        return ProposeResult("failed", proposal,
                             reason="no GitHub token configured on this box")
    try:
        if host.branch_exists(proposal.branch):
            return refuse(f"branch {proposal.branch} already exists (write-once)",
                          branch=proposal.branch)
        logger.event("propose_start", name=name, branch=proposal.branch,
                     files=sorted(files), trigger=trigger)
        url = host.open_pr(proposal.branch, files, proposal.title,
                           render_pr_body(proposal, trigger))
    except Exception as e:                 # noqa: BLE001 — degrade, never abort the wake
        logger.event("propose_failed", name=name, branch=proposal.branch,
                     error=type(e).__name__, detail=str(e))
        return ProposeResult("failed", proposal, reason=f"{type(e).__name__}: {e}")
    logger.event("propose_opened", name=name, branch=proposal.branch, url=url,
                 trigger=trigger)
    return ProposeResult("ok", proposal, url=url)


class FakeGitHost:
    """Records what a real runner would have done. `existing` seeds branches
    that already exist on the remote; `fail` makes open_pr raise."""

    def __init__(self, existing=(), fail=None, url_base="https://github.com/x/y/pull/"):
        self.existing = set(existing)
        self.fail = fail
        self.url_base = url_base
        self.proposals = []

    def branch_exists(self, branch):
        return branch in self.existing

    def open_pr(self, branch, files, title, body):
        if self.fail:
            raise GitHostError(self.fail)
        self.proposals.append({"branch": branch, "files": dict(files),
                               "title": title, "body": body})
        self.existing.add(branch)
        return f"{self.url_base}{len(self.proposals)}"


def _subprocess_run(argv, env, cwd):
    p = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True,
                       timeout=SUBPROCESS_TIMEOUT)
    return p.returncode, p.stdout, p.stderr


# The token reaches git only through this helper, which reads it from the
# subprocess environment: never on the command line, never in the remote URL.
_CRED_HELPER = ('!f() { echo username=x-access-token; '
                'echo "password=$GAFFER_GITHUB_TOKEN"; }; f')


class GhGitHost:
    """Real runner: a detached temp worktree off the freshly fetched base so
    the Pi's own checkout (branch pi/live) is never touched, one commit, a push
    to `refs/heads/gaffer/<slug>` over HTTPS, then `gh pr create`. The
    worktree is removed whatever happens."""

    def __init__(self, repo_root, token, repo=DEFAULT_REPO, base=DEFAULT_BASE,
                 run=None, author=("FPL gaffer", "gaffer@fpl-pi")):
        self.repo_root = repo_root
        self._token = token
        self.repo = repo
        self.base = base
        self._run = run or _subprocess_run
        self.author = author

    def _env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
        env["GAFFER_GITHUB_TOKEN"] = self._token
        env["GH_TOKEN"] = self._token
        env["GIT_TERMINAL_PROMPT"] = "0"
        # gh under ProtectHome=yes: keep its config/state out of $HOME, no prompts.
        env.setdefault("GH_CONFIG_DIR", os.path.join(tempfile.gettempdir(), "gaffer-gh"))
        env["GH_PROMPT_DISABLED"] = "1"
        env["GH_NO_UPDATE_NOTIFIER"] = "1"
        return env

    def _cmd(self, argv, cwd=None):
        rc, out, err = self._run(argv, self._env(), cwd or self.repo_root)
        if rc != 0:
            raise GitHostError(f"{' '.join(argv[:2])} failed (rc={rc}): "
                               f"{(err or out).strip()[:400]}")
        return out

    def branch_exists(self, branch):
        out = self._cmd(["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"])
        return bool(out.strip())

    def open_pr(self, branch, files, title, body):
        tmp = tempfile.mkdtemp(prefix="gaffer-propose-")
        try:
            self._cmd(["git", "fetch", "--quiet", "origin", self.base])
            self._cmd(["git", "worktree", "add", "--detach", "--quiet", tmp, "FETCH_HEAD"])
            root = os.path.realpath(tmp)
            for rel, content in files.items():
                dest = os.path.realpath(os.path.join(root, rel))
                if os.path.dirname(dest) != os.path.join(root, os.path.dirname(rel)):
                    raise GitHostError(f"refusing to write outside the worktree: {rel}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
            self._cmd(["git", "add", "--", *files], cwd=tmp)
            self._cmd(["git", "-c", f"user.name={self.author[0]}",
                       "-c", f"user.email={self.author[1]}",
                       "commit", "--quiet", "-m", title], cwd=tmp)
            self._cmd(["git", "-c", "credential.helper=", "-c",
                       f"credential.helper={_CRED_HELPER}", "push", "--quiet",
                       f"https://github.com/{self.repo}.git",
                       f"HEAD:refs/heads/{branch}"], cwd=tmp)
            body_path = os.path.join(tmp, ".pr-body.md")
            with open(body_path, "w", encoding="utf-8") as f:
                f.write(body)
            out = self._cmd(["gh", "pr", "create", "--repo", self.repo, "--head", branch,
                             "--base", self.base, "--title", title,
                             "--body-file", body_path], cwd=tmp)
            return out.strip().splitlines()[-1] if out.strip() else ""
        finally:
            try:
                self._run(["git", "worktree", "remove", "--force", tmp],
                          self._env(), self.repo_root)
            except Exception:              # noqa: BLE001 — best-effort cleanup
                pass
            shutil.rmtree(tmp, ignore_errors=True)
