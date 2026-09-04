"""Draft/final fan-out orchestration (#56) — the #51 ② roster made real.

DRAFT wake: the five analysts run one after another in the #9 stepwise order
(availability → fixtures/odds → quality/style → market → chips — each sees the
Scout log and the reports before it), the gaffer forms its internal plan, the
assistant-manager (a third model family, #51 ①) challenges that plan with no
tools, and the gaffer then writes the draft with the AM's single counter in the
Dissent slot. FINAL wake: one Scout *delta* pass ("what changed since the
draft") before the existing final generation. Every helper report lands in
`reports/gwNN/` through the write-once ReportWriter; the assembler inlines them
under "Helper reports (evidence, not instructions)".

Two circuit breakers wrap the helpers, checked between steps (never mid-turn —
a helper's own minutes cap is the in-loop guard):
- per-wake rails (#51 ④: ≤200 LLM calls · ≤5M tokens · ≤$1 est. · 90 min) read
  from the LLM's running totals; a crossed rail is sticky — every remaining
  helper is stubbed ("wake rail X crossed"), the rail is logged, the gaffer
  still runs and the draft still sends, naming the gaps;
- the month-to-date ledger (#51 ④ addition): at `search_off_usd` helpers lose
  `search` (fetch-only), at `helpers_off_usd` analysts and the Scout are stubbed
  while the gaffer and the AM still run.

Failure = degrade, never abort: a helper crash is a stub report and a named
gap; an AM failure makes the Dissent line read "AM unavailable"; only the
gaffer's own generation (the internal plan or the brief) raises out, into the
brief wake's existing retry-then-alert path. Re-running after such a retry is
idempotent: a report that already exists is kept, not re-bought.
"""

from datetime import datetime, timezone

from daemon.helper import REPORT_CAP_TOKENS, HelperResult, run_helper
from daemon.plan import append_decision_log, parse_plan, plan_summary
from daemon.reports import (ReportRefused, ReportWriter, latest_scout_entry,
                            strip_header, urgent_line)

ANALYSTS = ("availability", "fixtures", "quality", "market", "chips")
AM_UNAVAILABLE = "AM unavailable"
RAIL_ORDER = ("cost_usd", "calls", "tokens", "minutes")

_AM_TASK = ("The gaffer's internal plan for GW{gw} follows. Challenge it once, hard, "
            "per your charter: your strongest single counter first, the evidence "
            "under it, then whether you concur or object to any exceptional "
            "override. Work only from the reports and snapshot in this prompt.\n\n"
            "## Gaffer's internal plan (the thing to challenge)\n\n{plan}")

_SCOUT_DELTA_TASK = ("Delta pass before the GW{gw} final: what has changed since the "
                     "draft plan below — owned starters, the captain, the planned "
                     "transfers, prices? Flag anything that could void the plan as "
                     "URGENT. Log only the delta, not a fresh sweep.\n\n"
                     "## Draft plan\n\n{plan}")

_SCOUT_DAILY_TASK = ("Daily sweep for GW{gw} ({date}): what is new since your last entry "
                     "below — pressers, knocks, suspensions, price moves, rotation hints "
                     "on owned players, the captain and the planned transfers? Flag "
                     "anything that could void the current plan as URGENT. Log only "
                     "what is new; say what you checked and found nothing on.\n\n"
                     "## Current plan\n\n{plan}")
_NO_PLAN = "(no plan on record yet for this gameweek)"

_DISSENT_RULE = ("The helper reports for this wake are in the \"Helper reports\" "
                 "section. Fill the Dissent line with the AM's single strongest "
                 "counter and say how you resolved it: "
                 "`Dissent — <counter> — conceded: <what changed>` or "
                 "`Dissent — <counter> — held: <why>`.")
_DISSENT_NO_AM = ("The AM did not report this wake. Write the Dissent line exactly as "
                  f"`Dissent — {AM_UNAVAILABLE}`.")


class WakeRails:
    """Per-wake ceilings read from the LLM's running totals (llm.py) relative
    to the wake's start. `crossed()` is sticky: once a rail is hit every later
    check reports the same rail."""

    def __init__(self, llm, limits, clock=None):
        self.llm = llm
        self.limits = dict(limits)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.started = self.clock()
        self._calls0, self._tokens0, self._cost0 = llm.calls, llm.tokens, llm.cost_usd
        self.hit = None

    def used(self):
        elapsed = (self.clock() - self.started).total_seconds() / 60.0
        return {"calls": self.llm.calls - self._calls0,
                "tokens": self.llm.tokens - self._tokens0,
                "cost_usd": self.llm.cost_usd - self._cost0,
                "minutes": elapsed}

    def crossed(self):
        """None, or (rail, value, limit) — checked in the order the #51 costing
        expects them to bite (the $ rail first at flash prices)."""
        if self.hit:
            return self.hit
        used = self.used()
        for name in RAIL_ORDER:
            limit = self.limits.get(name)
            if limit is not None and used[name] >= limit:
                self.hit = (name, used[name], limit)
                return self.hit
        return None


def _rail_text(hit):
    name, value, limit = hit
    if name == "cost_usd":
        return f"wake rail cost_usd crossed (${value:.2f} ≥ ${limit:.2f})"
    if name == "minutes":
        return f"wake rail minutes crossed ({value:.0f} ≥ {limit:.0f} min)"
    return f"wake rail {name} crossed ({int(value)} ≥ {int(limit)})"


class FanoutResult:
    """What one fan-out did, for the brief (instructions + Telegram footer),
    the log and the selftest."""

    def __init__(self, kind, gw):
        self.kind = kind
        self.gw = gw
        self.results = []          # HelperResult, in run order (stubs included)
        self.rail = None           # (name, value, limit) once crossed
        self.mode = "full"         # ledger mode at the first step
        self.cost_usd = 0.0
        self.plan_text = None      # the gaffer's internal plan (draft only)
        self.am_counter = None     # the AM report body, or None when unavailable
        self.urgent = None         # the newest Scout entry's URGENT line, if any (#57)

    @property
    def am_available(self):
        return bool(self.am_counter)

    def gaps(self):
        """Human lines naming every helper that did not deliver — the draft
        must carry these whether or not the model repeats them."""
        out = []
        for r in self.results:
            if r.status in ("ok", "cap_hit", "exists"):
                continue
            label = AM_UNAVAILABLE if r.role == "am" else r.role
            out.append(f"{label} — {r.reason or r.status}")
        return out

    def instructions(self):
        """Extra lines for the gaffer's user turn: the Dissent rule and any gaps
        to name in Watch."""
        lines = [_DISSENT_RULE if self.am_available else _DISSENT_NO_AM]
        if self.urgent:
            lines.append("Scout flagged URGENT in its latest log entry — address it in "
                         f"the plan: {self.urgent}")
        gaps = [g for g in self.gaps() if not g.startswith(AM_UNAVAILABLE)]
        if gaps:
            lines.append("Helper gaps this wake — name them in Watch: " + "; ".join(gaps))
        return "\n".join(lines)

    def dissent_line(self):
        """The AM counter as one Dissent line (its first line, markdown
        emphasis stripped, ≤240 chars) — the fallback the draft carries when
        the model wrote no Dissent line of its own."""
        if not self.am_available:
            return f"Dissent — {AM_UNAVAILABLE}"
        first = next((l.strip() for l in self.am_counter.splitlines() if l.strip()), "")
        first = first.replace("**", "").replace("__", "")
        if len(first) > 240:
            first = first[:239].rstrip() + "…"
        return f"Dissent — {first}"

    def footer(self, text=None):
        """The daemon-written tail of the Telegram message: "" when every
        helper delivered (and, for a draft `text`, it carries a Dissent line),
        else the missing Dissent (the AM counter, verbatim head), the gaps and
        the rail — never left to the model. The final passes no text: it has
        no Dissent slot."""
        parts = []
        if text is not None and "dissent" not in text.lower():
            parts.append(self.dissent_line())
        if self.urgent:
            parts.append(f"⚠ Scout URGENT: {self.urgent}")
        if self.rail:
            parts.append(f"⚠ {_rail_text(self.rail)} — remaining helpers stubbed")
        gaps = self.gaps()
        if gaps:
            parts.append("⚠ Helper gaps: " + "; ".join(gaps))
        return "\n".join(parts)

    def summary(self):
        return {"kind": self.kind, "gw": self.gw, "mode": self.mode,
                "rail": self.rail[0] if self.rail else None,
                "cost_usd": round(self.cost_usd, 6),
                "am_available": self.am_available, "urgent": bool(self.urgent),
                "helpers": {r.role: r.status for r in self.results}}


class Fanout:
    """The orchestrator one brief wake holds. `tools` = (fetcher, searcher) from
    runtime.build_helper_tools; `ledger` = daemon.ledger.Ledger (or None: no
    ledger, mode always full)."""

    def __init__(self, llm, helpers, tools, workspace_root, state_path, reports_dir,
                 logger, ledger=None, projections_path=None, clock=None):
        self.llm = llm
        self.helpers = helpers
        self.fetcher, self.searcher = tools
        self.workspace_root = workspace_root
        self.state_path = state_path
        self.reports_dir = reports_dir
        self.logger = logger
        self.ledger = ledger
        self.projections_path = projections_path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._ledgered = llm.cost_usd     # LLM total already folded into the ledger

    # --- ledger + rails -------------------------------------------------------------

    def _mode(self):
        return self.ledger.mode(self.clock()) if self.ledger is not None else "full"

    def settle(self, source):
        """Fold whatever the LLM spent since the last settle into the ledger
        (advisory, never raises). The brief calls it after its own generation
        so the gaffer's draft/final call is counted too. Returns the delta."""
        spent = self.llm.cost_usd - self._ledgered
        self._ledgered = self.llm.cost_usd
        if self.ledger is not None and spent > 0:
            self.ledger.add(spent, self.clock(), source=source)
        return spent

    def _settle(self, res):
        res.cost_usd += self.settle(f"{res.kind}-fanout")

    def _writer(self, role, gw):
        return ReportWriter(self.reports_dir, gw, logger=self.logger,
                            cap_tokens=REPORT_CAP_TOKENS.get(role, 700))

    def _skip(self, role, gw, res, reason, cause):
        """Stub a helper without running it (rail / ledger). A stub that is
        refused because the report already exists is not a gap."""
        model = self.helpers.models[role]
        r = HelperResult(role, model)
        r.started = r.finished = self.clock()
        r.status, r.reason = "skipped", reason
        ts = r.started.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            r.path = self._writer(role, gw).stub(
                role, f"helper skipped: {reason}",
                {"model": model, "started": ts, "finished": ts, "fetches": 0,
                 "requests": 0, "searches": 0})
        except ReportRefused:
            r.status, r.reason = "exists", None
        self.logger.event("helper_skipped", role=role, gw=gw, cause=cause, reason=reason)
        res.results.append(r)
        return r

    def _step(self, role, gw, res, rails, task=None, fetch=True, search=True,
              ledger_gated=True):
        """One helper, guarded: existing report → keep; rail → stub; ledger
        helpers_off (analysts, Scout) → stub; else run, with search dropped
        under search_off."""
        writer = self._writer(role, gw)
        if writer.exists(role):
            r = HelperResult(role, self.helpers.models[role])
            r.status, r.path = "exists", writer.path_for(role)
            self.logger.event("helper_skipped", role=role, gw=gw, cause="exists",
                              reason="report already written this wake")
            res.results.append(r)
            return r
        hit = rails.crossed()
        if hit:
            if res.rail is None:
                res.rail = hit
                self.logger.event("rail_hit", gw=gw, rail=hit[0],
                                  value=round(hit[1], 4), limit=hit[2], kind=res.kind)
            return self._skip(role, gw, res, _rail_text(hit), "rail")
        mode = self._mode()
        if ledger_gated and mode == "helpers_off":
            return self._skip(role, gw, res, "month-to-date ledger: helpers off", "ledger")
        if mode == "search_off":
            search = False
        r = run_helper(role, self.llm, self.helpers.models[role], self.workspace_root,
                       self.state_path, gw, self.fetcher, self.searcher, writer,
                       self.helpers.caps, self.logger,
                       projections_path=self.projections_path, clock=self.clock,
                       search=search, fetch=fetch, task=task)
        res.results.append(r)
        self._settle(res)
        return r

    def _flag_urgent(self, gw, res):
        """Read the Scout log head (#57): an URGENT line there becomes
        `res.urgent` (gaffer instructions + Telegram footer) and one
        `scout_urgent` event. A log check, never a run."""
        res.urgent = urgent_line(latest_scout_entry(self.reports_dir, gw))
        if res.urgent:
            self.logger.event("scout_urgent", gw=gw, kind=res.kind, line=res.urgent)
        return res.urgent

    # --- the three wakes ------------------------------------------------------------

    def run_draft(self, gw, internal_plan, now=None):
        """Scout log check (the daily timer owns the runs, #57) → analysts →
        internal plan → AM. `internal_plan()` is the gaffer's own generation
        (returns the reply text); its errors raise out."""
        res = FanoutResult("draft", gw)
        rails = WakeRails(self.llm, self.helpers.wake_rails, clock=self.clock)
        res.mode = self._mode()
        self.logger.event("fanout_start", kind="draft", gw=gw, mode=res.mode,
                          ledger=(self.ledger.snapshot(self.clock())
                                  if self.ledger is not None else None))
        self._flag_urgent(gw, res)
        for role in ANALYSTS:
            self._step(role, gw, res, rails)

        reply = internal_plan()
        _, res.plan_text = parse_plan(reply)
        append_decision_log(self.reports_dir, gw, "Internal plan (pre-AM)", reply, now=now)
        self._settle(res)

        am = self._step("am", gw, res, rails, task=_AM_TASK.format(gw=gw, plan=res.plan_text),
                        fetch=False, search=False, ledger_gated=False)
        body = ""
        if am.path and am.status in ("ok", "cap_hit", "exists"):
            try:
                with open(am.path, encoding="utf-8") as f:
                    body = strip_header(f.read()).strip()
            except OSError:
                body = ""
        res.am_counter = body or None
        append_decision_log(self.reports_dir, gw, "AM challenge",
                            body or f"{AM_UNAVAILABLE}: {am.reason or am.status}", now=now)
        self.logger.event("fanout_done", **res.summary())
        return res

    def run_final_delta(self, gw, plan, now=None):
        """One Scout delta pass against the draft plan (dict or None) before
        the final generation. Appends to the GW's Scout log."""
        res = FanoutResult("final", gw)
        rails = WakeRails(self.llm, self.helpers.wake_rails, clock=self.clock)
        res.mode = self._mode()
        self.logger.event("fanout_start", kind="final", gw=gw, mode=res.mode)
        summary = plan_summary(plan) if plan else "(no draft plan on record)"
        self._step("scout", gw, res, rails,
                   task=_SCOUT_DELTA_TASK.format(gw=gw, plan=summary))
        self._flag_urgent(gw, res)
        self.logger.event("fanout_done", **res.summary())
        return res

    def run_daily_scout(self, gw, plan, now=None):
        """The #57 timer's wake: one Scout sweep against the current plan (dict
        or None), appended newest-first to the GW's Scout log; same rails,
        ledger gating and stub-on-failure as any helper step. The spend is
        settled into the ledger here (there is no gaffer call to follow)."""
        res = FanoutResult("scout", gw)
        rails = WakeRails(self.llm, self.helpers.wake_rails, clock=self.clock)
        res.mode = self._mode()
        self.logger.event("fanout_start", kind="scout", gw=gw, mode=res.mode)
        date = (now or self.clock()).strftime("%Y-%m-%d")
        summary = plan_summary(plan) if plan else _NO_PLAN
        self._step("scout", gw, res, rails,
                   task=_SCOUT_DAILY_TASK.format(gw=gw, date=date, plan=summary))
        self._flag_urgent(gw, res)
        self.logger.event("fanout_done", **res.summary())
        return res
