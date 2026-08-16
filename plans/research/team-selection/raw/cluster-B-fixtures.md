# Cluster B — Fixtures, Context & Set-Pieces

Evidence base for four decision axes. Weights are SUGGESTED / non-binding. Citations inline; full list at end.
Compiled 2026-08-16. Bias caveat: FPL community/tool pages vary in rigor — academic + Opta sources are treated as tier-1; FPL blogs as tier-2 (directional).

---

### Axis 1: Fixture difficulty done PROPERLY — **Suggested weight: HIGH — "single biggest lever after player quality; but replace naive FDR"**

- **Official FPL FDR (color 1–5) is weak.** It is a smoothed, backward-looking team-strength rating that does **not** separate attack from defence — a team can score a lot AND concede a lot, which a single 1–5 number cannot express ([FPL360](https://fpl360.com/2026/05/06/fpl-fixture-difficulty-rating-explained-use-fdr-for-better-transfers/)). It also treats Arsenal (H) and Arsenal (A) as identical difficulty, despite home teams scoring ~30% more goals ([FPL Copilot](https://fplcopilot.com/blog/fpl-fixture-difficulty-rating)).
- **Better approach 1 — position-specific + xG-based.** The strongest FDR variants split ratings by position: defenders/GK keyed to expected goals *conceded* / clean-sheet probability; mids/fwds keyed to expected goals *created*, using Opta underlying data rather than result-based strength. Fantasy Football Scout's ticker uses FFS Elo plus model-projected Clean-Sheet% and Projected Goals (per-team xG baselines) ([FFS ticker](https://www.fantasyfootballscout.co.uk/fpl/ticker); [FPL360](https://fpl360.com/2026/05/06/fpl-fixture-difficulty-rating-explained-use-fdr-for-better-transfers/)).
- **Better approach 2 — market-odds-derived difficulty.** OddAlerts prices FDR directly from betting odds: strip the bookmaker margin from match odds + the over/under-2.5 line, then solve for each side's implied expected goals. This is dynamic (updates with team news/form) unlike static 1–5 ([OddAlerts](https://www.oddalerts.com/fpl/fixture-ticker)).
- **Better approach 3 — expected points (xPts), the endpoint.** FPL Review shows a model built on FPL position + expected fixture difficulty is "far superior" to recent-goal data, and their goalscoring model is more predictive than inferences from bookmaker odds ([FPL Review](https://fplreview.com/a-goalscoring-model-more-predictive-than-inferrences-from-bookmakers/)). xPts absorbs FDR plus home/away, form, and role — FDR is a component, not the output ([FPL Copilot](https://fplcopilot.com/blog/fpl-fixture-difficulty-rating)).
- **Academic backbone.** Team attack/defence strength + home advantage as Poisson/Dixon-Coles parameters is the standard, well-validated method for match-goal expectation ([dashee87 / Dixon-Coles](https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/)).
- **Strong vs folklore:** Strong — separating attack/defence, using xG-based or odds-based inputs, and home/away splitting all measurably improve on 1–5 FDR. Folklore — treating the official color grid as ground truth.

**How to apply:** Do NOT feed raw 1–5 FDR into the optimizer. Build a per-team, per-position difficulty from (a) Understat/FBref rolling xGF & xGA with recency weight, or (b) bookmaker-odds-implied team xG, split by home/away. Feed that as the fixture term inside an xPts projection rather than as a standalone score.

---

### Axis 2: Home / away advantage — **Suggested weight: MED — "real and worth ~+0.25–0.3 goals & ~55–58% of points, but shrinking; never zero"**

- **Baseline magnitude (with fans).** Home teams historically won ~0.39 more points per game at home than away and scored ~0.29 more goals per game ([Northumbria/Leeds study, via Leeds](https://www.leeds.ac.uk/news-science/news/article/4894/how-empty-stadiums-affected-football-during-pandemic)). Long-run home/away *win ratio* averaged 1.68 across 1992/93–2019/20 ([Significance](https://significancemagazine.com/home-advantage-whats-changed-since-covid/)).
- **COVID empty-stadium collapse (well-evidenced).** With no fans, the points edge nearly halved to ~0.22 and the goal edge fell to ~0.15 ([Leeds](https://www.leeds.ac.uk/news-science/news/article/4894/how-empty-stadiums-affected-football-during-pandemic)). The PL home/away win ratio fell from 1.68 to 0.94 in 2020/21 — a ~44% drop ([Significance](https://significancemagazine.com/home-advantage-whats-changed-since-covid/)). For the first time in PL history the away win rate exceeded home (40% vs 38%) in 2020/21 ([Sky Sports](https://www.skysports.com/football/news/11095/13511444/home-advantage-is-on-the-wane-in-the-premier-league-between-the-lines)). Referee foul/decision bias toward home sides also shrank without crowds ([Leeds](https://www.leeds.ac.uk/news-science/news/article/4894/how-empty-stadiums-affected-football-during-pandemic)).
- **Post-COVID: partial rebound but structural decline continues.** Ratio recovered to 1.26 (2021/22) and back toward ~1.68 from 2022/23 ([Significance](https://significancemagazine.com/home-advantage-whats-changed-since-covid/)). BUT the long-run trend is downward: home win rate peaked ~65% (1895), was 56% of points in 2011 (then a 20-year low), and current home win rate is ~42% — fifth-lowest in PL history — with away wins up to ~31% ([Sky Sports](https://www.skysports.com/football/news/11095/13511444/home-advantage-is-on-the-wane-in-the-premier-league-between-the-lines); [WhoScored/Sky via search](https://www.skysports.com/football/news/11095/13511444/home-advantage-is-on-the-wane-in-the-premier-league-between-the-lines)). Current per-game home edge is ~0.25 goals ([Football Perspectives](https://footballperspectives.org/home-advantage-football-what-can-data-tell-us/)).
- **Strong vs folklore:** Strong — the crowd-effect causal evidence (COVID natural experiment) and the multi-decade decline are both robust. Contested — the exact current magnitude drifts season to season; some PL sides now average fewer points at home than away ([Sky Sports](https://www.skysports.com/football/news/11095/13511444/home-advantage-is-on-the-wane-in-the-premier-league-between-the-lines)).

**How to apply:** Apply a home/away multiplier to the fixture term (roughly +0.12–0.15 goals to home xG, symmetric to away), NOT a flat legacy value — the effect is smaller than pre-2020 folklore and team-specific. Better: let odds/xG-based fixture difficulty (Axis 1) carry the venue split natively, since it's already priced in.

---

### Axis 3: Head-to-head & matchup / tactical context — **Suggested weight: LOW — "mostly narrative; small real signal in style-mismatch & derbies, drowned in noise"**

- **Raw H2H history has weak/negligible predictive power.** Records >~5 seasons old (different squads/managers) are effectively noise; H2H is at best a *confirming* indicator secondary to current form, xG differentials, and team news ([Better World Master](https://www.betterworldmaster.com/blog/head-to-head-records.php)). Sample size is the killer: two league meetings/season means even a decade gives ~20 matches — apparent patterns are often random variation ([Better World Master](https://www.betterworldmaster.com/blog/head-to-head-records.php)).
- **Team strength dominates.** Standard match-prediction models rank team attack/defence strength, form, and home advantage above H2H; H2H enters modern models only as one of dozens of features (e.g. alongside Pi-ratings, form) and is not a primary driver ([MDPI Poisson study](https://www.mdpi.com/2076-3417/14/16/7230); [arXiv Pi-ratings feature set](https://arxiv.org/pdf/2308.02414)).
- **Where a real signal exists (thin but plausible).** Derbies/local rivalries carry genuine, persistent psychological/tactical dynamics that survive squad turnover; recent H2H form can outweigh league form in high-stakes derbies ([Better World Master](https://www.betterworldmaster.com/blog/head-to-head-records.php)). Tactical style-mismatch (a disciplined low block repeatedly frustrating a possession side) is a recognized mechanism but hard to quantify and not established as a stable, exploitable edge in the sources found.
- **Strong vs folklore:** Mostly folklore — "bogey team" narratives are largely small-sample artifacts. Weak-but-real — derby variance and gross style mismatches. No tier-1 source found quantifying a durable, bettable tactical-matchup edge for FPL.

**How to apply:** Do NOT add an explicit H2H term to player projections — risk of overfitting to noise. If capturing style at all, encode *team-level* tactical priors (e.g. opponent PPDA/press intensity, defensive-block xGA profile from FBref) that already feed the xGA/xGF fixture model in Axis 1, rather than pair-specific history. Treat derby GWs as higher-variance (widen captaincy uncertainty), not higher-EV.

---

### Axis 4: Set-piece & penalty takers — **Suggested weight: HIGH — "penalty duty is one of the most reliable point-ceiling boosters; verify taker each season"**

- **Penalties are near-free goals.** Opta assigns a flat 0.78–0.79 xG per penalty ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal); [Jobs In Football](https://jobsinfootball.com/blog/what-is-the-xg-of-a-penalty/)) — StatsBomb 0.78, Wyscout 0.76. Only ~0.8% of all non-penalty shots (81 of 10,189 in a season) are worth ≥0.78 xG, so a penalty is a chance quality virtually unattainable in open play ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal)).
- **Conversion at an all-time high.** Four-season PL average (2020/21–2023/24) was 81.9% converted, the best four-year run in history; 2023/24 hit 89.6% (record), with keepers saving just 7.5% ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal)). PL averages ~98–108 penalties/season (~0.26–0.28 per match) post-VAR ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal); [Oddspedia](https://oddspedia.com/insights/football/premier-league-penalty-takers)).
- **Fantasy value.** Being first-choice penalty taker gives a consistent, high-probability goal route; corner/free-kick duty materially lifts assist potential. A designated taker is "immediately a much better FPL asset" ([Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2026/04/08/fpl-set-piece-and-penalty-takers-for-all-20-clubs-updated-3)). Penalties were 7.9% of all PL goals in 2023/24 ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal)) — a large slice concentrated on ~20 designated players. Rough ceiling math: ~5 penalties/season for a lead taker × ~0.82 conversion ≈ 4 extra goals ≈ ~16–20 FPL pts on top of open-play output.
- **Identifying the taker reliably.** No single official source; cross-reference: (a) FFS's per-club set-piece/penalty taker list, updated in-season ([FFS 2026/27 list](https://www.fantasyfootballscout.co.uk/fantasy-premier-league-set-piece-takers)); (b) corroborate with Fantasy Football Fix, OneFPL, allaboutfpl ([FFFix](https://www.fantasyfootballfix.com/blog-index/fpl-set-piece-takers-2026-27/); [OneFPL](https://onefpl.com/blog/fpl-penalty-set-piece-takers-2026-27)); (c) ground-truth against actual events via FBref/Understat penalty-taken logs and the official FPL bootstrap. Hierarchy matters — list the 1st and 2nd taker, because injuries/transfers/subs reassign duty mid-season.
- **Strong vs folklore:** Strong and well-quantified — penalty xG, conversion trend, and value concentration are all Opta-backed. Caveat — taker identity is volatile (new signings, managerial changes, on-pitch disputes) so must be re-verified, not hard-coded.

**How to apply:** Maintain a per-club taker table (penalties, direct FKs, corners; 1st + 2nd choice) refreshed each GW from FFS cross-checked against FBref penalty logs and the FPL API. Add an explicit "is-penalty-taker" boost to a player's goal expectation (≈ +0.05–0.08 goals/game for a lead taker on a penalty-winning side) and a smaller corner/FK boost to assist expectation. Downgrade immediately on taker change/injury.

---

## Sources

**Home advantage (academic / tier-1):**
- University of Leeds — empty-stadium home-advantage study: https://www.leeds.ac.uk/news-science/news/article/4894/how-empty-stadiums-affected-football-during-pandemic
- Northumbria University press release: https://newsroom.northumbria.ac.uk/pressreleases/football-without-the-fans-new-study-reveals-effect-of-empty-stadiums-during-pandemic-3121743
- Significance magazine — home advantage since COVID (win ratios by season/division): https://significancemagazine.com/home-advantage-whats-changed-since-covid/
- Sky Sports Between the Lines — home advantage on the wane (long-run + current figures): https://www.skysports.com/football/news/11095/13511444/home-advantage-is-on-the-wane-in-the-premier-league-between-the-lines
- Football Perspectives — home advantage data (~0.25 goals current): https://footballperspectives.org/home-advantage-football-what-can-data-tell-us/
- PMC — home advantage across European leagues during COVID: https://pmc.ncbi.nlm.nih.gov/articles/PMC8670806/

**Fixture difficulty:**
- FPL Review — goalscoring model more predictive than bookmaker odds: https://fplreview.com/a-goalscoring-model-more-predictive-than-inferrences-from-bookmakers/
- Fantasy Football Scout ticker (FFS Elo, CS%, Projected Goals): https://www.fantasyfootballscout.co.uk/fpl/ticker
- OddAlerts — odds-derived FDR methodology: https://www.oddalerts.com/fpl/fixture-ticker
- FPL Copilot — xPts vs FDR, home/away limitation: https://fplcopilot.com/blog/fpl-fixture-difficulty-rating
- FPL360 — FDR flaws (attack/defence not separated): https://fpl360.com/2026/05/06/fpl-fixture-difficulty-rating-explained-use-fdr-for-better-transfers/

**Match prediction / H2H (academic + analysis):**
- Dixon-Coles time-weighted model (dashee87): https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/
- MDPI — Poisson regression PL prediction: https://www.mdpi.com/2076-3417/14/16/7230
- arXiv — online skill rating / Pi-ratings feature set: https://arxiv.org/pdf/2308.02414
- Better World Master — H2H records used properly (limits, derby caveat): https://www.betterworldmaster.com/blog/head-to-head-records.php

**Penalties / set-pieces (Opta + FPL community):**
- Opta Analyst — penalties never closer to a free goal (conversion, xG, frequency): https://theanalyst.com/articles/premier-league-penalties-like-free-goal
- Jobs In Football — xG of a penalty (provider comparison): https://jobsinfootball.com/blog/what-is-the-xg-of-a-penalty/
- Fantasy Football Scout — set-piece & penalty takers, all 20 clubs: https://www.fantasyfootballscout.co.uk/2026/04/08/fpl-set-piece-and-penalty-takers-for-all-20-clubs-updated-3
- Fantasy Football Scout — 2026/27 set-piece takers list: https://www.fantasyfootballscout.co.uk/fantasy-premier-league-set-piece-takers
- Fantasy Football Fix — set-piece takers 2026/27: https://www.fantasyfootballfix.com/blog-index/fpl-set-piece-takers-2026-27/
- OneFPL — penalty & set-piece takers 2026/27: https://onefpl.com/blog/fpl-penalty-set-piece-takers-2026-27
- Oddspedia — PL penalty takers / frequency: https://oddspedia.com/insights/football/premier-league-penalty-takers
