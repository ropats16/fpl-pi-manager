# Cluster A — Core Predictive Signals: Evidence Base

Research for the FPL autonomous-manager. Each axis: a **suggested (non-binding) weight**, cited evidence
(strong vs folklore flagged), and a "How to apply" line. Weights are relative importance for a per-gameweek
points projection, not literal model coefficients.

---

### 1. Minutes / expected minutes (xMins) as the base multiplier — **Suggested weight: HIGH — the foundational gate; everything else multiplies through it**

- xMins is the average minutes a player plays across a Monte Carlo simulation (e.g. 1,000 sims), "factoring in rotation, injury risk, tactical considerations and the latest news." A value like 51 xMins is a *blend* of start-and-sub scenarios, not a class label ([FPL Review docs](https://docs.fplreview.com/the-model/projections/xmins/)). **Strong / industry-standard.**
- Expected points (xPts) is explicitly built as minutes × (xG + xA + clean-sheet prob + bonus) converted to FPL scoring — i.e. all attacking/defensive EV is conditioned on being on the pitch ([FPL Copilot xPts explainer](https://fplcopilot.com/blog/expected-points-explained); [Marcus Leadboot, Modelling xPts](https://medium.com/@marcusleadboot/modelling-xpts-in-fpl-gameweek-1-01fd2179eac6)).
- "Appearance minutes are the foundation of FPL performance... not picking too many players with minutes risk is crucial to sustainable success" ([FPL DNA Minutes Risk](https://www.fpldna.com/learn/minutes-risk/)). Academic work frames rotation/injury/congestion forecasting as "the primary lever for competitive advantage" ([OpenFPL, arXiv 2508.09992](https://arxiv.org/html/2508.09992v1); [data-driven FPL team selection, arXiv 2505.02170](https://arxiv.org/pdf/2505.02170)). **Strong.**
- Important non-linearity: EV is **not** directly proportional to xMins because of FPL's scoring structure ([FPL Review docs](https://docs.fplreview.com/the-model/projections/xmins/)). The 60-minute boundary is the key kink — a player earns 1 appearance point under 60 min and 2 at/over 60 min, and clean-sheet points (defenders/GK) require 60+ min, so the minutes→points curve is a step-plus-ramp, not linear. A 55-min-projected player is far less than 55/90ths of a 90-min player's EV for CS-dependent returns.
- **Evidence quality:** Strong and near-universal across every serious FPL model. The *magnitude* of decay/rotation adjustments is proprietary and model-specific (folklore-ish in exact numbers), but the principle that minutes is the base multiplier is settled.

**How to apply:** Make xMins a multiplicative gate on all EV, but model it via the 60-minute threshold (P(start), P(60+ min | start)) rather than a linear minutes fraction; hard-penalize sub/rotation-risk players (xMins well below ~70) and let CS-dependent EV collapse sharply below 60 projected minutes.

---

### 2. Betting odds (clean-sheet, anytime-scorer) as short-term predictors — **Suggested weight: HIGH for the short horizon (next 1–2 GWs); the best-calibrated external signal available**

- Bookmaker odds are **well calibrated** but **not fully efficient** — mispricings persist from overrounds, limited competition, pricing conventions and behavioural biases ([Sascha Wilkens, Bundesliga study, SAGE 2026](https://journals.sagepub.com/doi/10.1177/22150218261416681)). **Strong.**
- Odds' calibration/forecast accuracy has **improved over time** and generally exhibits superior statistical calibration to open models; models that beat them do so only by capturing residual signal (e.g. an xG-based model earned ~10–15% ROI, and a calibrated in-play model *almost* matched Betfair: 70.2% vs 70.6% accuracy) ([efficiency of fixed-odds forecasting review](http://previsaosimples.pbworks.com/w/file/fetch/65223638/soccerForecasting.pdf); [market-calibrated in-play model, arXiv 2605.16066](https://arxiv.org/pdf/2605.16066)). Takeaway: **treat odds as a strong prior your model must beat, not merely match.**
- Convert odds → probability by removing the overround/vig. Raw implied prob = 1/decimal_odds; summed across all outcomes this exceeds 100% (typical Premier League margins ~3–6%). De-vig to recover fair probabilities ([Pinnacle Odds Dropper, overround](https://www.pinnacleoddsdropper.com/blog/overround); [GammaStack, how odds are made](https://www.gammastack.com/blog/how-do-bookmakers-generate-sports-odds/)). **Strong.**
- De-vig methods: **(a) Multiplicative / basic normalization** — divide each raw implied prob by the booked sum (fast, most common, slightly overstates favourites). **(b) Shin method** — accounts for insider trading, more accurate at the extremes. **(c) Power/Logarithmic methods.** Multiple devig methods exist precisely to strip bookmaker margin to estimate true odds ([no-vig calculator explainer](https://infinitycalculator.com/sports/no-vig-calculator); [MDPI, domain-driven football probabilities](https://www.mdpi.com/2227-7390/13/24/3976)). For a two-way market (e.g. clean sheet: yes/no), multiplicative normalization is fine; for anytime-scorer, note it is a one-sided market so use the yes/no pair or an established devig.

**How to apply:** For the imminent GW, pull clean-sheet and anytime-scorer odds, de-vig (multiplicative baseline; Shin if precision at extremes matters), and use the fair probabilities directly for CS EV (def/GK) and goal EV (att/mid). Blend with your own model only when your model has a defensible edge; otherwise defer to the (better-calibrated) market.

---

### 3. xG / xA over raw historical points — **Suggested weight: HIGH for underlying-talent estimation; MED as a direct short-term points predictor (sample-size sensitive)**

- xG/xA are more *stable* and more predictive of future returns than raw past goals/points: xG ratio is "the most predictive in forecasting team-season outcomes on a game-by-game basis," beating other past metrics for rest-of-season performance ([Tony ElHabr, xG predictor of future results](https://tonyelhabr.rbind.io/posts/xg-predictor-future-results/)). "Over the long term, xG stabilizes, showing true attacking strength" ([Performance Odds, xG deep dive](https://www.performanceodds.com/how-to-guides/expected-goals-deep-dive-how-xg-can-predict-your-next-winning-bet/)). **Strong.**
- Provider matters: Understat shows lower prediction error than Opta in the Bundesliga, Premier League and Serie A; Opta is more stable in La Liga/Ligue 1 ([Comparative Analysis of xG Models, ResearchGate](https://www.researchgate.net/publication/387250442_Comparative_Analysis_of_Expected_Goals_Models_Evaluating_Predictive_Accuracy_and_Feature_Importance_in_European_Soccer)). For PL, Understat is a reasonable free primary source ([FBref/StatsBomb also usable]).
- **Sample-size caveat (the key contested point):** xG only stabilizes over meaningful shot volume. Small samples mislead — entropy/shot-distribution measures are "sensitive to sample size," with low-volume shooters appearing artificially concentrated ([Marc Lamberts, entropy-adjusted xG](https://marclamberts.medium.com/introducing-entropy-adjusted-expected-goals-xg-adj-bea333c1e5ad)). Early-season xG per 90 off 2–4 games is noisy; do not treat it as settled talent. **This is where xG should be shrunk toward a multi-season prior (see Axis 6).**
- Nuance: subsetting xG to "neutral gamestate" does **not** improve prediction over overall xG ([ElHabr](https://tonyelhabr.rbind.io/posts/xg-predictor-future-results/)) — don't over-engineer gamestate filters.

**How to apply:** Use per-90 xG/xA (Understat/FBref) as the estimator of finishing/creation talent that feeds goal & assist EV, in preference to raw past FPL points; but weight it by sample size (shot/chance volume) and shrink low-sample values toward the player's multi-season baseline before using them.

---

### 4. Form recency weighting — **Suggested weight: MED — real but easily overweighted; a tilt on the underlying estimate, not the estimate itself**

- Recent games *are* more predictive than older ones, so models weight samples by recency — but "not just simple linear decay; carefully tuned to balance enough history whilst prioritising recent form" ([Rittim AI FPL Manager](https://rittim.com/projects/ai-fpl-manager)). A validated gradient scheme (1.5× down to 0.6× across recent matches) reported **31% better predictive power than flat averages** ([FormBaller methodology](https://www.formballer.com/methodology)). **Moderate-strong.**
- Common windows: last 1–5 games are the standard lookback; form is often a weighted sum of residuals over the previous *x* games with most weight on the latest ([data-driven FPL framework, arXiv 2505.02170](https://arxiv.org/pdf/2505.02170); [FPL Form](https://fplform.com/)).
- **Regression to the mean is the dominant caveat and the anti-folklore point:** "team form" / hot streaks are heavily driven by recency bias and regress hard — much of what looks like form is noise ([Harvard Sports Analysis, Form, Recency Bias & Regression to the Mean](https://harvardsportsanalysis.org/2015/08/team-form-recency-bias-and-regression-to-the-mean/)). FPL's own "Form" stat (raw points over last 30 days) is especially noisy and finishing-luck-driven. **Treat raw recent points as weak; treat recent *underlying* numbers (xG/xA) as stronger.**

**How to apply:** Apply a mild geometric decay over the last ~4–6 games to *underlying* metrics (xG/xA, minutes, role), not to raw points; keep the decay gentle and always regress toward the season/multi-season mean so a 2-game purple patch doesn't dominate the projection.

---

### 5. Pre-season friendlies as predictors — **Suggested weight: LOW for output; MED-to-HIGH only for the minutes/role/set-piece signal**

- **Attacking output in friendlies is largely noise.** Direct FPL analysis of 2025/26 friendlies found poor correlation with league returns: Ollie Watkins had 5 goals + assist in pre-season then just one attacking return in his first 13 matches; Harry Wilson likewise faded. Conversely Antoine Semenyo did "very little in pre-season" then a Anfield opening brace launched a 17-goal season ([Fantasy Football Scout — Does pre-season form count for anything?](https://www.fantasyfootballscout.co.uk/2026/08/09/does-pre-season-form-count-for-anything)). **Strong (domain-specific).**
- Team-level pre-season results are also weak predictors: good-pre-season sides (Liverpool, City, Chelsea, Brighton, etc.) scattered across 1st–19th after six GWs ([Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2026/08/09/does-pre-season-form-count-for-anything)). One asymmetry noted: "bad summers tend to keep going" (struggling teams stayed poor) — weak, anecdotal.
- **What *does* carry signal:** minutes, formation, set-piece/penalty duties, new-signing integration and fitness — especially in the *final* friendlies and official (not behind-closed-doors) matches. "Pre-season minutes, especially in the final kickabouts, are usually a good way of predicting line-ups for Gameweek 1" ([Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2026/08/09/does-pre-season-form-count-for-anything); [FFS pre-season guide](https://www.fantasyfootballscout.co.uk/fpl-2026-27-the-ultimate-pre-season-guide-tips-more)). **Moderate.** Caveat: pre-season minutes are not a guaranteed GW1 start while internationals reintegrate.

**How to apply:** Use friendlies only to inform the *minutes/role* inputs (likely starter, set-piece/penalty taker, position) — especially final friendlies and official fixtures — and explicitly **ignore friendly goal/assist tallies** as a talent or form signal. Never downgrade a proven player for a quiet friendly (see Axis 6).

---

### 6. "Class player" prior — **Suggested weight: HIGH as a stabilizing prior; it should dominate when recent evidence is thin (early season / pre-season)**

The Bayesian-shrinkage rationale: for players with sparse recent data, posterior estimates should lean on the prior; for players with rich data, the observed data dominates. Football-analytics work confirms informative priors "substantially improved parameter estimation... particularly valuable for players with limited samples," and "for players with sparse samples, posteriors leaned more heavily on priors" ([Frontiers — Bayesian approach to predict football performance](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1486928/full); [Dwarfs on the Shoulders of Giants — informative priors in elite sport](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8970347/)). Informative priors are "particularly practical for very small samples when the goal is decision-making rather than generalizable inference" — exactly the GW1 case. A rolling **2–3 year** window of prior stats is "statistically sufficient for meaningful Bayesian predictions" ([Braun, Bayesian fantasy football](https://nathanbraun.com/bayesian-fantasy-football/); [srome, Bayesian hierarchical fantasy projections](https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/)). **Strong methodologically; the concrete parameterization below is my synthesis, not a single cited standard.**

**Concrete, usable definition of the class prior:**
- **Prior mean μ₀** = the player's minutes-weighted **xGI/90 (xG + xA per 90)** over the last 2–3 seasons (use FBref/Understat), combined with:
  - **Established role** (nailed starter? penalty/set-piece taker? attacking position) — gate the prior by expected minutes.
  - **Historical points ceiling** (best-season FPL points / PPG) to set the upside of the EV distribution.
- **Prior strength κ** (in "pseudo-games") = confidence in the prior, larger for long, consistent multi-season histories (e.g. Haaland, Salah → κ ≈ 15–20 games' worth) and smaller for players with volatile or short histories.
- **Blend (shrinkage):** posterior estimate = (κ·μ₀ + n·x̄_recent) / (κ + n), where n = recent games observed and x̄_recent = recent underlying rate. With n small (pre-season, n≈0; GW1–3, n≤3) the estimate stays near μ₀; as the season accrues, recent data takes over. This is the standard shrinkage / empirical-Bayes formula ([Frontiers Bayesian](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1486928/full); [Braun](https://nathanbraun.com/bayesian-fantasy-football/)).
- **Practical guardrail:** never let a single quiet friendly or 1–2 blank GWs move a high-κ player's projection more than a small fraction — the math above enforces this automatically because n is tiny relative to κ.

**How to apply:** For each player compute μ₀ from 2–3-season minutes-weighted xGI/90 + role + points ceiling, assign κ by history length/consistency, and project via posterior = (κμ₀ + n·x̄_recent)/(κ+n). Early season this keeps Haaland priced as Haaland regardless of a flat pre-season; the prior's grip decays organically as real matches accumulate.

---

## Sources

- FPL Review — xMins docs: https://docs.fplreview.com/the-model/projections/xmins/
- FPL Copilot — Expected Points explained: https://fplcopilot.com/blog/expected-points-explained
- Marcus Leadboot — Modelling xPts in FPL: https://medium.com/@marcusleadboot/modelling-xpts-in-fpl-gameweek-1-01fd2179eac6
- FPL DNA — Minutes Risk guide: https://www.fpldna.com/learn/minutes-risk/
- OpenFPL (arXiv 2508.09992): https://arxiv.org/html/2508.09992v1
- Data-driven FPL team selection (arXiv 2505.02170): https://arxiv.org/pdf/2505.02170
- Wilkens — Can simple models beat the odds? Bundesliga (SAGE 2026): https://journals.sagepub.com/doi/10.1177/22150218261416681
- Forecasting football results & efficiency of fixed-odds (review PDF): http://previsaosimples.pbworks.com/w/file/fetch/65223638/soccerForecasting.pdf
- Market-calibrated in-play forecasting model (arXiv 2605.16066): https://arxiv.org/pdf/2605.16066
- Pinnacle Odds Dropper — Overround explained: https://www.pinnacleoddsdropper.com/blog/overround
- GammaStack — How bookmakers generate odds: https://www.gammastack.com/blog/how-do-bookmakers-generate-sports-odds/
- Infinity Calculator — No-Vig / devig methods: https://infinitycalculator.com/sports/no-vig-calculator
- MDPI — Domain-driven identification of football probabilities: https://www.mdpi.com/2227-7390/13/24/3976
- Tony ElHabr — xG as predictor of future results: https://tonyelhabr.rbind.io/posts/xg-predictor-future-results/
- Performance Odds — xG deep dive: https://www.performanceodds.com/how-to-guides/expected-goals-deep-dive-how-xg-can-predict-your-next-winning-bet/
- Comparative Analysis of xG Models (ResearchGate): https://www.researchgate.net/publication/387250442_Comparative_Analysis_of_Expected_Goals_Models_Evaluating_Predictive_Accuracy_and_Feature_Importance_in_European_Soccer
- Marc Lamberts — Entropy-adjusted xG (sample-size sensitivity): https://marclamberts.medium.com/introducing-entropy-adjusted-expected-goals-xg-adj-bea333c1e5ad
- Rittim — AI FPL Manager (recency weighting): https://rittim.com/projects/ai-fpl-manager
- FormBaller — Form score methodology (gradient recency weighting): https://www.formballer.com/methodology
- Harvard Sports Analysis — Team Form, Recency Bias & Regression to the Mean: https://harvardsportsanalysis.org/2015/08/team-form-recency-bias-and-regression-to-the-mean/
- FPL Form: https://fplform.com/
- Fantasy Football Scout — Does pre-season form count for anything?: https://www.fantasyfootballscout.co.uk/2026/08/09/does-pre-season-form-count-for-anything
- Fantasy Football Scout — Ultimate pre-season guide 2026/27: https://www.fantasyfootballscout.co.uk/fpl-2026-27-the-ultimate-pre-season-guide-tips-more
- Frontiers — A Bayesian approach to predict performance in football: https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1486928/full
- Dwarfs on the Shoulders of Giants — informative priors in elite sport (PMC): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8970347/
- Nathan Braun — Bayesian fantasy football (2–3 yr prior window): https://nathanbraun.com/bayesian-fantasy-football/
- srome — Bayesian hierarchical fantasy projections: https://srome.github.io/Bayesian-Hierarchical-Modeling-Applied-to-Fantasy-Football-Projections-for-Increased-Insight-and-Confidence/
