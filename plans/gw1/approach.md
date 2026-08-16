# GW1 quick selection — approach

Design note for the pre-deadline GW1 run. Records *why* it's shaped this way,
so the reasoning is in-repo and cross-linkable. 2026-08-16.

Related: [#1 spec](https://github.com/ropats16/fpl-pi-manager/issues/1) · issues [#24](https://github.com/ropats16/fpl-pi-manager/issues/24)
(research) and [#25](https://github.com/ropats16/fpl-pi-manager/issues/25) (the run) ·
the pipeline gate [#4](https://github.com/ropats16/fpl-pi-manager/issues/4) ·
post-GW review [#21](https://github.com/ropats16/fpl-pi-manager/issues/21).

## The problem this solves

GW1 deadline is **Fri 2026-08-21 17:30 UTC**. The full-vision gaffer daemon
isn't live yet. We don't want to lock a team a week early on last-season points
and a bare optimizer run — pre-season is exactly when form, friendlies, new
signings, and injuries move things. But we also can't miss the deadline waiting
for the whole system.

So: a **one-shot, run-here (Claude Code) miniature of the end vision** that
produces a genuinely-reasoned GW1 brief now — while the durable daemon is built
in parallel over the following days.

## Two tickets, sequenced

**#24 — Research (must finish first).** Ground the gaffer in evidence-backed
football/FPL analytics so it decides on fundamentals, not hypotheses. Its job
is to *discover* the decision axes (the seed list is not a ceiling) and to find
& recommend preferred data sources (official / tier-1 / top FPL-draft
communities), cross-referenced. **Done (2026-08-16):** output is the
[team-selection research wiki](../research/team-selection/index.md) — start at
[importance-ranking](../research/team-selection/importance-ranking.md). The #25
run's decision-log MUST cross-link the relevant wiki pages per the acceptance
criteria.

**#25 — GW1 quick selection (needs #4 + #24).** A parent **gaffer** agent
delegates to **sub-agents by angle** — form; friendlies (checked against a
"class-player" prior so a quiet Haaland friendly doesn't wrongly downgrade
proven quality); fixtures + betting odds; head-to-head / matchup context
(rivalries, low/mid-block styles, a low team beating a big one); value/price;
status/injuries; and the **optimizer as one voice among many**. The gaffer
synthesizes with its **own judgment weighting**, free to overrule the optimizer
wholesale, building on #24's methods and doing its own current-season research.

## Key design decisions

- **Optimizer as one input, not the answer.** The run's implicit test is
  *"is the optimizer actually doing a good job?"* — so it's audited by the
  broader signal set, not trusted by default.
- **Gaffer judgment over a fixed weight table.** Weights are the gaffer's call
  per decision, *but every judgment is documented* — the values used, the
  weights leaned on, the rationale — so weightings are learnable post-GW.
- **The assistant manager is a sub-agent, not Rohit.** An assistant-manager
  agent pushes back on the gaffer's calls with evidence; the gaffer holds final
  judgment on whether to accept. Rohit is an **observer** — free to intervene,
  but not an active step in the loop.
- **Not necessarily the final team.** Once the full-vision gaffer + sub-agents
  are live over the following days, they may amend this selection if new intel
  lands before the deadline. #5 (plain optimizer brief) remains the guaranteed
  fallback if this run overruns.

## Outputs (this ticket, when run)

- `plans/gw1/brief.md` — XI, bench, captain/vice, transfers vs the recorded
  Aug-5 squad, reasoning.
- `plans/gw1/decision-log.md` — signals, weights, rationale per decision, and
  where the gaffer accepted/rejected the assistant manager's pushback.
  Cross-linked to `plans/research/` and the map. This is the **baseline for
  post-GW review** (#21).

## Documentation convention — Karpathy LLM wikis

As project docs grow, synthesize them as an **LLM-maintained wiki** rather than
letting Markdown sprawl. Convention (from
[Karpathy's gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)):

- **Three layers**: immutable *raw sources* (research, snapshots) the LLM never
  edits · an *LLM-owned wiki* of atomic, cross-linked pages · a *schema doc*
  (CLAUDE.md-style) defining the conventions.
- **`index.md`** — content catalog with one-line summaries; **`log.md`** —
  append-only `## [DATE] operation | title` record of ingests/queries/lints.
- The LLM does the bookkeeping: one new source touches ~10–15 pages,
  cross-refs auto-maintained; periodic "lint" for contradictions, stale
  claims, orphaned pages, missing links.

We adopt this where doc complexity warrants it — noted here so future-you (and
anyone shown the project) knows the intended system.
