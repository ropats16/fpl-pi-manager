# Discovery: Quantitative / Sports-Analytics Lens

What actually drives good FPL selection **beyond** the naive list (minutes, xG/xA, fixtures, odds,
form, home/away, set-pieces, price, captaincy). Every claim is sourced. Where the community
consensus is wrong per the data, it is flagged.

Overarching finding: the biggest edges are NOT better point-estimates of expected points. They are
(a) knowing which stats are *signal vs noise* so you don't chase mirages, (b) modeling the **whole
XI as a correlated portfolio** rather than 11 independent means, and (c) optimizing against **the
field** (rank) and **across weeks** rather than one gameweek's raw EV.

---

### Finishing over/under-performance (goals − xG) is mostly noise, not skill — **Suggested weight: HIGH (as a *fade* signal / prior toward xG, not goals)**

- Year-over-year, "a positive GAX [goals above expected] in one season does not necessarily elevate the likelihood of a positive residual in the subsequent season" — finishing outperformance does not persist. [KU Leuven DTAI](https://dtai.cs.kuleuven.be/sports/blog/biases-in-expected-goals-models-confound-finishing-ability/)
- Even a genuinely elite finisher (25% better than average, 100+ shots/yr) beats cumulative xG in ≥4 of 5 seasons only ~70% of the time; a 10%-better finisher at 125 shots only 41.6%. Detecting real finishing skill needs "a few hundred shots"; you see first signal around 75+ shots. [KU Leuven DTAI](https://dtai.cs.kuleuven.be/sports/blog/biases-in-expected-goals-models-confound-finishing-ability/), [StatsBomb](https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/)
- "G minus xG is poorly predictive of itself season-over-season and can be even more misleading than raw G/xG in portraying players strongly over- or under-performing in small samples." [American Soccer Analysis](https://www.americansocceranalysis.com/home/2023/8/28/the-replication-project-measuring-shooting-overperformance)
- Only ~5 players in modern datasets ever reach 500 shots; almost no single-season sample is large enough to call a player a good finisher with significance. [StatsBomb](https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/)
- **How to apply:** Rank/price players on underlying xG/xA (and shot volume/quality), NOT on actual goals. Treat a hot player whose goals >> xG as a *sell/avoid* candidate (regression coming); treat goals << xG as a *buy* (positive regression). Shrink single-season finishing toward the mean.
- **Why it's missed:** Naive managers (and the FPL "form" column) chase actual goals and recent hauls — the exact quantity that regresses hardest. They mistake variance for skill.

### Rank-differential / effective-ownership game theory: max rank ≠ max expected points — **Suggested weight: HIGH**

- FPL scoring is points-based, so "owning the same players as other smart managers does not make you rank against them" — shared players give everyone identical points; you can only *gain rank* on players you own differently from the field. [FPL Oracle](https://fploracle.team/blog/template-vs-differential-fpl)
- **Effective Ownership (EO)** = start% + captain%, and captaincy can push a premium above 90% EO (e.g. 55% owned × 65% captained ≈ 91% EO). A player you *don't* own at 91% EO is a rank liability even if he's not in your risk budget. [FPL Oracle](https://fploracle.team/blog/effective-ownership-fpl), [Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions)
- Concrete lever: differential captain becomes +EV for rank when the template captain's EO > ~70% and the alternative is within ~2 xPts with EO < ~35%; when *protecting* a rank you need a ≥2 xPts edge to stay template. [FPL Oracle](https://fploracle.team/blog/fpl-captaincy-strategy)
- **How to apply:** The optimizer's objective should be a function of `xPts − EO` (or explicitly maximize expected *rank*), not raw xPts. Feed in each player's ownership/EO; penalize captaining/holding ultra-high-EO assets only when a near-equal alternative exists; size differentials to your rank goal (chasing = take variance, defending = hug template).
- **Why it's missed:** Naive managers optimize raw total points in a vacuum. Against 11M entrants, two teams with identical expected points can have wildly different *expected rank*; the whole game is relative.

### Whole-XI variance & inter-player covariance (stacking / portfolio effects) — **Suggested weight: HIGH**

- Most FPL optimizers "assume players do not have correlated errors and ignore covariance/variance while focusing on expected points" — a known, exploitable blind spot. [Fantasy Football Reports](https://www.fantasyfootballreports.com/variance-fpl/)
- Serious sim tools (FPL Optimized, using FPL Review rates) explicitly Monte-Carlo whole-gameweek outcomes rather than summing means, precisely to capture that same-team/same-match returns move together. [FPL Optimized](https://fploptimized.com/scenarios.html)
- Two teammates (e.g. a defender + attacker on the same club) are *positively* correlated on clean-sheet / winning scripts, which raises your XI's variance (good when chasing, bad when defending). A defender vs. an opposing attacker are *negatively* correlated — a natural variance hedge.
- **How to apply:** After picking on mean xPts, evaluate the covariance structure: count same-team doubles/triples, captain-on-a-stack, and defender/attacker pairs in the *same* match. Deliberately raise stacking + team variance when you need rank upside; deliberately diversify across matches to lower variance when protecting rank. Judge the XI on its *distribution*, not the sum of 11 means.
- **Why it's missed:** Linear-programming/"pick top-11-by-xPts" builders treat players as independent assets. They systematically mis-price both the reward of a correlated ceiling and the risk of a correlated floor.

### Score distributions are right-skewed — optimize ceiling/floor, not the mean — **Suggested weight: MED-HIGH**

- FPL point distributions have "a hard left edge... and a long right tail"; the floor is rigid (≈2 for playing, blanks common) but the ceiling is open (hauls). [FPL Optimized scenarios](https://fploptimized.com/scenarios.html)
- The best public model (OpenFPL) is explicitly tuned to predict **"Haulers" (≥5 pts)** well and uses **entropy-based discretization** to avoid equal-weighting outcomes — i.e. it deliberately trades average accuracy to nail the rare high-return events that decide rank. [OpenFPL (arXiv 2508.09992)](https://arxiv.org/html/2508.09992v1)
- **How to apply:** Store per-player *distributions* (or at least a ceiling/floor / P(haul)) not just a point estimate. Pick captains and differentials on ceiling/P(haul); pick set-and-forget defenders and bench fodder on floor. Two players with equal mean but different skew are not interchangeable.
- **Why it's missed:** Naive tools reduce each player to one xPts number, which throws away the skew that actually wins mini-leagues and green arrows.

### Minutes/availability as a categorical gate, not a continuous "expected minutes" — **Suggested weight: HIGH**

- The state-of-the-art open model **dispenses with proprietary "expected minutes"** and instead uses the FPL API's categorical availability tags (0/25/50/75/100% chance of playing) — and still rivals commercial services. [OpenFPL (arXiv 2508.09992)](https://arxiv.org/html/2508.09992v1)
- Where OpenFPL *loses* to commercial FPL Review is almost entirely on **"Zeros" (non-playing players): 15% worse RMSE** — proving that correctly predicting who *doesn't* start is one of the largest remaining edges in the whole problem. [OpenFPL (arXiv 2508.09992)](https://arxiv.org/html/2508.09992v1)
- Autosub trigger is binary: a starter must play **exactly 0 minutes** to be subbed; 1 minute keeps him in and blocks the sub. [Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs)
- **How to apply:** Model minutes as a distribution over {0, cameo, ~60, 90} gated by the availability flag and rotation history, then propagate that into the points distribution. The single highest-leverage data pull each deadline is the "chance of playing" flag + predicted lineups; treat unresolved rotation as a hard variance/penalty, not a shaved mean.
- **Why it's missed:** Naive managers use season xPts without discounting start probability, and get repeatedly blanked by benchings, cup rotation, and knocks — the error concentrated exactly where models are weakest.

### Multi-week planning horizon & the true EV of a −4 hit — **Suggested weight: HIGH**

- A −4 must be judged on **net gain over ~3–4 gameweeks**, not one; "most knee-jerk transfers don't clear that bar over 3 GWs." [Full90 FPL](https://full90fpl.com/fpl-transfers-explained/)
- Optimal horizon for solvers is ~5–6 GWs ("that's where the biggest gains are"): a player worth 4.5 this week / 2.1 next loses to one worth 3.8 + 4.2 over the horizon. Banking a free transfer is itself a valued option in the plan. [FPL Copilot planner](https://fplcopilot.com/blog/transfer-planning-guide), [FPL Tactics](https://fpltactics.com/team-planner)
- **How to apply:** Optimize cumulative xPts over a rolling 5–6 GW window, treating free-transfer banking, one-now-one-later, and −4 hits as competing paths; only take a hit when the *horizon* delta > 4 (+ EO/variance adjustment). Value fixture *swings* and the flexibility of holding a transfer, not just this week's best XI.
- **Why it's missed:** Naive managers make reactive one-week transfers on last week's returns, repeatedly paying −4s that never clear the multi-week bar.

### Bonus Points System (BPS): large, semi-predictable, and rule-volatile — **Suggested weight: MED**

- Bonus is **15–20% of a top manager's season total** — too big to ignore, but "a high total BPS does not necessarily equal more Bonus points" (only top-3 per match score, so it's a *ranking within a match*, not a sum). [Ingenuity Fantasy](https://ingenuityfantasy.com/game-week-tips/fpl-bonus-points-how-its-scored-how-to-use-it-to-your-advantage/), [Premier League](https://www.premierleague.com/en/news/106533)
- BPS rules change yearly and reshape which archetypes win bonus: 2025/26 shifted GK save value by shot location and raised goal-line clearances 3→9 BPS; 2026/27 removed a metric so dribble-heavy "flair" players are no longer punished and DefCon monsters find bonus harder. Any model trained on old seasons is mis-calibrated. [Fantasy Football Scout 2025/26](https://www.fantasyfootballscout.co.uk/2025/07/19/fpl-2025-26-all-the-bonus-points-changes-explained), [Premier League 2026/27](https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system)
- **How to apply:** Model bonus as a *within-match rank* of BPS components (not a per-player constant), and re-fit BPS weights to the *current* season's ruleset. Favor players who dominate a match's BPS profile (goals + high pass/defensive volume on their own team) over those who split it.
- **Why it's missed:** Naive managers treat bonus as random luck, and models silently carry stale BPS coefficients across rule changes.

### Clean sheets: use xGA/underlying defence, treat actual CS as high-variance — **Suggested weight: MED**

- Actual goals-conceded / clean sheets are volatile week to week; "if a team has been conceding more than their xGA suggests, they may be due for positive regression (more clean sheets), and vice-versa." xGA is the stabler signal. [Marcus Leadboot — xCS](https://medium.com/@marcusleadboot/modelling-expected-clean-sheets-xcs-10ccca701403)
- The defensive picture is multi-factor (opponent attack strength × own defence × game state), so single-metric CS predictions are weak. [MyDeepMetrics](https://mydeepmetrics.com/statistics/clean-sheets-defensive-statistics)
- **How to apply:** Drive defender/GK selection off an expected-clean-sheet model built on team xGA and opponent xG, and *buy defences whose recent CS count lags their xGA* (regression tailwind). Don't extrapolate a run of clean sheets that the underlying numbers don't support.
- **Why it's missed:** Naive managers buy defenders on recent clean-sheet streaks — a noisy, mean-reverting count — instead of on the stable underlying defensive rate.

### Official FDR is position-blind and lags reality (attack/defence asymmetry) — **Suggested weight: MED**

- The official FDR "applies the same rating to every player regardless of position." A team can be great in attack and leaky in defence, so one number can't be right for both an attacker and a defender facing that opponent. [Marcus Leadboot — FDR adjusted](https://medium.com/@marcusleadboot/fpl-fixture-difficulty-ratings-fdr-adjusted-for-attack-defence-6828a9713696)
- FDR also lags: a mid-season manager change or tactical shift leaves the rating stale "for several weeks while the rolling data catches up" — the lag *is* the edge. [FPL Copilot FDR](https://fplcopilot.com/blog/fpl-fixture-difficulty-rating)
- **How to apply:** Replace the single FDR with **two** ratings — opponent *defensive* strength (for your attackers) and opponent *attacking* strength (for your defenders/GK) — built from recent xG/xGA, and weight recent form fast enough to catch manager changes before the public FDR does.
- **Why it's missed:** The naive list says "fixtures," and most managers use FPL's own one-size FDR, which is both position-blind and slow.

### Team-value compounding via price-change timing — **Suggested weight: LOW-MED**

- Disciplined early/ahead-of-the-crowd buying can add **£2–3m+** of team value over a season — enough to fund a premium upgrade you otherwise couldn't afford. [FPL Watch](https://fplwatch.com/blog/maximizing-team-value)
- Mechanics create asymmetry: max ±£0.3m per GW in £0.1m steps, and you only bank 50% (rounded down) of a *rise* — so value gained early compounds while sell-on is taxed. [Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2026/07/20/how-do-fpl-price-changes-work), [Premier League](https://www.premierleague.com/en/news/2858775)
- **How to apply:** As a *tie-breaker only* (never override xPts), prefer moves that catch predicted rises / dodge drops; front-load transfers on players with strong ownership-momentum early in the season. Model the 50%-sell-tax so value is only "real" as future buying power.
- **Why it's missed:** It's a slow, second-order compounding effect invisible in any single-week decision; easy to over-chase (value ≠ points) but real as an enabler.

### Bench order & formation as free expected points — **Suggested weight: LOW-MED**

- "Getting your bench order right is free points. Getting it wrong costs you every single gameweek" — autosubs only fire for players on **0** minutes and must preserve a legal formation, so bench *priority* materially changes expected returns. [OneFPL autosubs](https://onefpl.com/blog/fpl-auto-subs-bench-order-rules), [Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs)
- Formation shape changes autosub *quality*: a 5-mid shape gives "a deeper bench of midfield cover, meaning auto-substitutions are more likely to bring on a player with genuine points potential" instead of a £4m non-playing forward. [RotoWire](https://www.rotowire.com/soccer/article/best-fpl-formation-2026-27-which-shape-wins-fantasy-premier-league-127303)
- **How to apply:** Set bench order by each fringe player's P(0 minutes) × his conditional xPts-if-plays (highest expected autosub contribution first), subject to formation legality; choose the starting formation that maximizes *expected realized* points including the autosub option value, not just the nominal best XI.
- **Why it's missed:** Naive managers set bench order by "gut" or price and never quantify the option value; it's small per week but strictly free and compounds over 38 GWs.

### Modeling meta-insights: median-of-ensemble, multi-horizon features, tune for haulers — **Suggested weight: MED (for the model builder)**

- OpenFPL forecasts from the **median of 50 models** (top-10 of each of 5 CV folds) — median beats mean by suppressing outliers. It builds ~196–206 features over **1-, 3-, 5-, 10-, and 38-match horizons** to separate short-term form from long-term baseline, and it decomposes points into minutes / goals+assists / defensive-contribution / clean-sheet / discipline sub-models. [OpenFPL (arXiv 2508.09992)](https://arxiv.org/html/2508.09992v1)
- Low-return predictions sharpen 15–25% moving from a 3-GW to a 1-GW horizon, but high-return (haul) predictions show **no systematic horizon benefit** — the ceiling is inherently hard to time, which argues for holding hauler assets rather than chasing them week to week. [OpenFPL (arXiv 2508.09992)](https://arxiv.org/html/2508.09992v1)
- **How to apply:** Ensemble multiple models and take the median; engineer features at several look-back horizons; decompose points into independent sub-models; and evaluate on hauler-recall, not just RMSE. Don't over-transfer chasing hauls the data says you can't time.
- **Why it's missed:** DIY managers (and simple models) use a single point estimate over a single form window and optimize average error — mis-calibrated for the rare events that decide the season.

---

## Sources

- OpenFPL (open-source FPL forecasting rivaling commercial services), arXiv 2508.09992 — https://arxiv.org/html/2508.09992v1
- KU Leuven DTAI, "Biases in Expected Goals Models Confound Finishing Ability" — https://dtai.cs.kuleuven.be/sports/blog/biases-in-expected-goals-models-confound-finishing-ability/
- KU Leuven / arXiv 2401.09940 (paper) — https://arxiv.org/pdf/2401.09940
- StatsBomb, "Quantifying Finishing Skill" — https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/
- American Soccer Analysis, "Measuring Shooting Overperformance" — https://www.americansocceranalysis.com/home/2023/8/28/the-replication-project-measuring-shooting-overperformance
- FPL Oracle, Template vs Differential (EO math) — https://fploracle.team/blog/template-vs-differential-fpl
- FPL Oracle, Effective Ownership — https://fploracle.team/blog/effective-ownership-fpl
- FPL Oracle, Captaincy decision framework — https://fploracle.team/blog/fpl-captaincy-strategy
- Fantasy Football Scout, Effective ownership for differentials — https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions
- Fantasy Football Reports, Variance in FPL — https://www.fantasyfootballreports.com/variance-fpl/
- FPL Optimized, Monte Carlo scenarios — https://fploptimized.com/scenarios.html
- Full90 FPL, Transfers/hits explained — https://full90fpl.com/fpl-transfers-explained/
- FPL Copilot, Transfer planning guide — https://fplcopilot.com/blog/transfer-planning-guide
- FPL Tactics, Team planner (horizon solver) — https://fpltactics.com/team-planner
- Premier League, How the BPS works — https://www.premierleague.com/en/news/106533
- Fantasy Football Scout, 2025/26 BPS changes — https://www.fantasyfootballscout.co.uk/2025/07/19/fpl-2025-26-all-the-bonus-points-changes-explained
- Premier League, 2026/27 BPS changes — https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system
- Ingenuity Fantasy, Bonus points strategy — https://ingenuityfantasy.com/game-week-tips/fpl-bonus-points-how-its-scored-how-to-use-it-to-your-advantage/
- Marcus Leadboot, Modelling expected clean sheets (xCS) — https://medium.com/@marcusleadboot/modelling-expected-clean-sheets-xcs-10ccca701403
- MyDeepMetrics, Clean sheets & defensive statistics — https://mydeepmetrics.com/statistics/clean-sheets-defensive-statistics
- Marcus Leadboot, FDR adjusted for attack & defence — https://medium.com/@marcusleadboot/fpl-fixture-difficulty-ratings-fdr-adjusted-for-attack-defence-6828a9713696
- FPL Copilot, Fixture difficulty rating — https://fplcopilot.com/blog/fpl-fixture-difficulty-rating
- FPL Watch, Maximizing team value — https://fplwatch.com/blog/maximizing-team-value
- Fantasy Football Scout, How price changes work — https://www.fantasyfootballscout.co.uk/2026/07/20/how-do-fpl-price-changes-work
- Premier League, Player price changes — https://www.premierleague.com/en/news/2858775
- OneFPL, Autosubs & bench order rules — https://onefpl.com/blog/fpl-auto-subs-bench-order-rules
- Fantasy Football Scout, How substitutes/autosubs work — https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs
- RotoWire, Best FPL formation 2026/27 — https://www.rotowire.com/soccer/article/best-fpl-formation-2026-27-which-shape-wins-fantasy-premier-league-127303
