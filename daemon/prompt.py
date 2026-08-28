"""Prompt assembly — the gaffer's system prompt built from the `agent/` workspace
markdown plus distilled season facts, under a hard token cap (#16).

Policy (locked in #9): lean index-then-fetch. Always-in = persona + season
snapshot + memory index + today's playbook + report index; hard cap ~25k tokens,
asserted by tests; critical facts at the prompt edges (headline at the top,
the full snapshot adjacent to the user turn) to fight context rot.

Invariant (#9/#10): prompts are assembled from *distilled* state + data, never
raw API payloads and never raw snapshot JSON. `season_snapshot` formats facts as
prose/markdown; nothing here ever `json.dumps`es the state into model context.
"""

import csv
import json
import os
import unicodedata

CAP_TOKENS = 25000
# Conservative ~3.5 chars/token. Dense markdown (prices, names, punctuation)
# tokenizes below the ~4-char English-prose average, so we round the ratio down
# to avoid *under*-counting and blowing the real budget.
_TOKEN_NUM, _TOKEN_DEN = 2, 7


def estimate_tokens(text):
    """Cheap, stdlib-only token estimate (~3.5 chars/token, rounded up)."""
    return (len(text) * _TOKEN_NUM + _TOKEN_DEN - 1) // _TOKEN_DEN


def _char_budget(cap_tokens):
    """Max chars whose estimate stays within cap_tokens (inverse of estimate_tokens)."""
    return cap_tokens * _TOKEN_DEN // _TOKEN_NUM


# --- name join: synthetic squad ids -> real projection rows ---------------------------

def normalize_name(name):
    """Fold a display name to a join key. Squad names ("Bruno Fernandes",
    "Joao Pedro") and projection web_names ("B.Fernandes", "J.Pedro") converge on
    the surname token, accent- and case-folded."""
    s = (name or "").strip()
    if " " in s:
        s = s.rsplit(" ", 1)[1]      # surname token: "Bruno Fernandes" -> "Fernandes"
    if "." in s:
        s = s.rsplit(".", 1)[1]      # dotted initial: "B.Fernandes" -> "Fernandes"
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_projections(path, gw):
    """Distilled projections for one gameweek, keyed by (normalized name, position).

    Reads the pipeline's `projections.csv` (long format: player x gameweek) and
    keeps only the given gw. The key is position-scoped so two players who share a
    surname in different positions (e.g. a GKP Palmer and a MID Palmer) can't be
    cross-wired — presenting the wrong player's points as fact would violate the
    never-fabricate rule. Same-name-same-position collisions remain first-row-wins
    (rare; squad ids are synthetic so no exact id-join exists — see #16). Malformed
    rows are skipped and a missing file yields {}, so the snapshot degrades to
    "proj n/a", never a crash."""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                if int(row["gw"]) != gw:
                    continue
                key = (normalize_name(row["web_name"]), row["pos"])
            except (TypeError, ValueError, KeyError):
                continue  # malformed pipeline row -> skip, never abort the load
            if not key[0]:
                continue  # a name that folds to empty ("Bruno G.") can't be joined
            out.setdefault(key, {
                "xpts": _f(row.get("xpts")),
                "horizon_xpts": _f(row.get("horizon_xpts")),
                "xmins": _f(row.get("xmins")),
            })
    return out


# --- distiller: state + projections -> prose facts (never raw JSON) -------------------

def _name_by_id(picks, pid):
    for p in picks:
        if p["id"] == pid:
            return p["name"]
    return f"#{pid}"


def _money(v):
    """Format £m, tolerating a missing/None scalar on a partially-init state."""
    return f"£{v:.1f}m" if isinstance(v, (int, float)) else "£n/a"


def _season_str(state):
    """Display season from state's stored '2026-27' -> '2026/27'. The model has no
    innate sense of 'when', so this concrete season is the time anchor; falls back
    to a neutral label rather than inventing one when state omits it."""
    s = state.get("season")
    return s.replace("-", "/") if isinstance(s, str) and s else "the current"


def _projection_for(pick, projections):
    return projections.get((normalize_name(pick["name"]), pick["pos"]))


def _proj_str(pick, projections):
    hit = _projection_for(pick, projections)
    if hit and hit.get("xpts") is not None:
        return f"{hit['xpts']:.1f} pts"
    return "proj n/a"


def _pick_line(pick, projections):
    return (f"- {pick['name']} ({pick['pos']}, {pick['club']}, "
            f"£{pick['price']:.1f}m) — {_proj_str(pick, projections)}")


def season_snapshot(state, projections):
    """Distilled 'my season' facts as markdown. The single source of squad truth
    is season-state.json; projections enrich it by name-join where available."""
    gw = state.get("current_gw")
    squad = state.get("squad", {})
    picks = squad.get("picks", [])
    starters = [p for p in picks if p.get("starting")]
    bench = sorted((p for p in picks if not p.get("starting")),
                   key=lambda p: (p.get("bench_order") is None, p.get("bench_order")))
    captain = _name_by_id(picks, state.get("captain"))
    vice = _name_by_id(picks, state.get("vice"))

    first_half = state.get("chips", {}).get("first_half", {})
    chips_left = [k for k, v in first_half.items() if v == "available"]

    matched = [p for p in starters
               if (_projection_for(p, projections) or {}).get("xpts") is not None]
    xi_total = sum(_projection_for(p, projections)["xpts"] for p in matched)

    season = _season_str(state)
    started = state.get("season_start")
    when = f" (it began {started})" if started else ""
    lines = [
        f"## My squad — GW{gw}",
        f"> Time anchor: it is the **{season} Premier League season, gameweek "
        f"{gw}**{when}. You were trained before this season, so your own memory of "
        "the calendar is out of date — anchor every judgment on this season and "
        "gameweek, never on an earlier one. This squad, its clubs and prices are "
        "pulled live from the official FPL API and are ground truth: treat the "
        "clubs, promotions, and transfers below as fact, never flag them as corrupt "
        "or wrong from prior-season memory, and never evaluate this as any earlier "
        "season. An unexpected club means a real transfer, not bad data.",
        "",
        f"Objective: {state.get('objective')} · Risk: {state.get('risk_mode')}",
        f"Bank {_money(state.get('bank'))} · Free transfers: {state.get('free_transfers')} "
        f"· Squad value {_money(squad.get('value'))}",
        f"Captain: {captain} · Vice: {vice}",
        f"Chips left (first half): {', '.join(chips_left) if chips_left else 'none'}",
        "",
        f"Starting XI (projected GW{gw} pts):",
    ]
    lines += [_pick_line(p, projections) for p in starters]
    lines += ["", "Bench:"]
    lines += [_pick_line(p, projections) for p in bench]
    lines += [
        "",
        f"Projected XI total (GW{gw}): {xi_total:.1f} pts "
        f"across {len(matched)}/{len(starters)} matched players.",
    ]
    return "\n".join(lines)


# --- workspace: the agent/ markdown tree ----------------------------------------------

class Workspace:
    """Reads the `agent/` tree. Files are read fresh each call so a pull that
    updates markdown applies on the next wake (#7 runtime-assembled context)."""

    def __init__(self, root):
        self.root = root

    def _read(self, *parts):
        path = os.path.join(self.root, *parts)
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read().strip()

    def persona(self):
        return self._read("GAFFER.md")

    def memory_index(self):
        return self._read("memory", "MEMORY.md")

    def playbook(self, name):
        return self._read("playbooks", f"{name}.md")

    def report_index(self):
        """One line per gameweek-report folder listing its files — an index, not
        the bodies (index-then-fetch)."""
        reports = os.path.join(self.root, "reports")
        if not os.path.isdir(reports):
            return ""
        lines = []
        for gw_dir in sorted(os.listdir(reports)):
            full = os.path.join(reports, gw_dir)
            if not os.path.isdir(full):
                continue
            files = sorted(f for f in os.listdir(full) if not f.startswith("."))
            lines.append(f"- reports/{gw_dir}: {', '.join(files) if files else '(empty)'}")
        return "\n".join(lines)


_DEADLINE_KEYWORDS = ("deadline", "transfer plan", "lock the team", "who should i")
_REVIEW_KEYWORDS = ("post-gw", "post gw", "how did i do", "last gameweek", "last gw",
                    "gameweek review")


def select_playbook(user_text):
    """Route a message to today's playbook. The T−2h final check -> deadline-final;
    other deadline work -> deadline-brief; post-gameweek retrospectives ->
    post-gw-review; everything else (the common ad-hoc status question) ->
    squad-review, the conservative default that keeps a stray message grounded
    rather than mis-routed. The brief wake (#18) drives the two deadline
    playbooks via its synthetic user text ("… draft deadline brief" / "final
    pre-deadline check …")."""
    low = (user_text or "").lower()
    if "final" in low and "deadline" in low:
        return "deadline-final"
    if any(k in low for k in _DEADLINE_KEYWORDS):
        return "deadline-brief"
    if any(k in low for k in _REVIEW_KEYWORDS):
        return "post-gw-review"
    return "squad-review"


# --- assembler ------------------------------------------------------------------------

class Assembler:
    def __init__(self, workspace_root, state_path, projections_path=None,
                 cap_tokens=CAP_TOKENS, gw=None, approval_store_path=None):
        self.ws = Workspace(workspace_root)
        self.state_path = state_path
        self.projections_path = projections_path
        self.cap_tokens = cap_tokens
        self.gw = gw
        # When wired (#18), a live pending/approved plan is rendered as prose into
        # the prompt so debate replies are grounded in what a `yes` would lock.
        self.approval_store_path = approval_store_path

    def _headline(self, state):
        cap = _name_by_id(state.get("squad", {}).get("picks", []), state.get("captain"))
        return (f"{_season_str(state)} season · GW{state.get('current_gw')} · "
                f"{_money(state.get('bank'))} bank · {state.get('free_transfers')} FT "
                f"· (C) {cap}")

    def _plan_section(self):
        """(title, body) for the plan awaiting/approved, rendered as prose (never
        raw json — repo invariant). ("", "") when nothing is pending/approved, so
        it drops out of the optional-section list."""
        if not self.approval_store_path:
            return "", ""
        try:
            from daemon.plan import ApprovalStore, plan_prose
            st = ApprovalStore(self.approval_store_path).load()
            if st.pending_plan:
                return f"## Plan awaiting approval (GW{st.gw})", plan_prose(st.pending_plan)
            if st.approved_plan:
                return f"## Approved plan (GW{st.gw})", plan_prose(st.approved_plan)
        except Exception:            # noqa: BLE001 — a broken store never mutes the bot
            pass
        return "", ""

    def assemble_system_prompt(self, user_text):
        with open(self.state_path, encoding="utf-8") as f:
            state = json.load(f)
        gw = self.gw if self.gw is not None else state.get("current_gw")
        projections = load_projections(self.projections_path, gw)
        snapshot = season_snapshot(state, projections)

        headline = self._headline(state)
        persona = self.ws.persona()
        plan_title, plan_body = self._plan_section()
        # Index sections, highest-priority first (dropped lowest-first under budget).
        # The plan-awaiting section sits below the playbook, above the reports
        # index — grounding debate without displacing identity or the snapshot.
        optional = [(t, b) for t, b in (
            ("## Standing memory", self.ws.memory_index()),
            ("## Playbook", self.ws.playbook(select_playbook(user_text))),
            (plan_title, plan_body),
            ("## Gameweek reports", self.ws.report_index()),
        ) if b]

        # Must-keep = identity + the traceable facts, held at the two prompt edges
        # (headline on top, snapshot adjacent to the user turn). Index sections are
        # dropped lowest-priority-first until the *rendered* prompt — separators and
        # all — fits the cap, so trimming is never the disproportionate all-or-nothing
        # nuke of a single-token overflow.
        def render(sections):
            parts = [headline, persona] + [f"{t}\n{b}" for t, b in sections] + [snapshot]
            return "\n\n".join(p for p in parts if p)

        included = list(optional)
        prompt = render(included)
        while included and estimate_tokens(prompt) > self.cap_tokens:
            included.pop()  # drop the lowest-priority index section, re-measure
            prompt = render(included)
        if estimate_tokens(prompt) > self.cap_tokens:
            # Pathological: identity + facts alone exceed the cap. Keep the facts.
            prompt = "\n\n".join([headline, snapshot])[:_char_budget(self.cap_tokens)]
        return prompt

    def build_messages(self, user_text):
        return [
            {"role": "system", "content": self.assemble_system_prompt(user_text)},
            {"role": "user", "content": user_text},
        ]
