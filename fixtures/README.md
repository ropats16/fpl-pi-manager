# fixtures/ — offline pipeline inputs

Committed, deterministic inputs for `./run_pipeline.sh offline` — the file-contract
seam that lets the whole math pipeline run and be verified with **no network**.

- `bootstrap.json` — distilled `bootstrap-static` snapshot (players, teams, 38 events).
- `fixtures.json` — distilled fixtures snapshot (FDR, home/away, kickoff).

Both are **distilled** outputs of `fpl_api.py` (kind/health/fetched_at + arrays), the same
shape a live `fetch` produces. `run_pipeline.sh offline` feeds them straight into
`fpl_api.py csv` → `fpl_projections.py` → `fpl_optimizer.py`.

Provenance: real FPL data snapshotted 2026-08-02 (pre-2026-27 GW1), public read-only API
only — **no entry/PII**. Refresh by copying a newer distilled snapshot over these files.
The `fpl_api.py csv` step gates on the bootstrap's embedded health checks (player-count
550–900, exactly 38 events) and aborts rather than emit CSVs from a bad snapshot.

## season-state round-trip inputs (`season_state.py selftest`)

- `entry.json` — a **scrubbed, synthetic** `/entry/{id}/` payload (fake id `9999999`, no
  real name/region). Feeds the `init` step of the read→act→write-back test — **no PII**.
- `squad-decision.json` — a legal 15-man GW1 build (2 GKP / 5 DEF / 5 MID / 3 FWD, £100.0m,
  club cap ≤3), derived from `plans/gw1/brief.md`. **Element ids are synthetic placeholders**
  (real FPL ids don't exist pre-season, before any GW deadline locks picks); names, clubs,
  and prices are the brief's real values. It's the "decision" the write-back test acts on.
