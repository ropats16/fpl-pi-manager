---
title: FPL Agentic System — Master Spec
summary: Architecture, decisions, and roadmap for the user's Fantasy Premier League management system (2026/27 season).
category: projects
tags: [fpl, architecture, roadmap, decisions]
source: user
confidence: high
created: 2026-08-01
updated: 2026-08-05
---

# FPL Agentic System — Master Spec

## Goal
Make good FPL decisions before ~38 weekly deadlines on the user's behalf, keeping the user informed and in control. Human-in-the-loop by design: system recommends, user confirms in the official app. No automated transfers (ToS risk; no FPL password stored — public read endpoints + entry ID suffice).

## Architecture (5 layers)
1. **Collect** — scheduled/cron fetches: FPL API (bootstrap-static, fixtures, element-summary, entry), betting odds, Understat xG, injury/presser news. Store normalized aggregates; raw bootstrap is multi-MB, re-fetch on demand.
2. **Model** — Python: expected points per player per GW over 1–6 GW horizon. Odds-implied fixture strength + xG/xA + minutes model + BPS sub-model.
3. **Decide** — ILP optimizer (PuLP+CBC) for transfers/XI/bench under budget/position/3-per-club; captaincy = EV adjusted for effective ownership + risk mode; chip timing via Monte Carlo over blank/double GW calendar.
4. **Deliver** — pre-deadline brief (moves, XI, captain, reasons, risks) pushed via Telegram; publishable page optional.
5. **Learn** — post-GW scoring of predictions vs actuals; assumptions log; preference log (which recs user accepts/overrides) in this wiki.

## Key decisions (with rationale)
- **Single agent, not multi-agent.** Data to Model to Decide is one sequential pipeline; splitting buys coordination overhead, zero accuracy. A second agent earns its place only with different goals/info/checks.
  - Phase 2: red-team mode (contrarian pass on each brief, same agent).
  - Phase 3: shadow-team tournament (3-4 philosophies managing ghost squads all season: odds-maximalist vs xG-purist vs template vs differential).
  - Revisit only if autonomous execution is ever wanted (then: separate checker agent with veto).
- **Cron + state on disk, NOT a 24/7 agent.** Presence is not the goal; cron+SQLite is more robust on a 1GB ARM board. Every job reads state, does one thing, writes back, exits.
- **Hybrid runtime:** build v1 in this chat runtime (fast iteration), port to user's Raspberry Pi (3B/4, 64-128GB SD) when stable. Pi owns Collect/Model/Decide on cron; LLM work (news extraction, brief narrative, debate) via API or this chat. Pi notes: 64-bit OS Lite, lean libs, logs on tmpfs, back up SQLite off-card (git).
- **Communication:** (1) pushed notes = templated Telegram bot messages from scripts (Bot API, ~15 lines); (2) interactive debate = this chat agent. Phase 2: two-way Telegram commands via short polling cron (approve, show squad, risk: aggressive).
- **Sentiment analysis: CUT.** Community sentiment tracks ownership/template, already captured precisely via effective ownership. News = structured extraction, not sentiment.

## User / season facts
- Entry ID **2928517**, team "Magnificos" (was auto-named "Rokshi" at registration). Registered 2026-08-05.
- Squad (built 2026-08-05, exactly £100.0m, £0.0 bank): Roefs, Verbruggen, Senesi, Guéhi, Diop(4.0), Mitchell, F.Kadıoğlu, B.Fernandes, Semenyo, Hughes(4.5), Tavernier, Szoboszlai, Haaland, Kusi Asare(4.5), João Pedro.
- GW1 deadline: **Fri 2026-08-21, 17:30 UTC** (23:00 IST). Season opens Arsenal–Coventry. Transfer window closes Aug 31 (post-GW1).
- Pi: hostname `fplpi`, user `saf`, OS Lite 64-bit, SSH from Mac working. `~/fpl/` holds scripts + `data/` + `logs/`. Nightly cron 03:30 fetch to data/snapshots (verify with `crontab -l`).
- Pi files use `~/fpl/data/` — NOTE: fpl_api.py fetch default out dir is ./fpl-data; pass `--out data`.

## Skills built
1. `fpl-api` — fetch/distill/csv/diff/selftest. On Pi + skills/. Users paste scripts via nano (download links unreliable for this user; TextEdit mangles quotes — use base64 or careful paste).
2. `fpl-projections` — v1: base_rate(pts/90 blend ep_next) × minutes_share × FDR multiplier × status haircut × 4% decay, 6-GW horizon. v1.1 fix: minutes<450 → not projected (kills youth-player bug: Byfield/Rowswell/Mheuka/Furo artifact). On Pi, selftest passing (selftest assert on newguy fails by design post-patch — harmless).
3. `fpl-optimizer` — PuLP ILP, modes scratch/from-squad(k-sweep)/xi/selftest; constraints: shape 2/5/5/3, budget, 3-per-club, --min-xmins 900 default; XI picker over legal formations; C/VC by gw1 xpts. Pi needs: `sudo apt install -y python3-pulp coinor-cbc`.

## Build log
- 2026-08-01: spec + probes done.
- 2026-08-02/03: Pi setup (flash, SSH), fpl_api deployed, first fetch+distill green (564 players, 20 teams, 38 events, 380 fixtures).
- 2026-08-05: draft squad built (user made own edits from my draft — kept Senesi+Guéhi, added Diop/Hughes/Kusi Asare punts). Projections run; youth bug found+fixed (v1.1). Model verdict on user squad: spine excellent (Bruno 31.7, Haaland 31.4, Semenyo 26.2, Guéhi 23.5, Senesi 23.2), bench projects ~0 (Diop/Hughes/Kusi Asare sub-450 mins). Optimizer built + selftest green.

## Skills to build (remaining, in order)
4. `fpl-team-news` — presser/injury extraction into fitness taxonomy: FIT / DOUBTFUL / OUT_SHORT_TERM / OUT_LONG_TERM / ROTATION_RISK + expected return + citation.
5. `fpl-price-watch` — nightly price-change threshold alerts (LiveFPL feed; fplstatistics shut down 2026; whatthef.pl tracks predictor accuracy).
6. `fpl-deadline-brief` — weekly one-pager + Telegram push.
7. `fpl-review` — post-GW self-grading into memory.

## Data audit verdicts
- Core: FPL API (free, read-only, tolerated), betting odds (best fixture signal; The Odds API free tier), Understat xG, vaastav/Fantasy-Premier-League GitHub (training data).
- Nice-to-have: LiveFPL price feed, premierinjuries.com, FPL Review (free projections benchmark; taken down ~1h pre-deadline — snapshot earlier).
- Cut: social sentiment, Twitter/X scraping, FBref (Cloudflare-blocked here; retry on Pi with browser headers/curl_cffi else drop — optional luxury behind Understat).

## Methods audit verdicts
- Build: odds-implied projections (backbone), ILP optimizer, minutes/rotation model (top error source), scoped gradient-boosted ML (no deep learning — dataset too small), Monte Carlo chip sims (phase 2), structured news extraction, BPS sub-model, dominated-option pruning + decision lenses (Conservative/Aggressive/Template/Differential).
- Cut: generic sentiment, end-to-end black-box ML, reinforcement learning, Poisson/Dixon-Coles (only if odds access fails).

## Weekly cadence (in-season)
Tue: post-GW review + data refresh. Wed-Thu: injury/presser scans + nightly price watch. Fri: brief v1. Matchday minus 2h: final brief.

## Runtime constraints
Sandbox: ~2min cap, ephemeral, 64KB file cap, network allowlist (FPL API blocked in sandbox, works via web_fetch + works direct from Pi). Persist only distilled data.

## Roadmap
1. DONE Spec + probes (08-01) → 2. DONE fpl-api + season-state (08-02) → 3. DONE projections v1.1 (08-05) → 4. DONE optimizer (08-05) → 5. **pre-deadline run ~Aug 18-20: refresh data, projections, optimizer from-squad + scratch, news scan, final squad + XI + captain brief** → 6. deadline brief + Telegram → 7. Pi port completion → 8. two-way commands → 9. red-team mode → 10. shadow teams.

## Open items
- The Odds API free key (user requested, awaiting email).
- Telegram bot token via @BotFather (step 6).
- Verify 2026/27 rules against official FPL page (see season rules topic).
- Known model gaps for v2: Understat blend, odds layer, news/minutes for new signings (currently 0), Saliba+Timber injury effect on ARS defence not in FDR.

Related: [2026/27 rules](../topics/fpl-2026-27-season-rules.md), [data reachability](../topics/fpl-data-source-reachability.md), [season state](../../fpl/season-state.json)
