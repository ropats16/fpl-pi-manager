# Audit: fpl-pi-manager folder (2026-08-16)

Subagent audit of the Mac folder pre-git. Verbatim findings.

## Headline

**This is not a codebase. It is a flat download folder containing 8 files scraped out of a chat UI.** No `skills/`, no `agents/`, no `data/`, no `.git`, no subdirectories. The previous session's claimed inventory is roughly **50% fabricated or, at best, describes artifacts that only ever existed inside the chat runtime and on the Raspberry Pi — never on this Mac.**

## 1. File tree (as found)

```
fpl-pi-manager/          (8 files, 0 subdirs, 31.9 KB total, no .git)
├── SKILL.md                              2,192 B    2 Aug 12:58
├── season-state.json                       909 B    2 Aug 13:00
├── fpl_api.py                            6,753 B    2 Aug 13:18
├── _index.md                               668 B   16 Aug 09:48
├── fpl-2026-27-season-rules.md           1,383 B   16 Aug 09:48
├── fpl-agent-system.md                   7,985 B   16 Aug 09:48
├── fpl-data-source-reachability.md       2,876 B   16 Aug 09:48
└── fpl_projections.py                    8,933 B   16 Aug 09:56
```

### Provenance (xattrs)

All but one file carry `com.apple.quarantine` + `kMDItemWhereFroms`: downloaded via Brave from hyper.io chat UI in two batches — Aug 2 (`chat.hyper.io`: SKILL.md, season-state.json, fpl_api.py) and Aug 16 (`bot.hyper.io`: the four .md files). `fpl_projections.py` has no quarantine flag — pasted/scp'd/copied locally.

### Deleted-directory signal

APFS link count on the dir = 10 with 0 actual subdirs → consistent with **8 subdirectories having existed and been removed** — matching the claimed tree shape (`skills/fpl-api/`, `agents/hyper/memory/topics/`, etc.). The tree was flattened; files are the leaves stripped of their directories. All relative links in every md file are broken as a result.

## 2. Python files

### fpl_api.py — 176 lines, v0.1, stdlib-only ✅

Modes: `fetch [--entry ID] [--out DIR]` (default out `./fpl-data`), `distill`, `diff` (0.5pp ownership threshold), `selftest` (synthetic 600-player payload). `get()` has 2 retries/linear backoff/20s timeout; `health_bootstrap()` asserts elements/teams/events, 550–900 players, exactly 38 events. Hardcoded: FPL API base URL, UA `fpl-agent/0.1`, field allowlists. No secrets. Quality decent.

**Stale rev**: spec documents a `csv` mode (fetch/distill/csv/diff/selftest); this file has no `csv`. SKILL.md documents `/event-status/` and `/entry/{id}/history/` endpoints never called here.

### fpl_projections.py — 232 lines, v1/v1.1, stdlib-only ✅ (dead imports: json, math)

Model: `base_rate` (last-season pts/90 ⊕ ep_next; weight 0.7 if <450 min, else 0.25) × `minutes_share` (floor 0.10) × `fixture_mult` (position-split FDR tables, HOME_EDGE 1.06) × `status_mult` (a/d/i/s/u → 1.0/0.5/0.1/0/0; chance-of-playing clamp GW1 only) × `DECAY 0.96^i`. HORIZON 6 GWs. Handles DGWs and blanks. `DATA = Path("data")` — relative, CWD-dependent.

**Failing selftest**: v1.1 patch makes `minutes_share()` return 0.0 for <450 min, but `selftest()` still asserts `newguy xpts > 0` for a 0-minute player. The file's own verification gate is red — spec waves it off as "harmless by design", it isn't (kills regression checking).

### Integration gap

Projections reads `data/players.csv`+`fixtures.csv` "produced by fpl_api.py" — but this fpl_api.py produces only timestamped JSON. **Pipeline cannot run end-to-end on the Mac.** The csv-mode rev presumably lives on the Pi.

## 3. Markdown/JSON contents

- **season-state.json** — effectively empty: `entry_id`, `squad`, `bank`, `free_transfers`, `objective` all null, `history` [], `last_check` null. 12 days stale vs spec (squad built 08-05). Clearest proof the state loop was never wired. Chips modelled as two sets (first expires ~2027-01-02), risk_mode balanced, price sources livefpl.net + whatthef.pl.
- **fpl-agent-system.md** — the real master spec (created 08-01, updated 08-05, confidence high). 5 layers: Collect (cron) → Model (xPts 1–6 GW) → Decide (PuLP/CBC ILP + captaincy EV + Monte Carlo chips) → Deliver (Telegram) → Learn. Decisions: single agent not multi; cron + on-disk state, explicitly NOT 24/7 daemon; no automated transfers (ToS risk); no FPL password stored; sentiment analysis CUT. Facts: entry 2928517 "Magnificos"; full 15-man squad @ £100.0m listed (Roefs, Verbruggen, Senesi, Guéhi, Diop, Mitchell, Kadıoğlu, B.Fernandes, Semenyo, Hughes, Tavernier, Szoboszlai, Haaland, Kusi Asare, João Pedro); GW1 deadline Fri 2026-08-21 17:30 UTC; Pi = host `fplpi`, user `saf`, OS Lite 64-bit, `~/fpl/` with data/+logs/, nightly 03:30 cron claimed. Footgun noted: fetch defaults `./fpl-data`, Pi expects `data/` → pass `--out data`. Build log: 08-02/03 first green fetch (564 players/20 teams/38 events/380 fixtures); 08-05 squad built, youth bug fixed, optimizer built + selftest green (Bruno 31.7, Haaland 31.4, Semenyo 26.2, Guéhi 23.5, Senesi 23.2 xPts/6GW). Skills remaining: fpl-team-news, fpl-price-watch, fpl-deadline-brief, fpl-review. Open: Odds API key awaited, Telegram bot token uncreated, 26/27 rules unverified.
- **SKILL.md** — fpl-api manifest; documents 4 modes + 4 endpoints (2 unimplemented in the local py); broken paths to agents/ tree; never-store-password rule.
- **_index.md** — memory index, all 3 links broken, stale at 08-01.
- **fpl-2026-27-season-rules.md** — season starts Fri 21 Aug 2026 (World Cup delay), ends 30 May 2027; 33 weekend + 5 midweek rounds; transfer window closes after GW1; 8 chips in two sets (GW1–19 / GW20–38); ≤5 rolled FTs; DefCon points continue; post-WC rotation risk. Typo: chip-set-1 expiry "2 Jan 2026" should be 2027. FPL API event-1 deadline flagged as stale placeholder.
- **fpl-data-source-reachability.md** — working: FPL API, vaastav GitHub, Odds API (needs key), Telegram (needs token), Understat, premierinjuries, livefpl.net (React SPA — needs XHR sniffing). Dead: fplstatistics.co.uk. Blocked from chat runtime, retry on Pi: FBref (Cloudflare), fplreview, Reddit. Unprobed: whatthef.pl, fpl.solioanalytics.com, Tokvam Transfer Algorithm.

## 4. Discrepancies

Missing everywhere on the Mac (home dir searched to depth 8): **fpl_optimizer.py** (spec describes convincingly: PuLP ILP, scratch/from-squad/xi/selftest, 2/5/5/3 + budget + 3-per-club constraints, `--min-xmins 900`, needs `python3-pulp coinor-cbc`; built 08-05 per log — lives on Pi or lost in ephemeral sandbox), **draft_board.py** (pure hallucination — never in any doc), **data/** (no snapshots/CSVs at all), **MASTER-PLAN.md** (never existed; fpl-agent-system.md is the master plan). No FPL-related skills in ~/.claude/skills, no `hyper` dir anywhere.

## 5. Secrets / PII

**No secrets — clean.** All credential mentions are references to credentials not yet obtained. PII: entry ID 2928517 + team name; Pi hostname `fplpi` + user `saf` (Pi confirmed real via ~/.ssh/known_hosts). Private repo or scrub before public push.

## 6. Actual build stage

Mac: ~step 2.5/10 (stale fetch script, projections with red selftest, spec, uninitialized state). Per docs, Pi: step 4/10 as of 08-05. Zero Telegram code. Zero daemon code (by design). Cron unverified from here. Projections genuinely ran against real data at least once (per-player numbers internally consistent).

## Bottom line

1. The thinking (spec, probe matrix, season rules) is real, good, decision-dense — the most valuable assets in the folder. Don't rebuild.
2. The code is partially real but stranded: two of three scripts, one rev behind, mutually incompatible, failing test. The optimizer is unaccounted for.
3. The previous session's inventory was not accurate: described the intended tree as actual, invented draft_board.py and MASTER-PLAN.md, claimed data that was never downloaded.

**Recovery priority**: (a) SSH `saf@fplpi`, inventory `~/fpl/`, recover optimizer + csv-mode fpl_api, `crontab -l`; (b) treat Mac folder as stale mirror; (c) fix CSV handoff + selftest before the GW1 pre-deadline run (deadline Fri Aug 21).
