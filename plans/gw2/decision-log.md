# GW2 2026-27 — Decision Log

Ad-hoc gaffer run (deadline-day, ~50 min to 2026-08-28 17:30 UTC). Same shape as
[GW1](../gw1/decision-log.md): parent gaffer + 4 Opus-4.8 research sub-agents
(team-news · GW1-review · fixtures/targets · market/meta, tight-ship anti-fabrication
rule) + independent Fable assistant-manager attacking the draft. Rohit approved and
executed the moves in the app himself. **Baseline for post-GW review
([#21](https://github.com/ropats16/fpl-pi-manager/issues/21)).**

- **Data provenance:** live FPL API (bootstrap 2026-08-28 16:46 UTC, entry 2928517)
  + live web (FFScout, RotoWire, PL.com, predicted-XI aggregators). Local projections
  regenerated from same snapshot; optimizer advisory only (cold-start ep_next model).
- **State going in:** GW1 = 43 pts, rank ~6.38M. Bank £0.0, TV £100.0, 1 FT, all
  chips available. Captain GW1: Haaland (blanked, 2).

## Decisions

**1. Transfer (1 FT, no hit): Yates (NFO 4.5) → Slater (HUL 4.5, id 290).**
Yates = structural zero (0 min GW1, not in predicted XI, NFO run bad to GW3).
Slater: 90 min, 6 pts GW1, Hull's pen + set-piece taker, only playable £4.5 MID
(tier otherwise dead: Hemmings/Crooks). Burn-now-vs-roll adjudicated FOR burn:
£0.0 bank means a Slater rise to 4.6 locks us out permanently; roll's option value
~nil since next week's 2 FT would buy this same move + one more anyway.

**2. XI (3-4-3):** Raya | Gabriel, Shaw, van Ewijk | Bruno (C), Mbeumo, Szoboszlai,
Slater | Haaland (VC), João Pedro, Calvert-Lewin.
**Bench:** 1 Mitchell · 2 Diop · 3 Hughes · GK Palmer.

**3. Captain Bruno over Haaland.** Both models edged Bruno (repo projections 4.75 v
4.00; RotoWire 6.40 v 6.26): MUN home v promoted IPS, on pens, community selling him
(depressed EO = rank-chase upside at 6.4M). Haaland away CRY tonight is his weakest
fixture of the run — his captain weeks are GW3 (COV H) and GW5 (SUN H). Accepted
risk, on record: Haaland hauls uncaptained tonight.

**4. AM overrule ACCEPTED — Mitchell benched for van Ewijk.** Draft had Mitchell
starting; AM: £4.5 CRY DEF home to MCI tonight with a CB (Riad) out = near-zero CS,
no attacking threat. van Ewijk (COV H v HUL) carries attacking-RB upside; Mitchell
plays tonight so he's a known quantity as first autosub by Sunday. All other AM
verdicts: agree (captain, transfer, Slater>van Ewijk in XI, DCL starts, chips hold).

**5. Chips: hold all four.** Expert bar for GW2 wildcard = 3-4 non-starters; we
have 2 (Yates now fixed, Hughes). Palmer is fodder-by-design, doesn't count.

## GW1 diagnosis (one line)

Everything except Yates/Hughes was variance, not structure — XI all played 90
(Haaland 0.74xG blank; Bruno/Mbeumo zeros in the 0-2 Hull shock). No panic sells.

## Post-deadline squad (manual tracking — the 15 as entered)

| Pos | Player | Club | £ |
|---|---|---|---|
| GK | Raya | ARS | 6.0 |
| GK | Palmer | IPS | 4.0 |
| DEF | Gabriel | ARS | 8.0 |
| DEF | Mitchell | CRY | 4.5 |
| DEF | Shaw | MUN | 4.5 |
| DEF | Diop | IPS | 4.0 |
| DEF | van Ewijk | COV | 4.0 |
| MID | Bruno Fernandes | MUN | 12.0 |
| MID | Mbeumo | MUN | 8.0 |
| MID | Szoboszlai | LIV | 7.0 |
| MID | Slater | HUL | 4.5 |
| MID | Hughes | CRY | 4.5 |
| FWD | Haaland | MCI | 15.5 |
| FWD | João Pedro | CHE | 7.6 (bought 7.5) |
| FWD | Calvert-Lewin | LEE | 6.0 |

Bank £0.0 · FT after this GW: 1 · hits: 0 · chips: all live.

## Handoff notes for the full gaffer

- **GW3 FT candidate #1: Calvert-Lewin out.** LEE has the hardest GW3-6 run in the
  league (~3.8 FDR). His GW2 (BRE H) was fine; the pain starts GW3.
- **Haaland captain GW3 (COV H) and GW5 (SUN H)** — pre-flagged premium weeks.
- **Palmer (IPS GK) never plays** (Scherpen is #1). Unfixable at £4.0/£0 bank;
  fine as fodder, matters only for Bench Boost.
- **Watchlist from research:** De Cuyper (BHA 4.6, 17 pts, 1.68xGI — unaffordable
  at £0 bank, keep watching), Isak→LIV (1.09xG blank GW1, buy-dip), C.Palmer CHE.
- **Szoboszlai holds extra value:** confirmed LIV pen + all set pieces GW1.
- **Sync note:** `season-state.json` deliberately NOT updated in this PR — the Pi
  rewrites its copy via `pull-squad` (run it post-deadline to pull the real GW2
  picks). Known hazard: the file is git-tracked AND Pi-rewritten; a committed change
  can conflict on the Pi and block `pull-reload.sh` merges. Worth a ticket: move it
  out of git or out of the merge path.
- **Verify after deadline:** FPL transfers endpoint still showed 0 transfers at
  time of writing (Rohit was entering it); confirm Yates→Slater registered via
  `/api/entry/2928517/transfers/`.
