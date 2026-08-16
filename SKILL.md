---
name: fpl-api
description: Fetch, validate, distill, and diff Fantasy Premier League API data into compact snapshots. Use whenever the FPL pipeline needs fresh data — players, fixtures, gameweek deadlines, the user's entry — or when checking price/status/ownership changes between snapshots.
---

# fpl-api

> **Provisional** — this is a prior-effort Claude-Code-style skill file for the data layer only. Whether skills take this form, and whether the gaffer is a single agent or gaffer + assistant sub-agents (one skill per task or not), is an open architecture decision tracked in [#9](https://github.com/ropats16/fpl-pi-manager/issues/9) (blocked by runtime lock [#7](https://github.com/ropats16/fpl-pi-manager/issues/7)). Kept and link-corrected here; do not treat its shape as settled.

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
