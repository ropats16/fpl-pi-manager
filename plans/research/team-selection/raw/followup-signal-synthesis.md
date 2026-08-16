# Signal Synthesis Methodology — Combining & Arbitrating Decision Signals

How a "gaffer" agent should COMBINE many individual signals (odds, xG/xA, minutes/start-prob, DEFCON, fixtures, form, effective ownership, class-player prior) into one decision, and RECONCILE them when they conflict. Focus is the combination/arbitration layer, cross-referenced against forecast-combination and calibration literature (established stats), with FPL practice flagged where it is folklore rather than proven.

Key framing up front: **this is a forecast-combination + calibration problem, and the literature has a robust, boring answer** — simple/near-equal weighting of a few de-correlated, individually-decent signals, wrapped in a hard minutes gate, then calibrated against reality. Fancy learned weights lose out-of-sample on small samples (which a Pi + one FPL season always is).

---

### 1. Market-vs-model blending — key recommendation: treat the closing betting line as a strong prior your model must *beat*, not merely echo; blend model as a *bounded adjustment* to the market prior, and validate the blend by Closing Line Value.

- The closing line is the most efficient publicly available price: it aggregates injuries, lineups, weather and sharp money, and "consistently beating it is the strongest predictor of long-term profitability — more reliable than short-term win rate" ([sports-ai.dev CLV guide](https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance)). Positive CLV is "the most reliable *leading* indicator of long-term profitability, outperforming realized ROI in short-to-medium sample sizes."
- A model earns the right to override the market only when it is *better calibrated* than the market. Concrete existence proof: PropsBot's MLB models post Brier 0.1903 vs Vegas 0.1947 — better-calibrated than the market, "which is the precondition for generating CLV" ([PropsBot CLV glossary](https://propsbot.ai/glossary/closing-line-value/); [sports-ai.dev](https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance)).
- Markets carry known *biases* you can exploit as adjustments: implied probabilities show **favourite-longshot / favourite bias** (favourites win more than implied) in La Liga, though Shin's model de-biases EPL odds to near-unbiased estimates ([Springer, betting market efficiency in binary choice models](https://link.springer.com/article/10.1007/s10479-022-04722-3)). So: convert odds to probabilities, remove the overround (Shin/Shin-vig method), and only then treat as prior.
- Simple xG-based models finetuned with **isotonic regression** can match or beat bookmaker-implied probabilities on calibration and accuracy ([Wilkens, Bundesliga, SAGE 2026](https://journals.sagepub.com/doi/10.1177/22150218261416681)); market-calibrated models (anchoring the model to the line, then adjusting) are an active research pattern ([market-calibrated AFT model, arXiv](https://arxiv.org/pdf/2605.16066)).
- Weighting guidance: give the de-vigged market probability the majority prior weight (start ~60–80%) and let the model move it only within a bounded band, widening the model's share only where you have evidence (a backtested bias, or a signal the market cannot see — e.g. your own minutes/DEFCON read). The market already prices team result, home/away and fixture, so your model's *marginal* value is the player-level stuff odds don't isolate.

**How to apply:** De-vig bookmaker odds → team goal/clean-sheet/result priors; let the model adjust each prior within a capped band (e.g. ±20% relative) only where a logged, backtested reason exists; log the pre- and post-adjustment number and, retrospectively, whether you beat the closing line.

---

### 2. Combining probabilistic signals — key recommendation: default to near-equal (or inverse-variance) *linear* pooling of a *small, de-correlated* signal set; take a **median across an ensemble** for point projections; use **log/geometric pooling only for genuinely independent sources**; and collapse correlated signals (odds already ≈ xG+home/away+fixtures) to avoid double-counting.

- **Linear opinion pool** (weighted arithmetic mean of probabilities, weights ≥0 summing to 1) is the standard, robust combiner ([Ranjan & Gneiting, *Combining Probability Forecasts*, JRSS-B 2010](https://academic.oup.com/jrsssb/article/72/1/71/7076442)). **Log-linear pool** averages log-odds (≈ geometric mean); it is the "most natural" externally-Bayesian pool but is sharper/more extreme ([JRSS-B combining probability forecasts search summary](https://academic.oup.com/jrsssb/article/72/1/71/7076442); [Heskes, log opinion pools, NeurIPS 1997](https://proceedings.neurips.cc/paper/1997/file/59f51fd6937412b7e56ded1ea2470c25-Paper.pdf)).
- **Redundant vs independent is the deciding rule:** "Linear pooling is better for aggregating redundant information, whereas logarithmic pooling is better for independent sources" ([log opinion pool literature summary](https://www.researchgate.net/publication/272422988_Choosing_the_weights_for_the_logarithmic_pooling_of_probability_distributions)). Because most FPL signals are *redundant* (odds encode xG, fixture, home/away; form encodes xG), lean **linear** and, crucially, **don't feed the same information in twice**.
- **Double-counting is the central hazard.** The hardest part of expert aggregation is the "high correlation or dependence that typically occurs among opinions"; naive combination over-weights whatever information is shared, and correctly de-correlating "requires a large number of samples" to estimate the joint distribution ([Sample Complexity of Forecast Aggregation, arXiv](https://arxiv.org/pdf/2207.13126)). Practical fix on a Pi: pre-group signals into near-independent *buckets* and combine one representative per bucket, rather than trying to estimate a full covariance.
- **Inverse-variance (precision) weighting** gives the minimum-variance combination when estimators are unbiased and independent — weight each signal ∝ 1/variance, i.e. noisier signals get less say ([Inverse-variance weighting, Wikipedia](https://en.wikipedia.org/wiki/Inverse-variance_weighting)). Use it as the principled way to down-weight a flaky signal (e.g. small-sample DEFCON) rather than dropping it.
- **Median-of-ensemble** is OpenFPL's actual production choice: "Ensemble model forecasts are obtained as the median forecasted FPL points of the 50 individual models" (per-position ensembles of XGBoost + Random Forest) — median for robustness to outlier sub-models ([OpenFPL, arXiv 2508.09992](https://arxiv.org/html/2508.09992v1); [code](https://github.com/daniegr/OpenFPL)). For a gaffer combining several point projections, **median is the safe aggregator**; mean if you trust them all equally.
- **Calibration caveat (important, counter-intuitive):** "Any non-trivial weighted average of two or more distinct, *calibrated* probability forecasts is necessarily *uncalibrated* and lacks sharpness" ([Ranjan & Gneiting 2010](https://academic.oup.com/jrsssb/article/72/1/71/7076442)). So a pooled probability should be **re-calibrated** afterward (their beta-transformed linear pool; in practice, isotonic/Platt on held-out data) before it drives a decision.

**How to apply:** Sort signals into independent buckets (result/CS from de-vigged odds • player attacking threat from xG/xA • availability from minutes/start-prob • defensive points from DEFCON • context from fixtures/form/EO); pick ~one representative per bucket; combine by inverse-variance-weighted linear pool (or plain median of point projections); recalibrate the pooled probability on held-out gameweeks.

---

### 3. Calibration & backtesting — key recommendation: score the *combined* projection with strictly-proper rules (Brier / log loss) + reliability diagrams for probabilities, and rank-correlation (Spearman) of projected vs actual points; run a lightweight rolling-origin backtest that fits Pi constraints; calibrate probabilities to the closing line.

- **Brier score** = mean squared error of probability forecasts (0=perfect); **log loss** = negative log-prob, which punishes confident-and-wrong far harder (90% and wrong ≫ 60% and wrong). Both are **strictly proper scoring rules — they can't be gamed and reward honest probabilities** ([MetricGate: Brier vs Log Loss vs Calibration](https://metricgate.com/blogs/brier-score-vs-log-loss-vs-calibration/); [scikit-learn calibration docs](https://scikit-learn.org/stable/modules/calibration.html)).
- **Murphy decomposition** splits Brier into *reliability (calibration)* + *resolution* + *uncertainty* — lets you see whether error is miscalibration vs lack of discrimination ([Brier score topic, EmergentMind](https://www.emergentmind.com/topics/brier-score)). Reliability = mean squared gap between forecast prob and observed frequency per bin.
- **Reliability diagram / calibration curve:** plot mean predicted prob vs observed frequency; perfect = 45° diagonal; below diagonal = overconfident, above = underconfident ([Towards Data Science: Model Calibration visual guide](https://towardsdatascience.com/model-calibration-explained-a-visual-guide-with-code-examples-for-beginners-55f368bafe72/)). Fix miscalibration cheaply with **isotonic regression or Platt scaling** on held-out data ([scikit-learn](https://scikit-learn.org/stable/modules/calibration.html); [trainindata calibration](https://www.blog.trainindata.com/probability-calibration-in-machine-learning/)).
- For **points projections** (not probabilities) validate with RMSE/MAE like OpenFPL, but the decision-relevant metric is **rank correlation** of projected vs actual — you care about ordering players, not absolute xPts. OpenFPL stratifies by return tier (Zeros / Blanks ≤2 / Tickers 3–4 / Haulers ≥5) because getting *haulers* right drives rank gains — validate per tier, not just aggregate ([OpenFPL arXiv](https://arxiv.org/html/2508.09992v1)).
- **Calibrate to the closing line:** liquid markets aggregate distributed information; consistently beating the close is the leading indicator of edge, so use CLV as an out-of-sample validation of your combined probabilities and require **rolling windows of ≥250–1000 observations** before trusting a verdict — "< 500 bets" is flagged as a too-small sample ([sports-ai.dev CLV](https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance)).
- **Lightweight Pi backtest design:** rolling-origin / walk-forward — train on GWs 1..t, predict t+1, slide forward; never evaluate in-sample (this is the standard forecast-combination validation, "rolling-origin out-of-sample evaluation," and it also protects against the overfitting that sinks learned weights) ([Forecast Combination, WFM Labs](https://wiki.wfmlabs.org/wiki/Forecast_Combination)). Store per-GW: projected prob/points, actual, and Brier/log-loss so a calibration curve can be regenerated cheaply.

**How to apply:** Log every projection with its outcome; weekly, compute Brier + log loss + a reliability curve for probabilities and Spearman rank-corr (overall and haulers-only) for points; refit an isotonic calibrator on the rolling history; track CLV vs closing odds as the honesty check.

---

### 4. Hierarchical / gated decision structure — key recommendation: minutes is a **hard gate** applied *before* any EV; use a **class-player Bayesian prior shrunk by sample size**; arbitrate conflicts by gate-then-score, with the shrunk prior breaking ties under thin evidence.

- **Minutes-first gating is consensus FPL practice, and it is a gate not a factor.** "Appearance minutes are the foundation of FPL performance, and avoiding players with minutes risk is crucial"; models compute P(play ≥1 min) and P(≥60 min) and cap non-GK start probability (most models give no outfielder >90%) ([FPL Copilot xPts explained](https://fplcopilot.com/blog/expected-points-explained); [Fantasy Football Pundit predictor](https://www.fantasyfootballpundit.com/fpl-points-predictor/)). OpenFPL's weakness on low-return players is directly attributed to lacking expected-minutes data — evidence that minutes dominate ([OpenFPL arXiv](https://arxiv.org/html/2508.09992v1)). **Practical rule: multiply EV by P(start); below a start-prob threshold, drop the player from consideration regardless of how good the EV looks.**
- **Class-player prior via shrinkage (established statistics):** the **James–Stein / empirical-Bayes** result — shrink each player's noisy in-season estimate toward the group/positional mean, with shrinkage strength inversely proportional to that player's sample size. This provably lowers MSE, most so in "smaller data realms" ([Efron & Morris / CASI ch.7](https://efron.ckirby.su.domains/other/CASI_Chap7_Nov2014.pdf); [Stein's paradox & empirical Bayes, Rochford](https://austinrochford.com/posts/2013-11-30-steins-paradox-and-empirical-bayes.html)). Applied to player ratings this cut prediction error **13.8–17.2% in MSE vs MLE in data-limited settings** ([Empirical Bayes shrinkage for pairwise comparison, arXiv](https://arxiv.org/pdf/1807.09236)). So a "class player" gets a strong prior (his multi-season baseline) that early-season noise only slowly overrides — exactly the desired behaviour after a 2-game cold snap.
- **Bayesian FPL precedent:** modeling FPL as Bayesian point-prediction + optimization has reached ~top-1% of 2.5M managers ([Bayesian RL FPL summary](https://fplcopilot.com/blog/expected-points-explained)); Bayesian priors updated by in-season data are the standard structure for "player scoring ability" ([Bayesian high-return-player model, RPubs](https://rstudio-pubs-static.s3.amazonaws.com/382023_8f9dd445a5d342659a523f54e594678b.html)); Bayes-xG shows hierarchical player/position correction of xG is a validated technique ([Bayes-xG, PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11214280/)).
- **Arbitrating "great fixture but rotation risk":** structure as a gate cascade — (1) availability gate (start prob) can veto outright; (2) if it passes but is marginal, the shrunk class-player prior and inverse-variance weighting decide how much the great fixture is discounted; (3) EO/rank context (Topic 5/6) sets the risk appetite. This mirrors the six-step FPL captaincy framework: shortlist by xPts → EO → rank situation → fixture quality via xGA (not just FDR) → rotation-risk adjustment → independent vice-captain ([FPL Oracle captaincy framework](https://fploracle.team/blog/fpl-captaincy-strategy)).

**How to apply:** EV_final = P(start) × recalibrated_EV, then hard-drop below a start-prob floor; compute per-player EV as a shrinkage blend of class-player prior and in-season signal (weight on prior ∝ 1/√games_played); on conflict, gate first, then let the shrunk prior break ties.

---

### 5. Handling uncertainty & documenting decisions — key recommendation: attach an explicit confidence to every pick, allow an explicit **"defer / wait for team news"** state, and write a structured, timestamped rationale record (this satisfies the project's #25 decision-log requirement).

- Confidence should be **information-driven**: pre-lineup, availability is the biggest unknown, so many decisions should legitimately resolve to **defer until team news / press conferences**, because start-probability is the gate and it sharpens hours before deadline ([FPL Copilot: start % is for the upcoming GW only](https://fplcopilot.com/blog/expected-points-explained); models "allow overriding projected minutes when news breaks" for a fast edge ([Fantasy Football Pundit](https://www.fantasyfootballpundit.com/fpl-points-predictor/))). Encode "defer" as a first-class output, not a failure.
- A defensible decision record, per AI-audit standards, should capture **timestamp, decision type, inputs, the reasoning trace, which factors fired and how they were weighted, confidence scores, sources/provenance, actor/version, and outcome** — captured *as it happens*, not reconstructed later ([Streamkap: Decision Traces for AI agents](https://streamkap.com/resources-and-guides/decision-traces-ai-agents); [FINOS AI governance: agent decision audit & explainability](https://air-governance-framework.finos.org/mitigations/mi-21_agent-decision-audit-and-explainability.html)). The record should keep "rationale, sources, actor identity, and supporting material attached" with supersession history ([DecisionLog](https://www.decisionlog.ai/)).
- Why this matters beyond compliance: capturing inputs + weights + outcome is exactly the substrate you need to *learn weights post-hoc* (Topic 6) and to run the calibration backtest (Topic 3) — the log is not overhead, it's the training set.

**How to apply:** For every pick emit a decision record (template below) including a confidence tier and an explicit defer flag; if any high-weight signal is "unknown pending team news," default to defer and set a re-evaluation time before deadline.

---

### 6. Weighting philosophy — key recommendation: use **fixed near-equal (or inverse-variance) weights as the default**, add a thin *judgment/context* override layer that is logged and bounded, and only "learn" weights slowly and post-hoc from the decision log — do **not** trust learned optimal weights on small samples.

- **The forecast-combination puzzle (established, robust across 50+ years of competitions):** "a simple average of forecasts using equal weights often out-performs more sophisticated combinations based on estimated optimal weights" — because estimated weights carry estimation noise and overfit, especially with few data points ([Stock & Watson via Solving the Forecast Combination Puzzle, arXiv 2308.05263](https://arxiv.org/pdf/2308.05263); [Forecast combinations: a 50-year review, Wang & Hyndman, arXiv 2205.04216](https://arxiv.org/pdf/2205.04216)). This is the single most important result for the gaffer: **on one FPL season's data, a learned weight table will likely lose to equal/near-equal weights.**
- **When simple average is provably preferable:** many forecasts to combine, limited training data, high estimation error in optimal weights, and high correlation between forecast errors — all four describe FPL ([When to choose the simple average, ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0148296316303952); [Claeskens et al., simple theoretical explanation of the puzzle](https://forecasters.org/wp-content/uploads/gravity_forms/7-2a51b93047891f1ec3608bdbd77ca58d/2014/07/Vasnev_Andrey_ISF2014.pdf)).
- **The case for a judgment/agent-in-the-loop layer over a rigid table:** rigid weights can't encode context (rank situation, chip active, "the model can't see the leaked lineup"). FPL EO practice is inherently context-dependent — the same EV pick is right or wrong depending on rank (protect vs climb) and EO band (contrarian <40%, mixed 40–70%, rank-neutral >70%) ([FPL Oracle: effective ownership](https://fploracle.team/blog/effective-ownership-fpl); [template vs differential EO math](https://fploracle.team/blog/template-vs-differential-fpl)). So: fixed weights compute a base score, a bounded judgment layer adjusts for context, and the adjustment is *logged with its reason*.
- **Make judgment auditable/learnable:** capture the reasoning trace, which factors fired, confidence, and how competing factors were weighted, as it occurs ([Streamkap decision traces](https://streamkap.com/resources-and-guides/decision-traces-ai-agents); [FINOS explainability](https://air-governance-framework.finos.org/mitigations/mi-21_agent-decision-audit-and-explainability.html)). Then post-hoc, mine the log: were overrides right? This is how you *earn* the right to move weights — slowly, evidenced, not by fitting optimal weights to a short series (which the puzzle warns against). Inverse-variance is the one "learned" adjustment that's safe because it needs only per-signal error variance, not a full weight vector ([inverse-variance weighting](https://en.wikipedia.org/wiki/Inverse-variance_weighting)).

**How to apply:** Ship fixed near-equal (or inverse-variance) base weights; allow a bounded, logged judgment override for context (rank/EO/chip/late news); review overrides monthly against outcomes and only then nudge weights — never auto-fit optimal weights on <2 seasons.

---

## Decision-log template (gaffer fills one per pick)

```
DECISION: [transfer in X / captain Y / bench Z / HOLD / DEFER]
timestamp:            2026-08-16T10:42Z    (deadline: 2026-08-16T18:00Z)
gameweek / horizon:   GW3, 1-GW
model_version:        gaffer-v0.3 / weights-fixed-equal

--- SIGNALS (bucket → value → weight → note) ---
market (de-vigged):   CS 42%, win 61%     w=.30  prior; not adjusted
xG/xA (player):       0.48 xGI/90         w=.20  independent of odds
minutes/start-prob:   0.85  [GATE]        gate=PASS (floor .60)
DEFCON hit-rate:      1.1/gm (12-gm samp) w=.10  inverse-var downweighted (small n)
fixture (xGA-based):  opp 1.2 xGA         w=.15  redundant w/ odds → capped
form:                 collapsed into xG bucket (avoid double-count)
effective ownership:  38% (contrarian)    context, not EV
class-player prior:   strong (3-season)   shrinkage weight ∝ 1/√games

--- SYNTHESIS ---
combined_prob (pre-cal):   0.55
recalibrated_prob:         0.51   (isotonic on rolling GWs)
EV_raw:                    6.2 pts
EV_final = P(start)*EV:    5.3 pts
conflict?                  great fixture vs mild rotation risk → gate PASS,
                           prior + inv-var kept discount small
judgment override:         none  (or: "+0.4 for leaked lineup, reason logged")

--- OUTPUT ---
decision:                  CAPTAIN Y
confidence:                MEDIUM  (availability the main unknown)
defer_flag:                NO   (re-check presser 16:00 if start-prob < .75)
rationale (1 line):        edge is EO asymmetry at 38% + fixture; minutes safe
sources:                   [odds feed], [xG source], [minutes source]

--- OUTCOME (filled after GW) ---
actual_points:  __   brier_contrib: __   beat_closing_line: __   override_correct: __
```

---

## Sources

- Ranjan & Gneiting, *Combining Probability Forecasts*, JRSS-B 2010 — https://academic.oup.com/jrsssb/article/72/1/71/7076442 (and tech report https://www.stat.washington.edu/research/reports/2008/tr543.pdf)
- Heskes, *Selecting Weighting Factors in Logarithmic Opinion Pools*, NeurIPS 1997 — https://proceedings.neurips.cc/paper/1997/file/59f51fd6937412b7e56ded1ea2470c25-Paper.pdf
- *Choosing weights for logarithmic pooling* — https://www.researchgate.net/publication/272422988_Choosing_the_weights_for_the_logarithmic_pooling_of_probability_distributions
- *Sample Complexity of Forecast Aggregation*, arXiv — https://arxiv.org/pdf/2207.13126
- Inverse-variance weighting — https://en.wikipedia.org/wiki/Inverse-variance_weighting
- OpenFPL, arXiv 2508.09992 — https://arxiv.org/html/2508.09992v1 ; code https://github.com/daniegr/OpenFPL
- Solving the Forecast Combination Puzzle, arXiv 2308.05263 — https://arxiv.org/pdf/2308.05263
- Wang & Hyndman, *Forecast combinations: a 50-year review*, arXiv 2205.04216 — https://arxiv.org/pdf/2205.04216
- *When to choose the simple average in forecast combination* — https://www.sciencedirect.com/science/article/abs/pii/S0148296316303952
- Claeskens et al., *A simple theoretical explanation of the forecast combination puzzle* — https://forecasters.org/wp-content/uploads/gravity_forms/7-2a51b93047891f1ec3608bdbd77ca58d/2014/07/Vasnev_Andrey_ISF2014.pdf
- Brier vs Log Loss vs Calibration (MetricGate) — https://metricgate.com/blogs/brier-score-vs-log-loss-vs-calibration/
- scikit-learn probability calibration — https://scikit-learn.org/stable/modules/calibration.html
- Model Calibration visual guide (TDS) — https://towardsdatascience.com/model-calibration-explained-a-visual-guide-with-code-examples-for-beginners-55f368bafe72/
- Brier score topic (EmergentMind, Murphy decomposition) — https://www.emergentmind.com/topics/brier-score
- Forecast Combination (WFM Labs, rolling-origin) — https://wiki.wfmlabs.org/wiki/Forecast_Combination
- Closing Line Value & AI model performance (sports-ai.dev) — https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance
- PropsBot CLV glossary (Brier vs Vegas) — https://propsbot.ai/glossary/closing-line-value/
- Betting market efficiency in binary choice models (Springer) — https://link.springer.com/article/10.1007/s10479-022-04722-3
- Wilkens, *Can simple models predict football and beat the odds?* (SAGE 2026) — https://journals.sagepub.com/doi/10.1177/22150218261416681
- Market-calibrated AFT in-play model, arXiv — https://arxiv.org/pdf/2605.16066
- Efron & Morris / CASI ch.7 (James–Stein, ridge) — https://efron.ckirby.su.domains/other/CASI_Chap7_Nov2014.pdf
- Stein's paradox & empirical Bayes (Rochford) — https://austinrochford.com/posts/2013-11-30-steins-paradox-and-empirical-bayes.html
- Empirical Bayes shrinkage for pairwise comparison (13.8–17.2% MSE gain), arXiv — https://arxiv.org/pdf/1807.09236
- Bayes-xG hierarchical xG correction (PMC) — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11214280/
- FPL Copilot, xPts explained (minutes, start-prob) — https://fplcopilot.com/blog/expected-points-explained
- Fantasy Football Pundit predictor (minutes override) — https://www.fantasyfootballpundit.com/fpl-points-predictor/
- FPL Oracle: Effective Ownership — https://fploracle.team/blog/effective-ownership-fpl ; Template vs Differential — https://fploracle.team/blog/template-vs-differential-fpl ; Captaincy framework — https://fploracle.team/blog/fpl-captaincy-strategy
- Streamkap: Decision Traces for AI agents — https://streamkap.com/resources-and-guides/decision-traces-ai-agents
- FINOS AI governance: agent decision audit & explainability — https://air-governance-framework.finos.org/mitigations/mi-21_agent-decision-audit-and-explainability.html
- DecisionLog (rationale + provenance + supersession) — https://www.decisionlog.ai/
