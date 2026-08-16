# Player Availability & Minutes — Data Sources (2026/27)

Scope: availability / minutes-certainty only (odds, friendlies, H2H covered by a separate agent). Target host: headless Raspberry Pi 4B (~2GB RAM). Strong preference for API/JSON/CSV over heavy JS scraping. "Minutes certainty" is repeatedly cited as THE deadline factor; the top deadline pull is chance-of-playing + predicted lineups.

**Bottom line:** the official FPL `bootstrap-static` API is the machine-readable spine (free, JSON, no key, authoritative for injuries/suspensions/`chance_of_playing`). Everything else (predicted XIs, pressers) is enrichment to resolve rotation, which the FPL API deliberately does NOT encode.

---

## Injury & suspension

**Primary — Official FPL `bootstrap-static` API.**
`https://fantasy.premierleague.com/api/bootstrap-static/` → `elements[]` carries the availability spine per player:
- `status` — single-letter flag: **`a`** available, **`d`** doubtful, **`i`** injured, **`s`** suspended, **`u`** unavailable.
- `chance_of_playing_this_round` / `chance_of_playing_next_round` — integer % (0, 25, 50, 75, 100) or `null` when fully fit.
- `news` — free-text reason, e.g. "Ankle injury - 50% chance of playing"; suspensions likewise ("Suspended - available GW3").
- `news_added` — ISO timestamp of the last update (use to detect freshness / new news since last poll).

Why primary: it is the ground truth the game itself scores against, it is pure JSON, no auth/key, tiny (single GET, cacheable), trivially parseable on a Pi, and it already fuses injury + suspension into one field. **Latency caveat:** FPL editorial updates lag reality — a player ruled out in a presser may not flip to `d`/`i` for hours. So the API is authoritative for *what FPL believes at scoring time* but must be front-run by pressers/predicted XIs near deadline. Rate limits: undocumented but generous for a single low-frequency poller; use a real User-Agent and poll on the order of every 10–30 min (more often in the final hour), not per-second. Unofficial — no formal ToS/SLA; do not hammer. ([FPL Player class docs](https://fpl.readthedocs.io/en/latest/classes/player.html), [FPL API endpoints cheatsheet](https://www.oliverlooney.com/blogs/FPL-APIs-Explained))

**Backup 1 — Premier Injuries** (`https://www.premierinjuries.com/injury-table.php`). Positioned as the most comprehensive EPL injury/suspension source (return dates, status, per-team views). **Pi-friendliness warning:** the site is bot-protected — a plain `WebFetch`/curl returns **HTTP 403 Forbidden**. Scraping needs browser-like headers or a headless browser (heavy on a 2GB Pi). Treat as a human-verification / cross-check source, not an automated feed. ([Premier Injuries](https://www.premierinjuries.com/), [injury table](https://www.premierinjuries.com/injury-table.php))

**Backup 2 — PhysioRoom Premier League injury table** (`https://www.physioroom.com/advice/premier-league-injury-table/`). Long-running, regularly-updated HTML table (injury type, status, expected return). Human-readable; lightly scrapable (server-rendered table, no login) but no official API — parse defensively. ([PhysioRoom](https://www.physioroom.com/advice/premier-league-injury-table/))

**Cross-checks (not for automation):** Fantasy Football Scout "Injuries and Bans" section within its Team News page (FPL-tuned, updated after pressers) ([FFS Team News](https://www.fantasyfootballscout.co.uk/team-news)); Transfermarkt injuries and FotMob player pages (good coverage, but JS-heavy / unofficial). Official PL injury roundup exists but is editorial prose, not structured ([PL injuries](https://www.premierleague.com/en/news/3777299)).

---

## Predicted / confirmed lineups

Two distinct products with different timing (see final section):

**Predicted XIs (available pre-deadline) — this is what you actually decide on.**

**Primary — Fantasy Football Scout Team News page** (`https://www.fantasyfootballscout.co.uk/team-news`): predicted line-ups for all 20 clubs plus a per-club injury summary, and — critically — the XIs are **re-tuned after each pre-match press conference and closer to the deadline**. FPL-specific, community-trusted (used by top managers). Access: HTML page; premium/RMT projections behind membership; core predicted XIs and team news are viewable. Lightly scrapable but JS-rendered in places — parse conservatively, and prefer polling in the final ~90 min before deadline when it is freshest. ([FFS Team News](https://www.fantasyfootballscout.co.uk/team-news))

**Backup 1 — RotoWire Premier League lineups** (`https://www.rotowire.com/soccer/lineups.php`): shows both **predicted and confirmed** XIs in one place, clearly labelled, and flips predicted→confirmed as clubs release. Cleaner/more table-like than most, good for a light scrape. No free official API. ([RotoWire lineups](https://www.rotowire.com/soccer/lineups.php))

**Backup 2 — Sportsgambler football lineups** (`https://www.sportsgambler.com/lineups/football/`): predicted XIs driven by latest team/injury news, all fixtures on one page. Historically decent but treat any single predicted-XI source as noisy (see reliability note). ([Sportsgambler](https://www.sportsgambler.com/lineups/football/))

Other options: FantasyFootballHub predicted lineups (good model, membership; mixed user reviews on accuracy) ([FFHub review](https://allaboutfpl.com/2026/08/complete-detailed-review-of-fantasy-football-hub/)); WhoScored predicted XIs (JS-heavy).

**Confirmed XIs (post-deadline) — for post-mortem / captaincy-was-right analysis, NOT for the deadline decision.**

**Primary — FotMob** `get_match_lineup` endpoint returns starting XI + bench per team as JSON (unofficial internal API; also powers heatmaps/xG). JSON is Pi-friendly, but it is an undocumented private endpoint (ToS grey area, may change/break). ([FotMob API overview](https://parse.bot/marketplace/d2378e4b-52ce-4f58-bd5d-d500dfc9da27/fotmob-com-api), [FotMob](https://fotmob.us/))
**Backup — Premier League app/website** (official, most authoritative confirmed XIs) and RotoWire (above).

**Reliability of predicted lineups:** genuinely useful but imperfect — models miss late tactical/rotation calls and last-minute knocks; accuracy improves sharply *after* pressers. No source publishes a rigorous head-to-head accuracy score. Practical implication: use **consensus across 2+ predictors** and down-weight any player not unanimously named; never treat a predicted XI as certainty. ([FFHub review notes mixed accuracy](https://allaboutfpl.com/2026/08/complete-detailed-review-of-fantasy-football-hub/))

---

## Press-conference / team-news

Manager pressers are the earliest structured signal (rotation hints, "he trained today", "we'll assess") and typically land **1–2 days before the match** — well before the FPL API flags update. Value: front-run the official flags.

**Primary — Fantasy Football Scout press-conference/team-news roundups** (`https://www.fantasyfootballscout.co.uk/category/team-news`): FPL-framed digests of every manager's presser, folded straight into the predicted XIs and injury table. One FPL-relevant place instead of 20 club feeds. HTML; light scrape. ([FFS Team News category](https://www.fantasyfootballscout.co.uk/category/team-news))

**Backup 1 — allaboutfpl** (`https://allaboutfpl.com/`): FPL-focused presser/team-news write-ups; lightweight, scrapable blog. ([allaboutfpl](https://allaboutfpl.com/))

**Backup 2 — r/FantasyPL daily/deadline threads** (`https://www.reddit.com/r/FantasyPL/`) via the free Reddit JSON API (append `.json` to a listing URL). Machine-readable, fast crowd-sourced relay of presser quotes and late knocks. Noisy/unverified — use for early signal and to detect "something is happening", then confirm against FFS/official. Respect Reddit API rate limits + UA rules.

**Cross-check:** official club sites (authoritative presser transcripts, but 20 heterogeneous JS sites — impractical to scrape on a Pi) and BBC/Sky team-news pages (reliable, prose). Reserve for spot-checks, not automation.

---

## Quantifying start probability

Goal: convert flags + text + XIs into **P(start)** and **E(minutes)** per player.

**Core mapping — FPL status + `chance_of_playing`:**
- `a` & `chance = null` → fully available.
- `d` with `chance` = 25/50/75 → treat the % as P(available at all); it is *availability*, not P(start) — a 100%-fit rotation risk still won't start.
- `i` / `s` / `u` → P(start) ≈ 0 for that GW (suspended = 0).

**Layer 2 — nailedness from rolling minutes:** compute a rolling start rate / minutes share over the last N matches (`element-summary/{id}/` history + live `minutes`). A player with 6/6 90-minute starts is "nailed"; sub-60-min averages flag rotation/sub risk. This is where E(minutes) really comes from.

**Layer 3 — rotation/predicted-XI consensus:** presence in ≥2 predicted XIs raises P(start); absence or "50/50" language in pressers penalises it. Encode "unresolved rotation" as an explicit variance/penalty term rather than a point estimate.

**Published method — OpenFPL** (open-source, rivals paid services): deliberately **dispenses with proprietary expected-minutes** and instead feeds the **categorical FPL availability tags** into per-position XGBoost+RandomForest ensembles, using only official FPL + Understat data. Explicitly flags the key limitation: *the FPL API encodes injury/suspension but NOT whether a player will start, sub, or be rested.* That gap is exactly what predicted XIs + pressers must fill. Good Pi-friendly template: public data, no scraping, reproducible. ([OpenFPL paper, arXiv 2508.09992](https://arxiv.org/pdf/2508.09992), [OpenFPL-Scout-AI repo](https://github.com/elcaiseri/OpenFPL-Scout-AI))

**Recommended pipeline:** `P(start) = f(status/chance) × nailedness(rolling minutes) × predicted-XI consensus`, then `E(minutes) = P(start)×~85 + P(sub)×~20`. Apply a variance penalty for any player whose start isn't unanimously predicted. Compute as late as possible before the deadline.

Data backbone for all three layers is free official JSON: `bootstrap-static/` (flags), `element-summary/{id}/` (per-player history), `fixtures/`, `event/{gw}/live/` (live minutes). ([FPL API cheatsheet](https://www.oliverlooney.com/blogs/FPL-APIs-Explained))

---

## Deadline-timing implication

**The hard constraint:**
- **FPL deadline = 90 minutes before the first kick-off of the gameweek.**
- **Confirmed starting XIs are released only 75 minutes before *each* kick-off** (relaxed from 60 min starting 2024/25; still in force 2026/27), via the PL app/website and club/rights-holder platforms. ([PL: be first for team news](https://www.premierleague.com/en/news/4081650), [GiveMeSport: 75-min rule](https://www.givemesport.com/why-premier-league-team-lineups-are-announced-75-minutes-before-kick-off/))

**Consequence:** at the moment you must lock the team, **zero confirmed XIs exist** — not even for the first match (its XI drops ~15 min *after* your deadline), and later kickoffs are hours away. You therefore decide on **predicted XIs + FPL injury/suspension flags + press-conference quotes**, never confirmed lineups.

**Implications for the autonomous manager:**
1. **Decide as late as possible.** Schedule the final compute/commit in the last window before the 90-min cutoff (e.g. a poll+solve at T-15 to T-5 min), after the last pressers and freshest predicted XIs, with a safety margin for the Pi's runtime. Late data strictly dominates early data here.
2. **Treat unresolved rotation as variance, not a coin-flip point estimate.** Any player not unanimously predicted to start carries an explicit E(minutes) haircut / risk penalty; prefer nailed starters for the captaincy and non-benched slots where the 0-minute downside is catastrophic.
3. **Exploit the auto-sub safety net.** Because confirmed news arrives post-deadline, bench-order matters: order the bench so a late non-starter is covered by a likely-starting sub. This converts some post-deadline information risk into recoverable points.
4. **Never block on confirmed XIs** — a design that "waits for lineups" would miss the deadline entirely. The system must be able to commit on predicted data alone and simply update its priors (for post-mortem/learning) once confirmed XIs and live minutes arrive.

---

## Sources

- FPL Player class / fields — https://fpl.readthedocs.io/en/latest/classes/player.html
- FPL API endpoints explained (status flags, endpoints) — https://www.oliverlooney.com/blogs/FPL-APIs-Explained
- Premier Injuries (home) — https://www.premierinjuries.com/
- Premier Injuries injury table — https://www.premierinjuries.com/injury-table.php
- PhysioRoom PL injury table — https://www.physioroom.com/advice/premier-league-injury-table/
- Premier League injuries roundup — https://www.premierleague.com/en/news/3777299
- Fantasy Football Scout — Team News / predicted line-ups — https://www.fantasyfootballscout.co.uk/team-news
- Fantasy Football Scout — Team News category (pressers) — https://www.fantasyfootballscout.co.uk/category/team-news
- RotoWire PL lineups (predicted + confirmed) — https://www.rotowire.com/soccer/lineups.php
- Sportsgambler football lineups — https://www.sportsgambler.com/lineups/football/
- FantasyFootballHub review (accuracy notes) — https://allaboutfpl.com/2026/08/complete-detailed-review-of-fantasy-football-hub/
- allaboutfpl — https://allaboutfpl.com/
- r/FantasyPL — https://www.reddit.com/r/FantasyPL/
- FotMob API overview (get_match_lineup) — https://parse.bot/marketplace/d2378e4b-52ce-4f58-bd5d-d500dfc9da27/fotmob-com-api
- FotMob — https://fotmob.us/
- OpenFPL paper (availability tags method) — https://arxiv.org/pdf/2508.09992
- OpenFPL-Scout-AI repo — https://github.com/elcaiseri/OpenFPL-Scout-AI
- PL: be first for team news (75-min lineups) — https://www.premierleague.com/en/news/4081650
- GiveMeSport: why lineups announced 75 min before KO — https://www.givemesport.com/why-premier-league-team-lineups-are-announced-75-minutes-before-kick-off/
- OneFPL: how to track FPL injury news 2026/27 — https://onefpl.com/blog/how-to-track-fpl-injury-news
