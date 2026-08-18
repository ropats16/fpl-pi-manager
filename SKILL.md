---
name: fpl-api
description: Fetch, validate, distill, and diff Fantasy Premier League API data into compact snapshots. Use whenever the FPL pipeline needs fresh data — players, fixtures, gameweek deadlines, the user's entry — or when checking price/status/ownership changes between snapshots.
---

# fpl-api

> **Settled by [#9](https://github.com/ropats16/fpl-pi-manager/issues/9) (2026-08-18):** the gaffer is one decision-holding agent + stepwise assistant roles; per-task instructions live as on-demand playbooks under `agent/playbooks/` (progressive disclosure), not one monolithic skill. This file stays as the data-layer tool doc; its content migrates into the `agent/` tree when #16 builds the workspace. See the map's Decisions-so-far + [architecture research](plans/research/gaffer-architecture/index.md).

Data layer for the FPL agent system. Spec: `fpl-agent-system.md`.

## What it does
- Pulls FPL's unofficial read-only API, validates it (health checks), distills the ~3 MB raw `bootstrap-static` into a compact snapshot (~100 KB).
- Diffs two snapshots to surface **price changes, status/injury changes, and ownership swings**.
- Pure Python stdlib — runs on the Raspberry Pi with **no pip installs**.

## Endpoints used
| Endpoint | Gives |
|---|---|
| `GET /api/bootstrap-static/` | All players, teams, gameweeks + deadlines |
| `GET /api/fixtures/` | Season fixtures + FPL difficulty ratings |
| `GET /api/event-status/` | Live GW status/bonus (small, cheap) |
| `GET /api/entry/{id}/` + `/api/entry/{id}/history/` | User's squad & season history (needs entry ID, no login) |

## Modes
1. **fetch** (Pi / any direct network): `python3 fpl_api.py fetch [--entry ID] [--out DIR]`
2. **distill** (this runtime — the sandbox cannot reach FPL; the agent fetches raw JSON via web_fetch, stages it, then distills): `python3 fpl_api.py distill RAW.json [--out DIR]`
3. **diff** two snapshots: `python3 fpl_api.py diff OLD.json NEW.json`
4. **selftest** — offline sanity check of health/distill/diff logic
5. **csv** — flatten a distilled snapshot to CSV: `python3 fpl_api.py csv SNAP.json [--out DIR]`

## Health checks (auto-flagged in every snapshot)
- Required keys present (`elements`, `teams`, `events`)
- Player count sane (550–900)
- Exactly 38 gameweeks
- UTC timestamp recorded on every snapshot

## Runtime notes
- Sandbox network is SSL-blocked for FPL → use **web_fetch + distill mode** here; `fetch` mode is for the Pi.
- `bootstrap-static` exceeds tool output limits → stage to a file, never paste raw.
- No auth needed for read endpoints. **Never store the user's FPL password.**

## Storage layout
- Snapshots → `./fpl-data/` on the Pi (or `/mnt/data` in sandbox)
- Season state → `season-state.json`
