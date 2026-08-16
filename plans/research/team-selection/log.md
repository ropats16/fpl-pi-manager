# Log — team-selection wiki

Append-only operations record. Newest at bottom. Format:
`## [YYYY-MM-DD] operation | title`.

## [2026-08-16] ingest | initial build from 11 background research runs (#24)

- Ran 11 Opus-4.8 background research agents for issue
  [#24](https://github.com/ropats16/fpl-pi-manager/issues/24), in four waves:
  1. **Seed clusters (4):** core predictive signals; fixtures/context/set-pieces;
     value/captaincy + new-axis discovery; data sources.
  2. **Open-ended discovery (3):** quant/modeling lens; elite-practitioner lens;
     first-principles/adjacent-domain lens — each told to ignore the seed list
     and surface what the evidence says matters.
  3. **Gap follow-ups (3):** squad construction/budget; player-availability data
     sources; signal-synthesis methodology.
  4. **Reference pipelines (1):** open-source FPL models/optimizers whose
     documented methods we can adopt.
- Outputs preserved verbatim in [`raw/`](raw/) (immutable layer).
- Synthesised into this wiki: [importance-ranking.md](importance-ranking.md),
  five factor/method pages, [class-player-prior.md](class-player-prior.md),
  [sources/data-sources.md](sources/data-sources.md).
- Applied the evidence gate (proven / standard / candidate) per Rohit's
  instruction to only adopt FPL methods wholesale when they have documented
  results.
- Wired into [../../map.md](../../map.md) (Decisions-so-far) and referenced from
  [../../gw1/approach.md](../../gw1/approach.md).

Open lint items for a later pass:
- Set-piece/penalty **taker identities** and the early-season **template** are
  current-season facts that go stale fast — they belong to the [#25](https://github.com/ropats16/fpl-pi-manager/issues/25)
  run, not here. This wiki carries the *method* for finding them, not the list.
- A few claims rest on tier-2 FPL blogs (flagged inline); upgrade to primary
  where a better source appears.

## [2026-08-16] lint | two-axis code-review pass

Ran `/code-review` (Standards + Spec sub-agents, Opus 4.8). Spec: substantially
satisfied — all 11 seed axes present with method+weight+evidence, discovery goal met,
data sources named+justified, class-player prior applicable; only the decision-log
reference AC is deferred to [#25](https://github.com/ropats16/fpl-pi-manager/issues/25).
Standards: link integrity clean, schema obeyed. Fixed the flagged items:
- Single-sourced the optimizer MILP constants in [methods/squad-construction.md](methods/squad-construction.md#optimizer-objective--constraints);
  [methods/reference-pipelines.md](methods/reference-pipelines.md) and
  [importance-ranking.md](importance-ranking.md) now cross-link instead of duplicating
  the numbers (was Divergent-Change over 3 pages).
- Defined the evidence-strength tier vocabulary (`[proven]/[standard]/[tier-1]/[tier-2]`)
  in [CONVENTIONS.md](CONVENTIONS.md), distinct from the method-gate tags.
- Aligned the top-50 MID budget figure (41%, effective) across pages; cleaned three
  link display-texts (targets were already correct).
