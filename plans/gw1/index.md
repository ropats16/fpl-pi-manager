# plans/gw1 — content catalog

The GW1 2026-27 quick-selection run ([#25](https://github.com/ropats16/fpl-pi-manager/issues/25)).
LLM-maintained wiki ([Karpathy convention](approach.md#documentation-convention--karpathy-llm-wikis)):
immutable raw signals under `signals/`; the gaffer's synthesized deliverables at top level;
`log.md` = append-only operation record. Cross-links to the [research wiki](../research/team-selection/index.md)
and the [map](../map.md).

## Deliverables (the reviewed GW1 output)
- [brief.md](brief.md) — the squad: XI, bench, captain/vice, transfers note, headline calls, deadline checklist.
- [decision-log.md](decision-log.md) — signals, weights leaned on, per-decision rationale, assistant-manager pushback ledger, post-GW review hooks.

## Design
- [approach.md](approach.md) — why the run is shaped this way (optimizer-as-one-voice, gaffer judgment, AM-as-sub-agent).

## Raw signals (immutable — the five angle agents + AM, Opus 4.8)
- [signals/availability.md](signals/availability.md) — minutes GATE: nailedness, injuries, suspensions, friendlies, cheap enablers.
- [signals/fixtures-odds.md](signals/fixtures-odds.md) — GW1 fixtures, de-vigged 1X2/O-U, best attack/CS spots, promoted fragility.
- [signals/talent-style.md](signals/talent-style.md) — class-player prior, penalty/set-piece takers, usage share, summer role changes.
- [signals/value-ownership.md](signals/value-ownership.md) — live prices/EO, £100m budget shape, template vs differential, captaincy.
- [signals/optimizer-audit.md](signals/optimizer-audit.md) — the ILP on trial: reproduced, data-gap diagnosis, salvageable structure.
- [signals/gaffer-draft.md](signals/gaffer-draft.md) — the gaffer's pre-pushback draft (input to the AM).
- [signals/assistant-manager-pushback.md](signals/assistant-manager-pushback.md) — evidence-based challenge + concessions.

## Provenance note
Live official FPL API (obs 2026-08-16) + live web for odds/fixtures/team-news. The local
Aug-2 pipeline data was a cross-check only; its team labels are correct 2026-27, its
projection model is thin (see [decision-log §1](decision-log.md#1-the-premise-correction-assimilated-mid-run)).
