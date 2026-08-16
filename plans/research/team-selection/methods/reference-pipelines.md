# Method — reference pipelines to adopt

Open / documented end-to-end FPL pipelines whose methods we can **reuse instead of
inventing**. The evidence gate applies (per Rohit): **adopt wholesale only what has
documented, verifiable results** — everything else is a candidate to evaluate in our
own backtest. Full evidence: [../raw/followup-reference-pipelines.md](../raw/followup-reference-pipelines.md).

Our current pipeline: collector → projections → PuLP/ILP optimiser. The layers below
map onto it.

---

## Projection layer → OpenFPL  **[proven → adopt]**

- **Access:** paper [arXiv 2508.09992](https://arxiv.org/abs/2508.09992), code
  [github.com/daniegr/OpenFPL](https://github.com/daniegr/OpenFPL) (MIT).
- **Documented result (why it clears the gate):** using **public data only**, it rivals
  the commercial FPL Review and **beats it on high-return players ("Haulers", >2 pts)**
  across 1/2/3-GW horizons (Hauler 1-GW RMSE 5.142 vs 5.172), tested prospectively on
  2024/25.
- **Method (concrete, borrowable):** one ensemble regressor **per position**; **196
  features** averaged over **1/3/5/10/38-match windows** (player/team/opponent families);
  ensemble = **median of 50 models** (XGBoost + Random Forest, K-Best over 5 CV folds);
  **direct point regression** (not a goals/assists/CS sub-model stack); **FPL-API
  categorical availability tags (0/25/50/75/100%)** in place of a proprietary xMins model.
- **Pi note:** inference is light (load pre-trained models); the 50-model training is the
  only heavy step — do it **off-Pi** and ship artifacts.
- **Borrow:** the whole projection layer + evaluate ourselves on **hauler-recall**, not
  just RMSE.

---

## Optimizer layer → open-fpl-solver (ex sertalpbilal)  **[proven → adopt]**

- **Access:** [github.com/solioanalytics/open-fpl-solver](https://github.com/solioanalytics/open-fpl-solver)
  (Apache-2.0); the solver many top managers use — public track record.
- **Method (extracted from `dev/solver.py`):** multi-period MILP on **HiGHS/highspy**;
  objective = decay-weighted + captain-doubled + bench-weighted + vice fallback, with −4
  hits, FT accumulation (cap 5) and the four chips as mutually-exclusive toggles. The
  concrete parameters (decay base, bench-weight vector, vice/FT values) are stated once in
  [squad-construction.md#optimizer-objective--constraints](squad-construction.md#optimizer-objective--constraints)
  — not repeated here.
- **Pi note:** HiGHS is a fast open MILP solver on ARM — lighter than commercial engines;
  switch our PuLP+CBC to HiGHS if CBC proves slow.
- **Borrow:** the concrete objective parameters and transfer/chip economics.

---

## Fixture / clean-sheet layer

**penaltyblog (Dixon-Coles) — [standard → use].**

- **Access:** [github.com/martineastwood/penaltyblog](https://github.com/martineastwood/penaltyblog)
  (MIT), `pip install penaltyblog`.
- **Method:** production time-weighted **Dixon-Coles** (ξ≈0.0065) with low-score
  correction; `goal_expectancy()` infers implied goal expectancies + rho **directly from
  bookmaker 1X2 + O/U** odds → scoreline matrix → **clean-sheet & goals-conceded**
  probabilities to condition GK/DEF projections. Dixon-Coles is the established standard
  method (1997), so **[standard → use]** even though penaltyblog itself isn't
  FPL-benchmarked.
- **Pi note:** Cython, small, fast on ARM — ideal fixture-layer library.

---

## Baseline / sanity layer → recency-weighted / ARIMA  **[proven → adopt as baseline]**

- **Access:** Ramezani & Dinh, [arXiv 2505.02170](https://arxiv.org/abs/2505.02170)
  (paper only). Clean citable MILP objective `Σ c_j(x_j+y_j)` (captain doubling) + split
  XI/bench budgets.
- **Documented result:** across an estimator bake-off, a **recency-weighted / ARIMA(1,0,0)
  rolling-window** per-player points estimate with a constrained XI budget was best —
  beats a flat average. Robust/box-uncertainty optimisation was marginal → deprioritise.
- **Borrow:** use as a cheap, **leak-free baseline** to validate the ML projection against.

---

## Data — vaastav historical repo

**[standard → use, with caveat].**

- **Access:** [github.com/vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League)
  — the de-facto historical dataset (per-player per-GW CSVs).
- **Caveat (documented):** the `xP`/`ep_this` column is scraped **after** the GW and can
  contain post-deadline info — **unsafe as a leak-free label**. Build our own labels from
  realized points.

---

## Do NOT adopt

- **FPL Review "Massive Data" internals — [proprietary, do not adopt].** The model is
  undocumented; only the **output contract** (per-player per-GW xPts + editable xMins,
  ~6–14 GW horizon) and the design principle ("xMins gates xPts; odds drive goals") are
  borrowable. No published method → fails the gate.
- **Robust / box-uncertainty optimisation** — marginal gains reported (arXiv 2505.02170).
- **Bespoke goals/assists/CS point-decomposition** — OpenFPL shows direct point
  regression is competitive and simpler.

---

## Recommended stack (all Pi-viable at inference)

| Layer | Adopt | Gate |
|---|---|---|
| Projection | OpenFPL (position ensembles, multi-window features, median-of-N, API availability tags) | [proven] |
| Fixture/CS | penaltyblog time-weighted Dixon-Coles from odds | [standard] |
| Optimizer | open-fpl-solver multi-period MILP ([params in squad-construction](squad-construction.md#optimizer-objective--constraints)); HiGHS if CBC slow | [proven] |
| Baseline | recency-weighted / ARIMA points estimate | [proven] |
| Data | vaastav history (leak-safe labels) + live FPL/Understat APIs | [standard] |

Sequence: odds/xG → fixture strength → **minutes gate** → per-player xPts → MILP
objective coefficients → captain/bench falls out of the same MILP.
