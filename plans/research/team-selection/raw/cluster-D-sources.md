# Cluster D — Data Source Recommendations (FPL autonomous manager)

Scope: pick preferred data sources for (1) betting odds, (2) pre-season friendlies results/lineups, (3) head-to-head history, plus general FPL/analytics feeds. Runtime is a headless Raspberry Pi 4B (~2GB RAM), so **API/CSV/JSON sources are strongly preferred over heavy JS scraping** (Selenium/Playwright + Chromium is painful at 2GB). Prefer official; else tier-1.

Legend for access method: **API** = documented JSON/REST • **JSON (unofficial)** = reverse-engineered endpoint, no key • **CSV** = static file download • **Scrape (light)** = static HTML, plain HTTP + parser • **Scrape (heavy)** = JS-rendered, needs headless browser • **Paid** • **Community** = human-curated site/thread.

---

## Odds

Need machine-readable clean-sheet, anytime-goalscorer (AGS), and match-result (1X2) odds, ideally free/cheap, converted to implied probability with the vig removed.

Key reality check: **1X2 (match result) is trivially available everywhere; clean sheet (CS) and anytime-goalscorer (AGS) are "additional"/player-prop markets that are gated or absent on most free feeds.** Plan around that split.

| Source | Markets | Access | Cost | Notes |
|---|---|---|---|---|
| **The Odds API** (primary) | 1X2 (h2h), totals, BTTS; AGS/CS via "additional markets" | [API](https://the-odds-api.com/) | Free 500 req/mo; paid from ~$29/mo | Aggregates ~50 books incl. **Pinnacle** (sharp anchor). One normalized REST/JSON endpoint — ideal for a Pi. Free tier great for 1X2; **AGS/clean-sheet player-prop markets cost extra credits / higher plan** and are per-event calls, so budget requests. [Docs](https://the-odds-api.com/liveapi/guides/v4/) |
| **Betfair Exchange API** (backup, sharp truth) | 1X2, Over/Under, **TO_SCORE** (≈AGS), Correct Score, FIRST_GOAL_SCORER | [API](https://developer.betfair.com/exchange-api/) | Free data w/ funded acct; one-off ~£/€ app-key activation | Exchange prices = near-zero vig (lay/back midpoint ≈ true prob), the best de-vigged signal you can get. Use `marketType=TO_SCORE`/`FIRST_GOAL_SCORER` per match ([forum](https://forum.developer.betfair.com/forum/sports-exchange-api/exchange-api/28121-get-to-score-and-first-scorer-odds)). **No explicit "clean sheet" market** — derive CS from Correct Score / O-U 0.5 by team, or O/U team goals. **No match scores/incidents via API** ([FAQ](https://support.developer.betfair.com/hc/en-us/articles/115003875332)). Requires account + auth handshake (heavier setup). |
| **football-data.co.uk** (backup, historical/backtest) | 1X2, O/U 2.5, AH, closing odds from ~15 books incl. Bet365 & **Pinnacle** | [CSV](https://www.football-data.co.uk/englandm.php) | Free | Best free **historical** odds CSVs for EPL (back to 1990s; Pinnacle closing lines are a gold-standard fair-prob proxy). **No AGS, no clean-sheet, not live** — use for model training/backtesting priors, not gameweek decisions. |

Avoid on a Pi: **OddsPortal / Oddschecker** are JS-rendered aggregators requiring headless-browser scraping ([OddsPortal is JS-only](https://www.scrapehero.com/scraping-odds-portal/)) and their ToS restrict scraping — high RAM cost + legal grey area. Only worth it if you accept a heavy scraper; otherwise skip. **Pinnacle** has no public odds API for non-partners (the CRAN `pinnacle.data` package is historical sample data only) — reach Pinnacle lines *through* The Odds API instead.

Recommendation: **The Odds API primary** (JSON, Pi-friendly, free 1X2 + cheap paid tier for AGS/CS), **Betfair Exchange backup** for the sharpest de-vigged CS/AGS signal, **football-data.co.uk** for free historical calibration. For clean sheet specifically, either buy CS via The Odds API additional markets or **derive CS probability** from team Over/Under 0.5 goals or 1X2+totals.

---

## Odds → probability (removing vig)

1. **Decimal → raw implied prob:** `p_raw = 1 / decimal_odds`. (American: +odds → `100/(odds+100)`; −odds → `−odds/(−odds+100)`.)
2. **Overround (booksum):** sum raw probs across all outcomes of a market → `S = Σ p_raw`. `S > 1`; `S − 1` = the vig/margin.
3. **De-vig — pick a method** ([methods overview](https://betherosports.com/blog/devigging-methods-explained)):
   - **Multiplicative / proportional** (default, simplest): `p_fair_i = p_raw_i / S`. Guarantees Σ = 1. Fine for balanced markets (1X2, tight lines). ([no-vig calc](https://chancemetrics.com/no-vig-calculator))
   - **Power method:** solve `Σ p_raw_i^k = 1` for exponent `k`, then `p_fair_i = p_raw_i^k`. Better on lopsided lines.
   - **Shin (1993):** models margin as insider-information adverse selection; corrects favorite-longshot bias, giving favorites more prob than multiplicative. Best for skewed markets like **AGS** (one heavy favorite striker + many longshots). Worth it for goalscorer/CS markets.
4. **Multi-outcome markets (AGS):** the "yes to score" prices for all players in a match sum to well above 1 — normalize across the full player set (Shin recommended) rather than treating each striker's Yes/No pair in isolation.
5. **Best free de-vig shortcut:** use **Betfair Exchange** back/lay midpoint — margin is already ~1–2%, so minimal correction needed; treat it as the fair-prob benchmark to sanity-check bookmaker-derived numbers.

On tight two-way lines all methods agree; divergence only matters on lopsided prices (exactly where AGS/CS live), so prefer **Shin or power** for those two markets and **multiplicative** for 1X2.

---

## Friendlies

Need pre-season fixtures, scores, and — critically — **lineups + minutes** for PL clubs (who's fit, who's starting, rotation clues for GW1). Scores are easy; **minutes/lineups per friendly are the scarce resource.**

| Source | Gives | Access | Cost | Notes |
|---|---|---|---|---|
| **Fantasy Football Scout — Pre-Season Minutes/Goals/Assists Tracker** (primary) | **Minutes, goals, assists per player per friendly** in spreadsheet form | [Community](https://www.fantasyfootballscout.co.uk/fpl-2026-27-pre-season-minutes-goals-assists-tracker) | Free page (some FFS content is Members/paid) | The single best FPL-purpose pre-season minutes source — human-curated exactly for the "who's starting GW1" question. Scrape (light) the tracker table, or read manually. No API. Pair with their [friendlies-by-date fixture list](https://www.fantasyfootballscout.co.uk/2026/07/15/fpl-2026-27-premier-league-clubs-pre-season-friendlies-by-date). |
| **Transfermarkt** (backup, structured) | Friendly fixtures, scores, **lineups + minutes** (friendlies are covered as matches) | Scrape (light) or [worldfootballR](https://github.com/JaseZiv/worldfootballR)/ScraperFC wrappers | Free | Most reliable *structured* source for friendly lineups/minutes across clubs incl. lower-profile tour games. Static-ish HTML → parseable without a headless browser. ToS discourages scraping; keep request rate low. |
| **Sky Sports / ESPN pre-season hubs** (backup, fixtures+scores) | Fixtures, kickoff times, **scores** (lineups sparse) | Scrape (light) | Free | [Sky](https://www.skysports.com/football/news/11095/13546612/premier-league-pre-season-friendlies-2026-27-fixtures-results-uk-kick-off-times-summer-tour-schedule-and-training-camps) and [ESPN](https://www.espn.com/soccer/story/_/id/49154575/) maintain clean canonical fixture/result lists — good for the schedule skeleton, weak on minutes. Use to cross-check FFS/Transfermarkt. |

Notes: Soccerway and FotMob also carry friendly lineups but are JS-heavy (headless browser) — deprioritize on the Pi. The **FPL bootstrap-static API does NOT include friendlies** (only competitive fixtures), so friendlies must come from these external sources. Recommendation: **FFS tracker primary** (purpose-built minutes), **Transfermarkt backup** (structured, programmatic), **Sky/ESPN** for the authoritative fixture/score spine and cross-validation.

---

## Head-to-head

Need past meeting results between two clubs, ideally with underlying stats (xG, shots) to weight recent form over raw H2H.

| Source | Gives | Access | Cost | Notes |
|---|---|---|---|---|
| **football-data.co.uk** (primary) | Full historical EPL match CSVs (scores, results, + odds) back decades | [CSV](https://www.football-data.co.uk/englandm.php) | Free | Ideal for a Pi: download once, filter any club pair locally → instant H2H with zero live scraping. Also on [Kaggle](https://www.kaggle.com/datasets/louischen7/football-results-and-betting-odds-data-of-epl). No xG, but has results + closing odds (a strong strength proxy). |
| **FBref (StatsBomb)** (primary for underlying stats) | H2H match logs **with xG, shots, advanced metrics**; team/player season stats | Scrape (light, static HTML) via [worldfootballR](https://jaseziv.github.io/worldfootballR/articles/extract-fbref-data.html) / [ScraperFC](https://pypi.org/project/ScraperFC/) | Free | Best free advanced stats. Plain HTTP scraping works (no key). **Enforces a strict rate limit (~1 req / 3s; bans on abuse)** — cache aggressively; updates 24–48h post-match. Use for the "underlying quality" layer on top of raw H2H results. |
| **Understat** (backup, xG) | Match & shot-level **xG** for EPL | JSON-in-page, [worldfootballR](https://worldfootballr.sportsdataverse.org/articles/extract-understat-data.html)/ScraperFC | Free | EPL xG since 2014; lightweight JSON embedded in page (no headless browser needed). Great cheap xG feed to complement FBref. |
| **API-Football / football-data.org** (backup, clean API) | H2H endpoint, fixtures, results via REST | [API](https://www.football-data.org/) | Free tier (rate-limited) / paid | If you want a *proper JSON H2H API* instead of scraping: football-data.org free tier covers EPL results (10 req/min); API-Football has an explicit `head2head` endpoint. Cleanest for a Pi but free tiers are volume-limited. |

Also: **11v11** and **Soccerway** hold deep H2H archives but are scrape-only/JS-heavy — use football-data.co.uk CSV or football-data.org API instead. Recommendation: **football-data.co.uk CSV primary** (offline, Pi-perfect, results+odds), layer **FBref/Understat xG** for underlying quality, and use **football-data.org API** if you prefer a maintained JSON H2H endpoint over local CSV filtering.

---

## General FPL / analytics sources

| Source | Gives | Access | Cost |
|---|---|---|---|
| **Official FPL API — bootstrap-static & fixtures** | All players (prices, ownership, form, points), 20 clubs, 38-GW schedule, chips; `/fixtures/` for FDR & kickoff | [JSON (unofficial, no key)](https://fantasy.premierleague.com/api/bootstrap-static/) | Free |
| **Understat** | Team/player xG, xA, shot data | JSON-in-page / [worldfootballR](https://worldfootballr.sportsdataverse.org/) | Free |
| **FBref (StatsBomb)** | Advanced stats (xG, progressive passes, defensive actions) | Scrape (light), rate-limited | Free |
| **FotMob** | Predicted lineups, injuries, live ratings | Scrape (heavy / unofficial JSON) | Free (deprioritize on Pi) |
| **Fantasy Football Scout** | Pre-season minutes, predicted lineups, community analysis | Community (part paid) | Freemium |
| **FPL Review (Massive Data / Rate My Team)** | Points projections, optimizer (EV per player) | Web tool / partial data export | Freemium/paid |
| **r/FantasyPL** | Community sentiment, price-change & injury chatter, Ben Crellin-style deadline threads | [Reddit JSON API](https://www.reddit.com/r/FantasyPL/.json) | Free (rate-limited) |
| **Ben Crellin** | Rotation/fixture-difficulty & DGW/BGW projections | Community (X/Twitter, sheets) | Free |

Access-tier summary: **Free & Pi-friendly (API/JSON/CSV):** Official FPL API, football-data.co.uk, Understat, football-data.org, Reddit JSON. **Free but scrape (light, rate-limited):** FBref, Transfermarkt, Sky/ESPN. **Freemium/paid:** Fantasy Football Scout (some content), FPL Review. **Scrape-heavy (avoid on 2GB Pi):** FotMob, Soccerway, OddsPortal, Oddschecker.

FPL API caveats: unofficial (no SLA, endpoints can change), **no documented rate limit but returns 429 if hammered** — cache locally, poll politely (once per few min max around deadlines), and it can't be called from a browser front-end (CORS). It carries **no friendlies and no odds** — those must come from the sources above.

---

## Sources

- The Odds API — https://the-odds-api.com/ • docs https://the-odds-api.com/liveapi/guides/v4/
- Betfair Exchange API — https://developer.betfair.com/exchange-api/ • TO_SCORE/FIRST_GOAL_SCORER https://forum.developer.betfair.com/forum/sports-exchange-api/exchange-api/28121-get-to-score-and-first-scorer-odds • scores-not-available FAQ https://support.developer.betfair.com/hc/en-us/articles/115003875332
- football-data.co.uk — https://www.football-data.co.uk/englandm.php • all data https://www.football-data.co.uk/all_new_data.php • Kaggle mirror https://www.kaggle.com/datasets/louischen7/football-results-and-betting-odds-data-of-epl
- OddsPortal (JS-heavy, scrape caveat) — https://www.scrapehero.com/scraping-odds-portal/
- De-vig methods — https://betherosports.com/blog/devigging-methods-explained • https://chancemetrics.com/no-vig-calculator
- Fantasy Football Scout — pre-season minutes tracker https://www.fantasyfootballscout.co.uk/fpl-2026-27-pre-season-minutes-goals-assists-tracker • friendlies by date https://www.fantasyfootballscout.co.uk/2026/07/15/fpl-2026-27-premier-league-clubs-pre-season-friendlies-by-date
- Sky Sports pre-season — https://www.skysports.com/football/news/11095/13546612/premier-league-pre-season-friendlies-2026-27-fixtures-results-uk-kick-off-times-summer-tour-schedule-and-training-camps
- ESPN pre-season — https://www.espn.com/soccer/story/_/id/49154575/
- FBref extraction (worldfootballR) — https://jaseziv.github.io/worldfootballR/articles/extract-fbref-data.html
- Understat extraction — https://worldfootballr.sportsdataverse.org/articles/extract-understat-data.html
- worldfootballR (FBref/Transfermarkt/Understat wrapper) — https://github.com/JaseZiv/worldfootballR
- ScraperFC (Python: FBref/Understat/Transfermarkt/Sofascore) — https://pypi.org/project/ScraperFC/
- football-data.org API — https://www.football-data.org/
- Official FPL API (bootstrap-static) — https://fantasy.premierleague.com/api/bootstrap-static/ • endpoint guide https://medium.com/@frenzelts/fantasy-premier-league-api-endpoints-a-detailed-guide-acbd5598eb19
- r/FantasyPL — https://www.reddit.com/r/FantasyPL/
