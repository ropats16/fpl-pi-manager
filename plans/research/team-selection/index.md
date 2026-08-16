# Team-selection research — index

Evidence-backed survey of what drives good FPL / football team selection, for issue
[#24](https://github.com/ropats16/fpl-pi-manager/issues/24) (parent
[#1](https://github.com/ropats16/fpl-pi-manager/issues/1)). This is the gaffer's
**briefing, not a rulebook** — it may overrule any finding it judges it knows better,
but logs the override. Built 2026-08-16 from 11 Opus-4.8 background research runs; see
[log.md](log.md).

An **LLM-maintained wiki** (Karpathy convention) — conventions in
[CONVENTIONS.md](CONVENTIONS.md). Three layers: immutable [`raw/`](raw/) sources · the
curated pages below · the schema doc.

## Start here

- **[importance-ranking.md](importance-ranking.md)** — every axis (seed + discovered)
  ranked by suggested weight, **method-first**, evidence-tagged, each linked to its page.
  The money page for the [#25](https://github.com/ropats16/fpl-pi-manager/issues/25) run.
- **[class-player-prior.md](class-player-prior.md)** — the concrete, applicable
  class-player prior (Bayesian shrinkage formula + a GW1 recipe).

## Factor pages (what each axis is & how it's used)

- **[factors/predictive-signals.md](factors/predictive-signals.md)** — minutes/xMins (the
  gate), betting odds, xG/xA, form recency, pre-season friendlies, finishing regression.
- **[factors/fixtures-and-context.md](factors/fixtures-and-context.md)** — fixture
  difficulty done properly, home/away, head-to-head (mostly noise), set-pieces/penalties,
  team style & usage share, promoted-team fragility, congestion & rest, referees,
  game-state.
- **[factors/scoring-dimensions.md](factors/scoring-dimensions.md)** — DEFCON, BPS, GK
  save volume (the 2026/27 rule-driven axes).
- **[factors/value-and-ownership.md](factors/value-and-ownership.md)** — effective
  ownership & the rank objective, captaincy EV, whole-XI covariance, price/value/
  differentials.
- **[factors/meta-and-timing.md](factors/meta-and-timing.md)** — multi-week planning,
  chip timing, DGW/BGW planning, transfer discipline, decision-timing option value,
  behavioural & season-start guardrails.

## Method pages (how the axes are combined & implemented)

- **[methods/squad-construction.md](methods/squad-construction.md)** — budget shape,
  bench/GK, formation, the optimiser objective/constraints, GW1-specific construction.
- **[methods/signal-synthesis.md](methods/signal-synthesis.md)** — gate-then-pool,
  market-vs-model blending, calibration/backtesting, "don't learn optimal weights", the
  decision-log template.
- **[methods/reference-pipelines.md](methods/reference-pipelines.md)** — open FPL
  pipelines to adopt (OpenFPL, open-fpl-solver, penaltyblog/Dixon-Coles), evidence-gated.

## Sources

- **[sources/data-sources.md](sources/data-sources.md)** — preferred sources for odds,
  friendlies, head-to-head, player availability, and general feeds, with de-vig how-to
  and the deadline-timing constraint.

## Raw (immutable evidence snapshots)

[`raw/`](raw/) — the 11 background-agent outputs verbatim, each fully cited: 4 seed
clusters (`cluster-A..D`), 3 discovery lenses (`discovery-quant/practitioner/firstprinciples`),
4 follow-ups (`followup-squad-construction/availability-sources/signal-synthesis/reference-pipelines`).

## Evidence gate (see [CONVENTIONS.md](CONVENTIONS.md))

Methods are tagged **[proven → adopt]** (documented results), **[standard → use]**
(established statistical technique), or **[candidate → evaluate]** (unvalidated — backtest
first). Per Rohit: adopt FPL methods wholesale only when they have documented results.
