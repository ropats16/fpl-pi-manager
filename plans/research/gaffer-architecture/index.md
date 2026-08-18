# plans/research/gaffer-architecture — content catalog

Research for [#9 Decision: gaffer architecture](https://github.com/ropats16/fpl-pi-manager/issues/9).
Karpathy-wiki convention ([CONVENTIONS](../team-selection/CONVENTIONS.md)): immutable `raw/`
agent reports; synthesized pages at top level; `log.md` append-only. Fresh pass beyond
#24/#25 per the map's fresh-discovery mandate. All raws produced by Claude Opus 4.8
orchestrators with Opus 4.8 leaf agents, tight-ship anti-fabrication rules.

## Synthesis
- [synthesis.md](synthesis.md) — converged findings across the three tracks + the #25 run
  study; cost shape; the open decisions the #9 grilling must resolve.

## Raw (immutable — one file per research track)
- [raw/agent-org-design.md](raw/agent-org-design.md) — track A: single-vs-multi evidence,
  blackboard/stigmergy support for stepwise scheduling, persona/skill/memory file
  conventions + failure modes, prompt assembly under a token ceiling, cheap-worker QC.
- [raw/season-long-machinery.md](raw/season-long-machinery.md) — track B: multi-period MILP
  (from solver source), chip-timing machinery, price/team-value, learning loop, the
  season cadence table, replanning triggers. Includes two corrections fed back to the
  team-selection wiki (logged there 2026-08-18).
- [raw/reference-systems.md](raw/reference-systems.md) — track C: adversarial proof audit
  of FPL Review / open solver / OpenFPL / academic systems; no verifiable live ranks exist
  anywhere; benchmark targets (top 100k sustained; beat set-and-forget floor).
