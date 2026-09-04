"""Helper report writer (#54) — the single write path for helper output.

One file per role per gameweek under `<reports_dir>/gwNN/<role>.md`,
write-once (a second write is refused and logged, so what the gaffer read stays
what Rohit can read later), body capped at write time (analysts ~700 tokens so
the draft prompt stays under 25k with the reports inlined, #52 story 27), and a
source-stamped header: role, model, started/finished, fetch/search counts,
coverage, cap/failure status. Helpers can write nowhere else: every write goes
through `write_path`, which refuses any path outside the current gameweek's
report folder (asserted by test). A failed helper still produces a file — a
stub naming the failure and "coverage: none" — so silence never passes as
coverage.

The Scout's append-only `scout-log.md` is the one exception to write-once and
lands with the Scout timer (#57) on this same writer.
"""

import fcntl
import os
import re

from daemon.config import HELPER_ROLES
from daemon.prompt import char_budget, estimate_tokens


class ReportRefused(Exception):
    """A write the ACL or the write-once rule refused. The caller logs it and
    moves on — a refused report never raises out of a wake."""


def gw_folder(reports_dir, gw):
    return os.path.join(reports_dir, f"gw{int(gw):02d}")


def _render_header(role, header):
    h = dict(header or {})
    fetches = h.get("fetches", 0)
    requests = h.get("requests")
    fetch_line = (f"{fetches} ({requests} requests)" if requests is not None
                  else str(fetches))
    lines = ["---", f"role: {role}", f"model: {h.get('model', 'n/a')}",
             f"started: {h.get('started', 'n/a')}", f"finished: {h.get('finished', 'n/a')}",
             f"fetches: {fetch_line}", f"searches: {h.get('searches', 0)}",
             f"coverage: {h.get('coverage', 'n/a')}", f"status: {h.get('status', 'n/a')}",
             "---", ""]
    return "\n".join(lines)


def strip_header(text):
    """The body of a headed report file ("" for a file with no header)."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:].lstrip("\n")
    return text


def read_scout_log(reports_dir, gw):
    """The full `scout-log.md` for the GW ("" if none). The one path callers
    should use for the Scout log so nobody hand-rolls it (#56/#57)."""
    path = os.path.join(gw_folder(reports_dir, gw), "scout-log.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


# One Scout entry starts with the stamp line _append_scout writes — never a
# `### ` heading the model put inside its own body.
_ENTRY_RE = re.compile(r"^### \S+ — scout \(", re.MULTILINE)


def scout_entries(text):
    """The entries of a Scout log, newest first (stamp line + body each)."""
    starts = [m.start() for m in _ENTRY_RE.finditer(text or "")]
    return [text[a:b].strip() for a, b in zip(starts, starts[1:] + [len(text)])]


def latest_scout_entry(reports_dir, gw):
    """The newest entry of the GW's Scout log, "" if it has none (#57)."""
    entries = scout_entries(read_scout_log(reports_dir, gw))
    return entries[0] if entries else ""


def urgent_line(entry):
    """The first line of a Scout entry carrying the URGENT tag (markdown
    emphasis stripped, ≤240 chars), or None. The tag is the Scout charter's
    "could void the current plan" flag; the daemon surfaces it (#57)."""
    for line in (entry or "").splitlines()[1:]:
        if "URGENT" in line:
            line = line.strip().replace("**", "").replace("__", "").lstrip("-* ").strip()
            return line if len(line) <= 240 else line[:239].rstrip() + "…"
    return None


def read_reports(reports_dir, gw):
    """{role: body} for every helper-role report in the GW folder (headers
    stripped), sorted by role. Only `<role>.md` for a known helper role counts:
    the decision log, the Scout log and any other file in the folder are not
    "reports already written this wake". Missing folder -> {}."""
    folder = gw_folder(reports_dir, gw)
    if not os.path.isdir(folder):
        return {}
    out = {}
    for role in sorted(HELPER_ROLES):
        path = os.path.join(folder, f"{role}.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                out[role] = strip_header(f.read())
    return out


class ReportWriter:
    def __init__(self, reports_dir, gw, logger=None, cap_tokens=700):
        self.reports_dir = reports_dir
        self.gw = int(gw)
        self.folder = gw_folder(reports_dir, gw)
        self._logger = logger
        self.cap_tokens = cap_tokens

    def _log(self, event, **fields):
        if self._logger is not None:
            self._logger.event(event, gw=self.gw, **fields)

    def path_for(self, role):
        # The Scout writes an append-only log, never a write-once <role>.md (#57).
        name = "scout-log.md" if role == "scout" else f"{role}.md"
        return os.path.join(self.folder, name)

    def exists(self, role):
        # A log is never "already written": the Scout may append every wake (#57).
        if role == "scout":
            return False
        return os.path.exists(self.path_for(role))

    def _inside_folder(self, path):
        root = os.path.realpath(self.folder)
        target = os.path.realpath(path)
        return os.path.dirname(target) == root

    def write_path(self, path, text):
        """The ACL'd write: only directly inside this GW's folder, only a new
        file. Atomic (temp + replace) so a crash never leaves a half report."""
        if not self._inside_folder(path):
            self._log("report_refused", reason="outside_gw_folder", path=path)
            raise ReportRefused(f"refused: {path} is outside {self.folder}")
        if os.path.exists(path):
            self._log("report_refused", reason="exists", path=path)
            raise ReportRefused(f"refused: {path} already written (write-once)")
        return self._atomic_write(path, text)

    def _atomic_write(self, path, text):
        """temp + replace so a crash never leaves a half report. No write-once
        check (the Scout log is rewritten in place each append)."""
        os.makedirs(self.folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return path

    def _cap(self, role, body):
        body = (body or "").strip()
        if estimate_tokens(body) <= self.cap_tokens:
            return body
        budget = char_budget(self.cap_tokens)
        self._log("report_capped", role=role, tokens=estimate_tokens(body),
                  cap=self.cap_tokens)
        return body[:budget].rstrip() + f"\n\n[truncated at write time: ~{self.cap_tokens} token cap]"

    def write(self, role, body, header):
        """Write `<role>.md` once: header + capped body. Raises ReportRefused
        (already logged) on a second write or a role name that escapes. The
        Scout is the one exception — it prepends a dated entry to `scout-log.md`
        (#57), never write-once."""
        if role == "scout":
            return self._append_scout(body, header)
        path = self.path_for(role)
        text = _render_header(role, header) + self._cap(role, body) + "\n"
        out = self.write_path(path, text)
        self._log("report_written", role=role, path=out,
                  tokens=estimate_tokens(text), status=(header or {}).get("status"))
        return out

    def _append_scout(self, body, header):
        """Prepend one dated entry to `scout-log.md`, newest first, under a
        single `# Scout log — GWNN` header (#57). ACL'd inside the GW folder and
        atomic. Only the per-entry body is capped (`cap_tokens`); the log itself
        is left uncapped so the season's coverage trail survives."""
        path = self.path_for("scout")
        if not self._inside_folder(path):
            self._log("report_refused", reason="outside_gw_folder", path=path)
            raise ReportRefused(f"refused: {path} is outside {self.folder}")
        h = dict(header or {})
        ts = h.get("finished") or h.get("started") or "n/a"
        entry = (f"### {ts} — scout ({h.get('model', 'n/a')}; "
                 f"fetches {h.get('fetches', 0)}; searches {h.get('searches', 0)}; "
                 f"status {h.get('status', 'n/a')}; coverage {h.get('coverage', 'n/a')})"
                 f"\n\n{self._cap('scout', body)}\n")
        top = f"# Scout log — GW{self.gw:02d}\n"
        os.makedirs(self.folder, exist_ok=True)
        # Two writers can overlap (the #57 daily Scout vs the final delta): the
        # read-modify-write holds an exclusive lock so neither entry is lost.
        with open(path + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            existing = ""
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    existing = f.read()
            if existing.startswith("# Scout log"):
                rest = existing[existing.find("\n") + 1:]     # under our header
            else:
                rest = existing                               # keep a foreign top line
            text = top + "\n" + entry + rest
            out = self._atomic_write(path, text)
        self._log("report_appended", role="scout", path=out,
                  entries=len(scout_entries(text)))
        return out

    def stub(self, role, reason, header):
        """A failed helper's file: names the failure, declares no coverage."""
        h = dict(header or {})
        h["status"] = "failed"
        h["coverage"] = "none"
        return self.write(role, f"{reason}, coverage: none", h)
