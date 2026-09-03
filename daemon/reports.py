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

import os

from daemon.prompt import _char_budget, estimate_tokens

HEADER_KEYS = ("model", "started", "finished", "fetches", "searches",
               "coverage", "status")
# Files in a gw folder that are not helper reports (the brief/review record).
_NOT_REPORTS = {"decision-log.md", "scout-log.md"}


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


def read_reports(reports_dir, gw):
    """{role: body} for every helper report in the GW folder (headers stripped,
    decision log and scout log excluded), sorted by role. Missing folder -> {}."""
    folder = gw_folder(reports_dir, gw)
    if not os.path.isdir(folder):
        return {}
    out = {}
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name in _NOT_REPORTS or name.startswith("."):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            out[name[:-3]] = strip_header(f.read())
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
        return os.path.join(self.folder, f"{role}.md")

    def exists(self, role):
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
        budget = _char_budget(self.cap_tokens)
        self._log("report_capped", role=role, tokens=estimate_tokens(body),
                  cap=self.cap_tokens)
        return body[:budget].rstrip() + f"\n\n[truncated at write time: ~{self.cap_tokens} token cap]"

    def write(self, role, body, header):
        """Write `<role>.md` once: header + capped body. Raises ReportRefused
        (already logged) on a second write or a role name that escapes."""
        path = self.path_for(role)
        text = _render_header(role, header) + self._cap(role, body) + "\n"
        out = self.write_path(path, text)
        self._log("report_written", role=role, path=out,
                  tokens=estimate_tokens(text), status=(header or {}).get("status"))
        return out

    def stub(self, role, reason, header):
        """A failed helper's file: names the failure, declares no coverage."""
        h = dict(header or {})
        h["status"] = "failed"
        h["coverage"] = "none"
        return self.write(role, f"{reason}, coverage: none", h)
