# Method — signal synthesis (how the axes combine)

How the gaffer **combines** the many axes into one decision and **reconciles** them
when they conflict — the arbitration layer sitting over every factor page. Grounded
in forecast-combination and calibration literature (established statistics), not FPL
folklore. Full evidence: [../raw/followup-signal-synthesis.md](../raw/followup-signal-synthesis.md).

**Headline:** this is a forecast-combination + calibration problem with a robust,
boring answer — *simple/near-equal weighting of a few de-correlated signals, wrapped
in a hard minutes gate, then calibrated against reality.* Fancy learned weights lose
out-of-sample on the small samples a Pi + one FPL season always has.

---

## The gate-then-pool structure

1. **Minutes is a hard GATE, not a signal.** Compute `EV_final = P(start) ×
   recalibrated_EV`; below a start-prob floor, drop the player regardless of EV.
   **[standard → use]** — consensus practice; OpenFPL's weakness traces to missing
   expected-minutes.
2. **Bucket correlated signals, combine one per bucket.** The central hazard is
   **double-counting**: odds already encode xG + home/away + fixtures; form ≈ xG. Group
   into near-independent buckets — {result/CS from de-vigged odds} · {player threat from
   xG/xA} · {availability} · {DEFCON} · {context: fixture/form/EO} — and take one
   representative each. **[standard]** ([Sample Complexity of Forecast Aggregation](https://arxiv.org/pdf/2207.13126)).
3. **Combine by near-equal / inverse-variance LINEAR pooling.** Linear (weighted
   arithmetic mean) suits *redundant* information — which most FPL signals are; reserve
   log/geometric pooling for genuinely independent sources. Inverse-variance weighting
   (weight ∝ 1/variance) is the one safe "learned" adjustment — it down-weights a noisy
   signal (small-sample DEFCON) without a full weight vector. For point projections, take
   a **median across an ensemble** (OpenFPL's production choice). **[standard → use]**
   ([Ranjan & Gneiting, JRSS-B 2010](https://academic.oup.com/jrsssb/article/72/1/71/7076442);
   [inverse-variance weighting](https://en.wikipedia.org/wiki/Inverse-variance_weighting)).
4. **Recalibrate the pooled output.** Counter-intuitive but proven: any non-trivial
   average of *calibrated* forecasts is itself *uncalibrated* — so apply isotonic/Platt on
   rolling held-out GWs before the number drives a decision. **[standard → use]**.
5. **Break ties with the [class-player prior](../class-player-prior.md)** (James–Stein
   shrinkage, weight on prior ∝ 1/√games) when recent evidence is thin.

---

## Market-vs-model blending

**Suggested: treat the de-vigged closing line as a strong prior your model must *beat*,
not echo; blend the model as a *bounded adjustment*; validate by Closing Line Value.**

- The closing line is the most efficient public price; consistently beating it (positive
  CLV) is the strongest leading indicator of edge, better than short-run results
  ([sports-ai.dev](https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance)).
  A model earns an override only when it is **better-calibrated** than the market
  (existence proof: Brier 0.190 vs 0.195).
- **Method:** give the de-vigged market probability the majority prior weight (~60–80%);
  let the model move it only within a **capped band** (e.g. ±20% relative) where a logged,
  backtested reason exists — the market already prices team result/home-away/fixture, so
  the model's marginal value is the **player-level** stuff (minutes, DEFCON, usage) odds
  don't isolate. Log pre- and post-adjustment numbers and whether you beat the close.

Evidence tier: **[standard/tier-1]**.

---

## Calibration & backtesting (Pi-lightweight)

- **Score probabilities** with strictly-proper rules — **Brier** + **log loss** (punishes
  confident-and-wrong) — plus **reliability diagrams** (predicted vs observed frequency;
  45° = calibrated). Murphy-decompose Brier into reliability + resolution + uncertainty.
  Fix miscalibration with isotonic/Platt on held-out data.
- **Score points projections** with RMSE/MAE but weight the decision-relevant metric:
  **Spearman rank-correlation** of projected vs actual, **stratified by return tier**
  (Zeros / Blanks ≤2 / Tickers 3–4 / **Haulers ≥5**) — getting haulers right drives rank.
- **Backtest by rolling-origin / walk-forward** (train GWs 1..t, predict t+1, slide) —
  never in-sample; this is also what protects against the overfitting that sinks learned
  weights. Store per-GW: projected prob/points, actual, Brier/log-loss, and CLV vs the
  close as the honesty check. Require ≥250–1000 obs before trusting a verdict.
- All **[standard → use]** (scikit-learn calibration; forecast-combination literature).

---

## Weighting philosophy — do NOT learn "optimal" weights

- **The forecast-combination puzzle** (robust across 50+ years): a simple average with
  equal weights routinely beats estimated-optimal weights out-of-sample — worst exactly
  under FPL's conditions (many signals, little data, high estimation error, correlated
  errors) ([Solving the Forecast Combination Puzzle, arXiv 2308.05263](https://arxiv.org/pdf/2308.05263);
  [Wang & Hyndman 50-year review](https://arxiv.org/pdf/2205.04216)). **On one FPL season,
  a learned weight table will likely lose to near-equal weights.**
- **So:** ship **fixed near-equal (or inverse-variance) base weights**; add a thin,
  **bounded, logged judgment override** for context (rank/EO band, chip active, "model
  can't see the leaked lineup"); review overrides monthly against outcomes and only *then*
  nudge weights — never auto-fit on <2 seasons. This is the statistical backbone for the
  project's "gaffer judgment over a fixed weight table" stance
  ([../../../gw1/approach.md](../../../gw1/approach.md)) — judgment, but **auditable and
  bounded**, not a free hand.

---

## Decision-log template (satisfies the #25 decision-log requirement)

Emit one record per pick — the log is not overhead, it's the training set for
post-hoc weight learning and the calibration backtest. Capture, *as it happens*:
timestamp, decision type, inputs (per bucket: value, weight, note), the minutes gate
result, combined + recalibrated numbers, `EV_final`, any conflict and how it resolved,
judgment override + reason, **confidence tier**, an explicit **defer / wait-for-team-news
flag** with a re-check time, one-line rationale, sources, and (filled after the GW)
outcome + whether the override was right.

```
DECISION: [transfer in X / captain Y / bench Z / HOLD / DEFER]
timestamp / deadline / gameweek / model_version
--- SIGNALS (bucket → value → weight → note) ---
market (de-vigged) · xG/xA · minutes[GATE] · DEFCON · fixture · form(→xG bucket) · EO · class-prior
--- SYNTHESIS ---  combined_prob → recalibrated → EV_raw → EV_final=P(start)·EV ; conflict? ; override?
--- OUTPUT ---     decision · confidence · defer_flag(+recheck time) · rationale · sources
--- OUTCOME ---    actual_points · brier_contrib · beat_closing_line · override_correct
```

Full worked example: [../raw/followup-signal-synthesis.md](../raw/followup-signal-synthesis.md)
(§ Decision-log template). Decision-audit standard: capture reasoning trace, factors
fired, confidence, provenance as it happens
([FINOS explainability](https://air-governance-framework.finos.org/mitigations/mi-21_agent-decision-audit-and-explainability.html)).
