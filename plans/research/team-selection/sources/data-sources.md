# Preferred data sources

Recommended, justified data sources per category, cross-referenced. Runtime is a
headless **Raspberry Pi 4B (~2GB RAM)**, so **API/JSON/CSV strongly preferred over
heavy JS scraping**. Prefer official → tier-1 → highly-rated FPL communities. Full
evidence: [../raw/cluster-D-sources.md](../raw/cluster-D-sources.md) (odds/friendlies/
H2H/general), [../raw/followup-availability-sources.md](../raw/followup-availability-sources.md)
(availability).

Access legend: **API** (documented JSON) · **JSON** (unofficial endpoint, no key) ·
**CSV** · **scrape-light** (static HTML) · **scrape-heavy** (JS-rendered, needs headless
browser — avoid on Pi) · **paid** · **community**.

---

## Odds

The [#24](https://github.com/ropats16/fpl-pi-manager/issues/24) acceptance criterion for
odds. Reality check: **1X2 is available everywhere; clean-sheet (CS) and anytime-
goalscorer (AGS) are "additional"/player-prop markets, gated or absent on most free
feeds** — plan around that split.

| Source | Markets | Access | Why |
|---|---|---|---|
| **The Odds API** *(primary)* | 1X2, totals, BTTS; AGS/CS via paid "additional markets" | API, free 500 req/mo | One normalized JSON endpoint aggregating ~50 books incl. **Pinnacle** (sharp anchor); ideal for a Pi. Budget requests — AGS/CS cost extra credits. [the-odds-api.com](https://the-odds-api.com/) |
| **Betfair Exchange** *(backup — sharp truth)* | 1X2, O/U, `TO_SCORE`≈AGS, Correct Score, `FIRST_GOAL_SCORER` | API, free w/ funded acct | Exchange midpoint ≈ **near-zero-vig** true probability — the best de-vigged benchmark. No native CS market → derive from Correct Score / team O-U 0.5. Heavier auth setup. [developer.betfair.com](https://developer.betfair.com/exchange-api/) |
| **football-data.co.uk** *(backup — historical/backtest)* | 1X2, O/U 2.5, AH, **closing** odds incl. Pinnacle | CSV, free | Best free **historical** EPL odds (back to 1990s); Pinnacle closing lines are a gold-standard fair-prob proxy for calibration/backtesting. Not live, no AGS/CS. [football-data.co.uk](https://www.football-data.co.uk/englandm.php) |

**Why these:** official books have no open API for non-partners (Pinnacle included), so
reach sharp lines *through* The Odds API; Betfair gives the sharpest de-vigged signal;
football-data covers the free historical layer for calibration. **Avoid on Pi:**
OddsPortal / Oddschecker (scrape-heavy + ToS). **Clean-sheet gotcha:** no free feed gives
CS cleanly — buy via The Odds API additional markets, take Betfair Correct Score / team
O-U 0.5, or **derive** CS from 1X2 + totals.

### Odds → probability (removing the vig)

1. Decimal → raw implied: `p_raw = 1/decimal_odds`.
2. Overround `S = Σ p_raw` (>1); `S−1` = the margin.
3. De-vig — **[standard → use]**:
   - **Multiplicative** (`p = p_raw/S`) — default for balanced 1X2 / tight lines.
   - **Power** (`Σ p_raw^k = 1`) — better on lopsided lines.
   - **Shin** — models insider-information adverse selection; corrects favourite-longshot
     bias; best for skewed **AGS / CS** markets.
4. Multi-outcome AGS: normalize across the full player set (Shin), not each Yes/No in
   isolation.
5. Shortcut: **Betfair back/lay midpoint** is already ~1–2% margin — use as the fair-prob
   benchmark. Tight two-way lines agree across methods; divergence only matters on the
   lopsided AGS/CS prices — so prefer Shin/power there, multiplicative for 1X2.

---

## Friendlies

Acceptance criterion for pre-season friendlies. **Minutes/lineups per friendly are the
scarce resource** (scores are easy); they feed *role/minutes only*, never goal tallies
(see [../factors/predictive-signals.md#pre-season-friendlies](../factors/predictive-signals.md#pre-season-friendlies)).

| Source | Gives | Access | Why |
|---|---|---|---|
| **FFS pre-season minutes/goals/assists tracker** *(primary)* | **Minutes** per player per friendly | community, free page | Purpose-built for the "who starts GW1" question — the single best FPL-minutes source. [FFS tracker](https://www.fantasyfootballscout.co.uk/fpl-2026-27-pre-season-minutes-goals-assists-tracker) |
| **Transfermarkt** *(backup — structured)* | Friendly fixtures, **lineups + minutes** | scrape-light / worldfootballR | Most reliable *structured* source incl. lower-profile tour games; static-ish HTML. Keep request rate low (ToS). |
| **Sky Sports / ESPN** *(backup — spine)* | Fixtures, kickoff times, **scores** | scrape-light | Clean canonical fixture/result lists; weak on minutes — use for the schedule spine + cross-check. |

The **FPL API carries no friendlies** → must come from the above. FotMob/Soccerway carry
lineups but are scrape-heavy — deprioritise on Pi.

---

## Head-to-head

Acceptance criterion for H2H. Note the factor research says **don't build an explicit H2H
term** (it overfits noise — [../factors/fixtures-and-context.md#head-to-head--matchup-context](../factors/fixtures-and-context.md#head-to-head--matchup-context));
these sources are for the underlying-strength / style layer and backtesting.

| Source | Gives | Access | Why |
|---|---|---|---|
| **football-data.co.uk** *(primary)* | Full historical EPL match CSVs (scores, results, odds) | CSV, free | Pi-perfect: download once, filter any club pair locally → instant H2H, zero live scraping. [football-data.co.uk](https://www.football-data.co.uk/englandm.php) |
| **FBref (StatsBomb)** *(underlying stats)* | H2H match logs **with xG/shots**, team/player stats | scrape-light, rate-limited ~1 req/3s | Best free advanced stats; cache aggressively. Use for the "team style / opponent strength" layer. |
| **Understat** *(backup — xG)* | Match & shot-level **xG** (EPL since 2014) | JSON-in-page | Lightweight embedded JSON (no headless browser). |
| **football-data.org / API-Football** *(backup — clean API)* | `head2head` endpoint, fixtures, results | API, free tier (rate-limited) | A proper JSON H2H endpoint if you'd rather not scrape. |

---

## Player availability (the highest-leverage deadline pull)

Multiple analyses name **minutes-certainty** as THE factor; the top deadline pull is
chance-of-playing + predicted lineups.

| Need | Primary | Backups | Why |
|---|---|---|---|
| **Injury & suspension** | Official **FPL `bootstrap-static`** (`status` a/d/i/s/u + `chance_of_playing_next_round` % + `news` + `news_added`) — JSON, no key, authoritative for scoring | Premier Injuries (scrape-heavy, 403s bots — human cross-check), PhysioRoom (scrape-light) | The ground truth the game scores against; tiny, cacheable, Pi-trivial. **Latency caveat:** FPL editorial flags lag pressers by hours → front-run near deadline. [FPL API](https://fantasy.premierleague.com/api/bootstrap-static/) |
| **Predicted XIs** *(what you decide on)* | **FFS Team News** (re-cut after every presser) | RotoWire (predicted+confirmed one table), Sportsgambler | Use **consensus across ≥2 predictors**; single sources are noisy. [FFS](https://www.fantasyfootballscout.co.uk/team-news) |
| **Confirmed XIs** *(post-mortem only)* | FotMob `get_match_lineup` JSON / PL app | RotoWire | Arrive **after** your deadline — never for the decision. |
| **Pressers / team-news text** | **FFS presser roundups** | allaboutfpl, r/FantasyPL `.json` | Front-run FPL flags by 1–2 days; FPL-framed digest instead of 20 club feeds. |

**Quantifying start probability** (the method):
`P(start) = f(status/chance) × nailedness(rolling minutes from element-summary) ×
predicted-XI consensus`, then `E(min) = P(start)×~85 + P(sub)×~20`; apply a variance
penalty for any player not unanimously predicted to start. OpenFPL validates using the
categorical FPL availability tags in place of proprietary xMins
([arXiv 2508.09992](https://arxiv.org/abs/2508.09992)).

### Deadline-timing constraint

FPL deadline = **T-90 min** before first kickoff; confirmed XIs drop only **~75 min**
before *each* kickoff (relaxed from 60 in 2024/25) — so at lock time **zero confirmed
lineups exist**. Consequences for the autonomous manager: **decide as late as possible**
(final poll+solve ~T-15 to T-5 with runtime margin); treat unresolved rotation as an
explicit E(min)/variance penalty; exploit bench-order as the post-deadline safety net;
**never block waiting on confirmed XIs**. See
[../factors/meta-and-timing.md#decision-timing-option-value](../factors/meta-and-timing.md#decision-timing-option-value).
([PL 75-min rule](https://www.premierleague.com/en/news/4081650))

---

## General FPL / analytics feeds

| Source | Gives | Access |
|---|---|---|
| **Official FPL API** (`bootstrap-static`, `fixtures`, `element-summary/{id}`, `event/{gw}/live`) | prices, ownership, form, availability, schedule, live minutes | JSON, no key (poll politely; 429 if hammered; no CORS) |
| **Understat** | team/player xG, xA, shots | JSON-in-page |
| **FBref (StatsBomb)** | advanced stats (xG, progressive, defensive actions) | scrape-light, rate-limited |
| **vaastav/Fantasy-Premier-League** | canonical historical dataset (training/backtest) | CSV/git — mind the `ep_this` leakage ([reference-pipelines](../methods/reference-pipelines.md#data--vaastav-historical-repo)) |
| **r/FantasyPL**, **Fantasy Football Scout**, **FPL Review**, **Ben Crellin** | community sentiment, predicted lineups, projections, DGW/BGW & rotation | community / freemium |

**Avoid on 2GB Pi (scrape-heavy):** FotMob, Soccerway, OddsPortal, Oddschecker.
