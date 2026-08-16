# Conventions — team-selection wiki

Schema doc for this wiki (the Karpathy LLM-wiki "layer 3"). Defines how the
pages here are structured and maintained. Adopted per the convention recorded in
[../../gw1/approach.md](../../gw1/approach.md); origin
[Karpathy's gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Why a wiki and not one doc

Issue [#24](https://github.com/ropats16/fpl-pi-manager/issues/24) surfaced ~30
decision factors, ~5 method areas, and ~60 sources across 11 background research
runs. A single Markdown file would bury it. So the output is an atomic,
cross-linked wiki instead — small enough pages that [#25](https://github.com/ropats16/fpl-pi-manager/issues/25)
(and future sessions) pull only the page they need, and a new source touches a
handful of pages rather than one monolith.

## Three layers

1. **Raw sources (immutable)** — [`raw/`](raw/): the 11 background-agent outputs,
   verbatim. These are the cited-evidence snapshots. **Never edited.** Every wiki
   claim traces back to one of these (and through them to a primary URL). Dated
   2026-08-16.
2. **LLM-owned wiki (this layer)** — atomic, cross-linked pages: the factor
   pages ([`factors/`](factors/)), method pages ([`methods/`](methods/)), the
   data-source page ([`sources/`](sources/)), plus [importance-ranking.md](importance-ranking.md)
   and [class-player-prior.md](class-player-prior.md). Curated, synthesised,
   editable, kept consistent.
3. **Schema (this doc)** — the conventions.

Plus the bookkeeping pair: [index.md](index.md) (catalog + one-line summaries)
and [log.md](log.md) (append-only operations record).

## Page conventions

- **Cross-link liberally** with relative links: `[minutes / xMins](factors/predictive-signals.md#minutes--xmins)`.
  A link to a page that doesn't exist yet marks a page worth writing, not an error.
- **Cite every load-bearing claim** with a primary URL inline, or point to the
  `raw/` snapshot that holds the full citation. Prefer official > tier-1 analytics
  (Opta/StatsBomb/Understat/FBref, academic papers) > established FPL communities
  (r/FantasyPL, Fantasy Football Scout, FPL Review, FPL Oracle). FPL-blog folklore
  is labelled as such.
- **Evidence gate on methods** (per Rohit, 2026-08-16). Tag each method/technique:
  - **`[proven → adopt]`** — documented, verifiable results (e.g. OpenFPL's
    published hauler-RMSE vs a commercial benchmark; a solver with a public track
    record; an academic backtest).
  - **`[standard → use]`** — an established statistical technique, well-founded
    even if not FPL-benchmarked (de-vig, Dixon-Coles, James–Stein shrinkage,
    linear opinion pooling).
  - **`[candidate → evaluate]`** — reasonable but unvalidated; backtest before
    trusting. FPL folklore lives here until it earns better.
  Do **not** import an FPL heuristic wholesale on assertion alone.
- **Evidence-strength tiers** (distinct from the method-gate tags above — the gate
  rates *what to do with a method*, the tier rates *how strong the backing is*). Factor
  pages end with `Evidence tier: …` and [importance-ranking.md](importance-ranking.md)
  uses these in its Evidence column:
  - **`[proven]`** — documented, verifiable results (same bar as `[proven → adopt]`).
  - **`[standard]`** — an established statistical technique (same bar as `[standard → use]`).
  - **`[tier-1]`** — strong primary/official or top-analytics evidence (Opta/StatsBomb/
    Understat/FBref, academic papers, official rules).
  - **`[tier-2]`** (a.k.a. `[tier-2/folklore]`) — FPL-blog / community assertion,
    directional only; treat as `[candidate → evaluate]` until upgraded.
- **Weights are SUGGESTED and non-binding.** The gaffer sets weights by judgment
  per decision (see [../../gw1/approach.md](../../gw1/approach.md)); this wiki is
  its briefing, not a rulebook. It may overrule any finding it judges it knows
  better — but the override is logged (see [methods/signal-synthesis.md](methods/signal-synthesis.md)).
- **Season context: 2026/27.** Rules verified against official Premier League
  pages where asserted (DEFCON, BPS, chips). Convert relative dates to absolute.

## Maintenance

- **`index.md`** — one line per page; update when a page is added/retitled.
- **`log.md`** — append `## [YYYY-MM-DD] operation | title` for each ingest,
  query, or lint. Never rewrite history.
- **Lint** periodically: contradictions across pages, stale claims (rule changes,
  taker changes), orphaned pages, missing cross-links. Log the lint.
- **New source** → drop the snapshot in `raw/`, thread its findings into the
  relevant wiki pages, update `index.md`, append to `log.md`.
