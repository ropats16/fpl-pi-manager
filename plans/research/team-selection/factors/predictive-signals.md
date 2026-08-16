# Factors — core predictive signals

The player-level signals that estimate expected returns. Full evidence:
[../raw/cluster-A-signals.md](../raw/cluster-A-signals.md),
[../raw/discovery-quant.md](../raw/discovery-quant.md),
[../raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md).
Weights are suggested; see [../importance-ranking.md](../importance-ranking.md).

---

## Minutes / xMins

**Suggested weight: the GATE (applied before all EV).**

The foundational multiplier — no minutes, no returns. Everything else multiplies
through it.

- **Method:** model via the **60-minute scoring kink**, not a linear minutes
  fraction. A player earns 1 appearance point <60 min, 2 at 60+, and clean-sheet
  points (DEF/GK) need 60+. So `EV = P(start) × P(60+ | start) × conditional EV`,
  and CS-dependent EV collapses sharply below ~60 projected minutes
  ([FPL Review xMins docs](https://docs.fplreview.com/the-model/projections/xmins/)).
- **Hard gate:** below a start-probability floor, drop the player regardless of how
  good the EV looks. OpenFPL's largest error is concentrated on non-playing players
  ("Zeros", 15% worse RMSE) — evidence that predicting *who doesn't start* is one of
  the biggest remaining edges ([OpenFPL, arXiv 2508.09992](https://arxiv.org/html/2508.09992v1)).
- **Where the number comes from:** FPL API `status` + `chance_of_playing`, rolling
  minutes (nailedness), and predicted-XI consensus — see
  [data-sources › player availability](../sources/data-sources.md#player-availability-the-highest-leverage-deadline-pull)
  for the concrete `P(start) × E(min)` recipe and the deadline-timing constraint.

Evidence tier: **[proven]** — universal across serious models.

---

## Betting odds

**Suggested weight: HIGH for the short horizon (next 1–2 GWs) — the best-calibrated
external signal available.**

- **Method:** de-vig, then use fair probabilities directly. Raw implied prob =
  `1/decimal_odds`; the booked sum exceeds 1 (PL overround ~3–6%). Strip it:
  **multiplicative** normalization for balanced 1X2; **Shin or power** for skewed
  markets (anytime-scorer, clean-sheet) where favourite-longshot bias matters
  ([Pinnacle overround](https://www.pinnacleoddsdropper.com/blog/overround)). Use CS
  odds for DEF/GK CS-EV, anytime-scorer for attacker goal-EV. See
  [../sources/data-sources.md#odds--probability-removing-the-vig](../sources/data-sources.md#odds--probability-removing-the-vig).
- **Treat the closing line as the prior your model must beat, not echo.** Odds are
  well-calibrated and improving; models that beat them capture only residual signal
  ([Wilkens, SAGE 2026](https://journals.sagepub.com/doi/10.1177/22150218261416681)).
  The market already prices team result / home-away / fixture, so your model's
  marginal value is the **player-level** stuff odds don't isolate — and player-prop
  markets are the softest, most-beatable, especially early season
  ([raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md)).
- Blending mechanics (weight the market prior, adjust within a bounded band, validate
  by CLV): [../methods/signal-synthesis.md#market-vs-model-blending](../methods/signal-synthesis.md#market-vs-model-blending).

Evidence tier: **[tier-1]** — academic + betting literature.

---

## xG / xA

**Suggested weight: HIGH for underlying-talent estimation; MED as a direct
short-term predictor (sample-size sensitive).**

- **Method:** use per-90 xG/xA (Understat/FBref) as the finishing/creation estimator
  feeding goal & assist EV, in preference to raw past FPL points — xG is stabler and
  more predictive of future returns than past goals
  ([ElHabr](https://tonyelhabr.rbind.io/posts/xg-predictor-future-results/)).
- **Shrink low-sample values** toward the multi-season baseline before use — early-
  season per-90 off 2–4 games is noisy. This is where the
  [class-player prior](../class-player-prior.md) does its work.
- **Usage, not just rate:** prefer the player who takes a large **share** of his
  team's shots/xG/box-touches, not merely a high per-90 — see
  [fixtures-and-context.md#team-style--usage-share](fixtures-and-context.md#team-style--usage-share).
- **xA source (sustainability haircut):** open-play xA is more robust than set-play
  xA (which depends on a corner/FK role that can change) — keep open-play at full
  weight, discount set-play by taker-role security. A refinement on the axis, not a
  new axis.
- Don't over-engineer gamestate filters — subsetting xG to "neutral gamestate"
  doesn't improve prediction ([ElHabr](https://tonyelhabr.rbind.io/posts/xg-predictor-future-results/)).

Evidence tier: **[tier-1]**.

---

## Form recency

**Suggested weight: MED — real but easily overweighted; a tilt on the underlying
estimate, not the estimate itself.**

- **Method:** apply a **mild geometric decay over the last ~4–6 games to *underlying*
  metrics** (xG/xA, minutes, role) — never to raw points — and always regress toward
  the season/multi-season mean. A validated gradient scheme (1.5×→0.6×) reported ~31%
  better predictive power than flat averages
  ([FormBaller](https://www.formballer.com/methodology)).
- **Anti-folklore:** "hot streaks" are largely recency bias and regress hard; FPL's
  raw "Form" stat (points over 30 days) is especially noisy
  ([Harvard Sports Analysis](https://harvardsportsanalysis.org/2015/08/team-form-recency-bias-and-regression-to-the-mean/)).
  Recent *underlying* numbers carry signal; recent *points* mostly don't.
- Multi-horizon features (average each base metric over 1/3/5/10/38-match windows)
  are how OpenFPL separates short-term form from long-term baseline — a directly
  borrowable feature-engineering trick ([../methods/reference-pipelines.md](../methods/reference-pipelines.md)).

Evidence tier: **[tier-1]**.

---

## Pre-season friendlies

**Suggested weight: LOW for output; MED-HIGH only for the minutes/role/set-piece
signal.**

- **Attacking output in friendlies is noise.** Direct 2025/26 analysis: pre-season
  goals barely correlate with league returns (Watkins hot then dry; Semenyo quiet
  then 17 goals). Team-level pre-season results scatter across the table
  ([Fantasy Football Scout](https://www.fantasyfootballscout.co.uk/2026/08/09/does-pre-season-form-count-for-anything)).
- **What carries signal:** minutes, formation, set-piece/penalty duty, new-signing
  integration and fitness — especially in the *final* friendlies and official
  fixtures. "Pre-season minutes in the final kickabouts are usually a good way of
  predicting Gameweek-1 line-ups."
- **Method:** use friendlies **only** to inform minutes/role inputs; explicitly
  ignore friendly goal/assist tallies as x̄ in any projection. Never downgrade a
  proven player for a quiet friendly — the [class-player prior](../class-player-prior.md)
  enforces this automatically.

Evidence tier: **[tier-1]** (domain-specific).

---

## Finishing over/under-performance

**Suggested weight: MED — a *fade* signal / prior toward xG, not a positive driver.**

- **Method:** rank on xG/xA, not actual goals. Treat a hot player whose **goals ≫ xG**
  as a sell/avoid (regression coming); **goals ≪ xG** as a buy (positive regression).
  Shrink single-season finishing toward the mean.
- **Why:** finishing overperformance (goals − xG) does **not** persist year-to-year;
  detecting real finishing skill needs "a few hundred shots," and almost no single
  season is a large enough sample
  ([KU Leuven DTAI](https://dtai.cs.kuleuven.be/sports/blog/biases-in-expected-goals-models-confound-finishing-ability/);
  [StatsBomb](https://blogarchive.statsbomb.com/articles/soccer/quantifying-finishing-skill/);
  [American Soccer Analysis](https://www.americansocceranalysis.com/home/2023/8/28/the-replication-project-measuring-shooting-overperformance)).
- **But keep a whitelist** of multi-season proven outperformers (Son/Kane-tier) whose
  baseline is legitimately above xG — xG models are themselves biased in ways that
  confound finishing, so "sell all overperformers" is wrong
  ([arXiv 2401.09940](https://arxiv.org/pdf/2401.09940)). Distinct from the
  [class-player prior](../class-player-prior.md): that's about *output in a role*,
  this is specifically about *finishing above xG*.

Evidence tier: **[tier-1]**.

---

See also: [class-player-prior.md](../class-player-prior.md) (the stabilising prior
that shrinks every rate above by sample size).
