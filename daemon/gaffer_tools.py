"""The gaffer's chat tools (spec §2) — the nine `Tool`s the resident agent may
call while answering in Telegram, each with a per-wake cap.

The gaffer works like a real manager: it delegates to a staff seat (`ask_helper`),
reads what the staff already wrote (`read_report`, `read_projections`), checks the
raw FPL facts (`fpl_lookup`) and — only when no seat covers it — searches and
fetches the web on the same allowlist/scrub the analysts use. Two ticket tools and
a PR-status tool let it commission and track work it cannot do itself, but it opens
a ticket only when Rohit asks for a capability change (GAFFER.md "Your tools").

`host` is duck-typed (PR 2 adds these to GhGitHost/FakeGitHost):
    open_issue(title, body, labels) -> (number, url)
    issue_status(n) -> str
    pr_status(n)    -> str
A tool whose dependency is None is simply not offered (no host / no search key /
no fetcher). `ask_helper` runs the injected `helper_runner(role, question) -> str`
(the existing `run_helper` for that role, task=question) and appends the answer as
a dated Q&A section to that role's GW report — write-once guards a fan-out
overwrite, an append is allowed (spec §2).
"""

import csv
import os
from datetime import datetime, timezone
from http.client import HTTPException

from daemon.agent import Tool
from daemon.config import HELPER_ROLES
from daemon.prompt import char_budget, normalize_name
from daemon.reports import (ReportRefused, ReportWriter, gw_folder, read_scout_log,
                            strip_header)
from daemon.tools import FETCH_TOOL, SEARCH_TOOL

# The engineer (PR 3) is not a chat seat — it builds tickets, it does not answer
# questions — so it is never an `ask_helper` target.
ASKABLE_ROLES = tuple(r for r in HELPER_ROLES if r != "engineer")
# Every role whose report the gaffer may read — the seats plus the Scout log.
# read_report joins this into a path, so it MUST be validated against this set
# (a model-chosen `role` like "../../GAFFER" must never escape the GW folder).
READABLE_ROLES = frozenset(HELPER_ROLES)

_FPL_API = "https://fantasy.premierleague.com/api"
BOOTSTRAP_URL = f"{_FPL_API}/bootstrap-static/"
FIXTURES_URL = f"{_FPL_API}/fixtures/"
_POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
_LOOKUP_KINDS = ("player", "team", "fixtures")


def _iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int_or(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _head(text, max_tokens):
    budget = char_budget(max_tokens)
    text = (text or "").strip()
    return text if len(text) <= budget else text[:budget].rstrip() + "…"


def build_gaffer_tools(cfg, workspace_root, state_path, reports_dir, projections_path,
                       gw, fetcher, searcher, helper_runner, host, logger=None):
    """Return the gaffer's chat tools (spec §2). Only the tools whose dependency
    is present are offered. Every `fn` returns a string and never raises (the
    run_agent loop turns a thrown tool into evidence, but these degrade first)."""
    boot_cache = {}
    wake_gw = gw            # the read_report arg `gw` shadows the builder's; keep this

    # --- ask_helper ---------------------------------------------------------------
    def ask_helper(role=None, question=None, **_):
        role = (role or "").strip()
        question = (question or "").strip()
        if role not in ASKABLE_ROLES:
            return (f"ask_helper: unknown role {role!r}; ask one of "
                    f"{', '.join(ASKABLE_ROLES)}.")
        if not question:
            return "ask_helper: give the staff member a question."
        text = helper_runner(role, question)
        section = f"### {_iso_now()} — {role} (asked)\n\n{text}"
        try:
            ReportWriter(reports_dir, gw, logger=logger).append_section(role, section)
        except (ReportRefused, OSError, TypeError, ValueError):
            pass                    # the answer still returns; the append is best-effort
        return text

    # --- read_report --------------------------------------------------------------
    def read_report(role=None, gw=None, **_):
        role = (role or "").strip()
        if role not in READABLE_ROLES:
            # `role` is joined into a path below: reject anything but a known seat
            # so "../../GAFFER" can never read outside the GW folder into context.
            return (f"read_report: unknown role {role!r}; readable reports are "
                    f"{', '.join(sorted(READABLE_ROLES))}.")
        g = _int_or(gw, wake_gw)
        if role == "scout":
            body = read_scout_log(reports_dir, g)
        else:
            path = os.path.join(gw_folder(reports_dir, g), f"{role}.md")
            body = ""
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    body = strip_header(f.read())
        if not (body or "").strip():
            return f"no {role or '(unnamed)'} report for GW{g} yet."
        return _head(body, 1500)

    # --- read_projections ---------------------------------------------------------
    def read_projections(name=None, **_):
        name = (name or "").strip()
        if not name:
            return "read_projections: give a player name."
        key = normalize_name(name)
        rows = []
        try:
            with open(projections_path, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if normalize_name(row.get("web_name", "")) == key:
                        rows.append(row)
        except OSError:
            return f"read_projections: projections file unavailable for {name!r}."
        if not rows:
            return f"no projections row for {name!r} (name-join found nothing)."
        rows.sort(key=lambda r: _int_or(r.get("gw"), 0))
        head = rows[0]
        out = [f"{head.get('web_name', name)} ({head.get('pos', '?')}, team "
               f"{head.get('team', '?')}) — projections by GW:"]
        for r in rows:
            out.append(f"GW{r.get('gw')}: xpts={r.get('xpts')} xmins={r.get('xmins')} "
                       f"horizon={r.get('horizon_xpts')} price={r.get('now_cost')}")
        return "\n".join(out)

    # --- fpl_lookup ---------------------------------------------------------------
    def _bootstrap():
        if "b" not in boot_cache:
            boot_cache["b"] = fetcher.fetch_json(BOOTSTRAP_URL)
        return boot_cache["b"]

    def _team_by_id(boot):
        return {t.get("id"): t for t in boot.get("teams", [])}

    def _match_team(boot, name):
        nl = name.lower().strip()
        for t in boot.get("teams", []):
            if nl in ((t.get("name") or "").lower(), (t.get("short_name") or "").lower()) \
                    or nl in (t.get("name") or "").lower():
                return t
        return None

    def fpl_lookup(kind=None, name=None, **_):
        kind = (kind or "").strip().lower()
        name = (name or "").strip()
        if kind not in _LOOKUP_KINDS:
            return f"fpl_lookup: kind must be one of {', '.join(_LOOKUP_KINDS)}."
        if not name:
            return "fpl_lookup: give a name."
        try:
            boot = _bootstrap()
        except (ValueError, OSError, HTTPException) as e:
            return f"fpl_lookup: could not read the FPL bootstrap: {e}"
        teams = _team_by_id(boot)
        if kind == "player":
            key = normalize_name(name)
            for p in boot.get("elements", []):
                if normalize_name(p.get("web_name", "")) == key:
                    club = (teams.get(p.get("team")) or {}).get("short_name", "?")
                    price = _int_or(p.get("now_cost"), 0) / 10
                    news = p.get("news") or "no news"
                    return (f"{p.get('web_name')} — {_POS.get(p.get('element_type'), '?')}, "
                            f"{club}, £{price:.1f}m · status {p.get('status')} ({news}) · "
                            f"form {p.get('form')} · ep_next {p.get('ep_next')} · "
                            f"selected {p.get('selected_by_percent')}% · "
                            f"xGI {p.get('expected_goal_involvements')}")
            return f"fpl_lookup: no player matched {name!r}."
        if kind == "team":
            t = _match_team(boot, name)
            if not t:
                return f"fpl_lookup: no team matched {name!r}."
            return (f"{t.get('short_name')} ({t.get('name')}) — attack "
                    f"{t.get('strength_attack_home')}/{t.get('strength_attack_away')} "
                    f"(H/A), defence {t.get('strength_defence_home')}/"
                    f"{t.get('strength_defence_away')} (H/A)")
        # fixtures
        t = _match_team(boot, name)
        if not t:
            return f"fpl_lookup: no team matched {name!r}."
        tid = t.get("id")
        try:
            fixtures = fetcher.fetch_json(FIXTURES_URL)
        except (ValueError, OSError, HTTPException) as e:
            return f"fpl_lookup: could not read fixtures: {e}"
        lines = []
        for fx in fixtures or []:
            if fx.get("finished") or tid not in (fx.get("team_h"), fx.get("team_a")):
                continue
            home = fx.get("team_h") == tid
            opp = teams.get(fx.get("team_a") if home else fx.get("team_h")) or {}
            diff = fx.get("team_h_difficulty") if home else fx.get("team_a_difficulty")
            lines.append(f"GW{fx.get('event')}: {'H' if home else 'A'} vs "
                         f"{opp.get('short_name', '?')} (difficulty {diff})")
        if not lines:
            return f"fpl_lookup: no upcoming fixtures found for {t.get('short_name')}."
        return f"{t.get('short_name')} upcoming fixtures:\n" + "\n".join(lines)

    # --- ticket + PR tools --------------------------------------------------------
    def open_ticket(title=None, body=None, **_):
        title = (title or "").strip()
        if not title:
            return "open_ticket: give a title."
        number, url = host.open_issue(title, body or "", labels=["gaffer"])
        return f"#{number} {url}"

    def ticket_status(number=None, **_):
        n = _int_or(number, None)
        if n is None:
            return "ticket_status: give an issue number."
        return host.issue_status(n)

    def pr_status(number=None, **_):
        n = _int_or(number, None)
        if n is None:
            return "pr_status: give a PR number."
        return host.pr_status(n)

    # --- assemble (only offer a tool whose dependency is present) -----------------
    tools = []
    if helper_runner is not None:
        tools.append(Tool("ask_helper",
            "Ask one staff member (an analyst, the Scout, or the Assistant Manager) "
            "a specific question; returns their answer and files it under their GW "
            f"report. Roles: {', '.join(ASKABLE_ROLES)}. Delegate here first.",
            {"type": "object", "properties": {
                "role": {"type": "string", "enum": list(ASKABLE_ROLES)},
                "question": {"type": "string"}},
             "required": ["role", "question"]}, ask_helper, cap=2))
    if reports_dir is not None:
        tools.append(Tool("read_report",
            "Read a staff member's written report for this (or a given) gameweek.",
            {"type": "object", "properties": {
                "role": {"type": "string"},
                "gw": {"type": "integer", "description": "gameweek; defaults to this wake's"}},
             "required": ["role"]}, read_report, cap=6))
    if projections_path is not None:
        tools.append(Tool("read_projections",
            "The projection pipeline's rows for one player across all gameweeks.",
            {"type": "object", "properties": {"name": {"type": "string"}},
             "required": ["name"]}, read_projections, cap=6))
    if fetcher is not None:
        tools.append(Tool("fpl_lookup",
            "Structured facts from the public FPL API: a player's price/status/form, "
            "a team's strengths, or a team's upcoming fixtures.",
            {"type": "object", "properties": {
                "kind": {"type": "string", "enum": list(_LOOKUP_KINDS)},
                "name": {"type": "string"}},
             "required": ["kind", "name"]}, fpl_lookup, cap=6))
    if searcher is not None:
        tools.append(Tool.from_schema(
            SEARCH_TOOL, lambda query=None, **_: searcher.search(query or "", role="gaffer"),
            cap=3))
    if fetcher is not None:
        tools.append(Tool.from_schema(
            FETCH_TOOL, lambda url=None, **_: fetcher.fetch(url or ""), cap=5))
    if host is not None:
        tools.append(Tool("open_ticket",
            "Open a GitHub issue labelled 'gaffer' for work you cannot do yourself. "
            "Only when Rohit has asked for a capability change.",
            {"type": "object", "properties": {
                "title": {"type": "string"}, "body": {"type": "string"}},
             "required": ["title", "body"]}, open_ticket, cap=1))
        tools.append(Tool("ticket_status",
            "The state, title, labels and last comment of a GitHub issue.",
            {"type": "object", "properties": {"number": {"type": "integer"}},
             "required": ["number"]}, ticket_status, cap=4))
        tools.append(Tool("pr_status",
            "The state, draft flag, checks and mergeability of a pull request.",
            {"type": "object", "properties": {"number": {"type": "integer"}},
             "required": ["number"]}, pr_status, cap=4))
    return tools
