# FPL Modeling Pipelines — Reference Methods to Adopt

Research date: 2026-08-16. Goal: catalogue OPEN / DOCUMENTED end-to-end FPL pipelines and extract concrete, reusable methods so we adopt rather than invent. Every claim is cited. Pi-suitability is flagged per method.

Our current pipeline: collector -> projections -> PuLP/ILP optimizer. The two most directly reusable primary artifacts are **OpenFPL** (projection layer, MIT, open) and **open-fpl-solver / FPL-Optimization-Tools** (optimizer layer, Apache-2.0, open). The fixture/clean-sheet layer maps cleanly onto **Dixon-Coles via penaltyblog** (MIT).

---

### 1. OpenFPL — open paper + open repo (arXiv 2508.09992; MIT)

**Access:** Paper [arxiv.org/abs/2508.09992](https://arxiv.org/abs/2508.09992) / HTML [arxiv.org/html/2508.09992v1](https://arxiv.org/html/2508.09992v1). Code + trained models: [github.com/daniegr/OpenFPL](https://github.com/daniegr/OpenFPL) (MIT, 21 stars, Jupyter). This is the single closest match to our projection layer — a documented method that reportedly rivals FPL Review on high-return players using only public data.

**Method (concrete):**
- **One ensemble regressor per FPL position** (GK, DEF, MID, FWD, plus assistant managers). Direct regression of FPL points — NOT a decomposed goals/assists/CS sub-model stack. The paper explicitly chose "direct" point regression over "an indirect approach forecasting FPL points from likelihood of rewarding events."
- **Feature set: 196 features** for outfield/GK positions, 122 for assistant managers. Three families — player-specific (Xp: FPL points, minutes, goals, assists, xG, xA), team-specific (Xt: goals scored/conceded, xG, Deep, PPDA), opponent-specific (Xo) — plus match-status (Xs).
- **Multi-horizon features:** every base feature is averaged over **five rolling windows — 1, 3, 5, 10, and 38 matches** (short-term form through full-season trend). This window-averaging is the feature-engineering trick to borrow directly.
- **Ensemble = median of 50 models.** Base learners are **XGBoost + Random Forest**. Build: K-Best Search (population K=10) per cross-validation fold over 5 folds → top-10 × 5 = 50 models; final forecast is the **median of the 50** model outputs. Hyperparameters tuned to minimize RMSE.
- **Minutes/availability:** deliberately avoids proprietary xMins. Uses the **categorical availability tags from the FPL API (0/25/50/75/100%)** as a feature (`Xs`), plus minutes history as a player feature. This is the pragmatic, public-data-only substitute for a bookmaker xMins model.
- **Training data:** FPL API + Understat, seasons 2020-21 through 2023-24; tested prospectively on 2024-25.
- **Evaluation:** RMSE / MAE, stratified into Zeros (0), Blanks (≤2), Tickers (3-4), **Haulers (≥5)**. Headline result: beats the commercial benchmark (FPL Review) for high-return players (>2 pts) across 1/2/3-GW horizons — e.g. Haulers 1-GW RMSE 5.142 vs 5.172. Hauler-recall is the metric that matters for rank gains.

**Pi suitability:** Inference is lightweight (XGBoost + RF predict, load pre-trained models, `pip install -r plug.txt`, run `play.ipynb`). Runs fine on a Pi. RE-TRAINING the 50-model K-Best search is heavier but is a one-off/off-Pi step; ship the trained models.

**Borrow:** Adopt the whole projection layer — 1/3/5/10/38-match window-averaged features, position-specific ensembles, median-of-N XGBoost+RF, and FPL-API availability tags in place of a proprietary xMins model. Evaluate ourselves on Hauler-recall, not just RMSE.

---

### 2. FPL Review "Massive Data" — proprietary model, documented interface only

**Access:** Product [fplreview.com](https://fplreview.com/access-the-massive-data-planner/); docs [docs.fplreview.com/the-model/projections/massive-data-model](https://docs.fplreview.com/the-model/projections/massive-data-model/). It is the commercial benchmark OpenFPL measures against and the CSV format most open solvers ingest.

**Method (documented surface, core is proprietary):**
- Inputs: historical performance, **market/bookmaker odds**, xG, tactical analysis, penalty-taker/rotation flags, data recency.
- **xMins:** produced as "editable expected minutes" combined with bookmaker inferences — the manager can override. Derivation algorithm is **not disclosed**.
- **xPts:** EV built from probability-weighted scoring events — goals, assists, clean sheets, cards, bonus, "all other point scoring events weighted by their respective probability." Exact probability model **not disclosed**.
- Projects **up to 14 GWs ahead**; market data/sims/projections refresh **hourly**, performance data overnight, team news validated before deadline.

**Pi suitability:** N/A (paid web service). Only the **CSV output** is consumable.

**Borrow:** Not the model (proprietary) but two things: (a) the **output contract** — a per-player, per-GW `xPts` + editable `xMins` table projecting ~6-14 GWs — is exactly the interface OpenFPL produces and the solver consumes; standardize on it. (b) The design principle: xMins is a first-class, human-overridable field feeding xPts, and odds are a strong signal for the goals/CS layer.

---

### 3a. open-fpl-solver (formerly sertalpbilal/FPL-Optimization-Tools) — open repo (Apache-2.0)

**Access:** [github.com/solioanalytics/open-fpl-solver](https://github.com/solioanalytics/open-fpl-solver) — the "solver" many top managers use (repo was transferred from `sertalpbilal/FPL-Optimization-Tools`; `daniegr` maintains a fork). Model code: `dev/solver.py` (`solve_multi_period_fpl`). Solver: **HiGHS via `highspy`** (historically CBC); data via **pandas**; deps managed with `uv`. No heavy ML — lightweight.

**Method (concrete — extracted from `dev/solver.py`):**
- **Multi-period MILP** over a horizon of gameweeks. Decision variables:
  - `squad[p,w]` (15-man roster per GW), `squad_fh[p,w]` (free-hit alternate squad)
  - `lineup[p,w]` (starting 11), `captain[p,w]`, `vicecap[p,w]`, `bench[p,w,order]` for order ∈ {0,1,2,3}
  - `transfer_in[p,w]`, `transfer_out[p,w]`, `fts[w]` free-transfer count with `fts_state` tracking
  - chips: `use_wc[w]`, `use_bb[w]`, `use_fh[w]`, `use_tc[p,w]`
- **Objective per GW:**
  `gw_xp[w] = points × (lineup + captain + 0.1·vicecap + TC + bench_weights·bench)`
  `gw_total[w] = gw_xp − 4·penalized_transfers + ft_gain − itb_penalty − opposing_play_penalty`
  - **Bench weights** `{0:0.03, 1:0.21, 2:0.06, 3:0.002}` (GK slot 0, outfield bench slots 1-3) — expected probability each bench player is needed.
  - **Vice-captain** carried at 0.1 weight (fallback EV).
  - **Time decay** objective: `Σ_w gw_total[w] · 0.84^(w − next_gw)` — future GWs discounted at 0.84/week.
- **Constraints:** `Σ squad = 15`; position quotas 2 GK / 5 DEF / 5 MID / 3 FWD; `Σ lineup = 11` (→ 15 when bench-boost active); max 3 per club; budget via `in_the_bank[w] = in_the_bank[w-1] + sales − purchases` (uses sell prices); `captain ≤ lineup`; valid formation via bench ordering; one captain / one vice.
- **Transfers:** hit = **4 pts** per transfer beyond free; FTs start at `initial_ft`, **+1 per unused week, clamped 0-5** (matches current FPL rules), reset to 1 on wildcard; `raw_gw_ft[w] = fts[w] − transfer_count[w] + 1 − use_wc[w] − use_fh[w]`. An `ft_value` (~1.5 pts) rewards banking FTs.
- **Chips (each modifies the model):** WC → transfer limit removed, FTs reset; BB → bench players score (lineup→15); FH → one-week `squad_fh`, transfers isolated, reverts after; TC → captain multiplier 3× instead of 2×. Mutual exclusivity: `use_wc + use_fh + use_bb + use_tc ≤ 1` per GW.

**Pi suitability:** Very good. HiGHS/`highspy` + pandas, no ML frameworks. HiGHS is a fast open-source MILP solver that runs on ARM. This is a lighter-weight optimizer stack than a commercial one.

**Borrow:** This is essentially the reference for our optimizer. Adopt: multi-period MILP over ~6-8 GW horizon; the **0.84^t decay**; the **bench-weight vector**; **0.1 vice weight**; the **4-pt hit / FT-accumulation (cap 5) / ~1.5 FT-value** transfer economics; and the four chips as constraint toggles. Consider **HiGHS/highspy** if PuLP+CBC proves slow on Pi.

### 3b. vaastav/Fantasy-Premier-League — canonical open data repo (1.7k stars)

**Access:** [github.com/vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League). The de-facto historical dataset.

**Method:** Scrapes FPL API into per-season `cleaned_players.csv`, per-GW `gws/gw{n}.csv`, and combined `gws/merged_gw.csv` (per-player per-GW rows). Load directly via `pd.read_csv(raw.githubusercontent.com/.../merged_gw.csv)`. **Caveat (documented):** the `xP` column comes from FPL's `ep_this`, scraped AFTER the GW — so it can contain post-deadline info and is unsafe as a leak-free feature/label. Understat merge scripts included.

**Pi suitability:** Pure data — trivially usable. Good for backfilling training history without re-scraping.

**Borrow:** Use as the historical training/backtest corpus for our projection model. Heed the `xP`/`ep_this` leakage caveat; build our own leak-free labels from realized points.

### 3c. penaltyblog — open library (MIT, 211 stars) [also covers target 5]

**Access:** [github.com/martineastwood/penaltyblog](https://github.com/martineastwood/penaltyblog), docs [penaltyblog.readthedocs.io](https://penaltyblog.readthedocs.io/), `pip install penaltyblog`.

**Method:** Production Poisson / Bivariate-Poisson / **Dixon-Coles** implementations (Cython, ~250× faster than pure Python). Includes `goal_expectancy()` / `goal_expectancy_extended()` to **infer implied goal expectancies + Dixon-Coles rho directly from bookmaker 1X2 (and O/U 2.5) probabilities** — a shortcut to team attack/defence strength from odds. Ships a `.claude/skills/penaltyblog/SKILL.md` for agents.

**Pi suitability:** Excellent — small, fast, pure-Python install (Cython wheels). Ideal fixture-layer library for a Pi.

**Borrow:** Use penaltyblog as the fixture/clean-sheet engine rather than hand-rolling Dixon-Coles. Feed odds → goal expectancies → scoreline matrix → clean-sheet & goals-conceded probabilities that condition our GK/DEF projections.

---

### 4. Ramezani & Dinh — "Data-driven framework for team selection" (arXiv 2505.02170)

**Access:** [arxiv.org/abs/2505.02170](https://arxiv.org/abs/2505.02170), HTML [arxiv.org/html/2505.02170](https://arxiv.org/html/2505.02170), also SSRN. Paper only (no repo found), but gives clean, citable MILP formulations and an estimator bake-off.

**Method (concrete):**
- **MILP objective (starting XI + captain):** `max Σ_j c_j·x_j + Σ_j c_j·y_j` — `x_j∈{0,1}` starter, `y_j∈{0,1}` captain (captain EV doubled via second term).
- **Constraints:** `Σ x_j = 11`; `Σ y_j = 1`; `y_j ≤ x_j`; budget `Σ v_j·x_j ≤ b` (they split XI budget b≈£83.5m vs bench `100−b`); formation min/max per position; `Σ_{j∈club} x_j ≤ 3`; no XI/bench duplication. (Bench solved as a secondary objective `max Σ c_j·x_j^b`.)
- **Hybrid scoring metric:** `c_HYB = (1−λ)·y_norm + λ·ŷ_norm` mixing normalized realized points with **ridge-regression** predictions (`argmin ‖y−Xw‖² + α‖w‖²`) on standardized features (ICT, xG, xA, xGI, xGC, selected%, starts). Tested λ = 1/3 and 2/3.
- **Estimator bake-off** for the points/cost input `c_j`: simple average, recency-weighted average (`w_t = t/Σi`), Holt exponential smoothing, **ARIMA(p,d,q)**, linear trend, bootstrap, Monte Carlo.
- **Result:** **ARIMA(1,0,0) rolling-window with a constrained (~£70m) XI budget was best** (704 cumulative pts, GW27-38 2023/24); recency-weighted average (635) and Monte Carlo (545) competitive. Robust/box-uncertainty and hybrid variants help some objectives but are "not uniformly superior."

**Pi suitability:** Fully lightweight — a small MILP (single-GW here) + ridge/ARIMA in statsmodels. Trivial on Pi.

**Borrow:** The captain-doubling objective term `Σ c_j(x_j + y_j)` and the split XI/bench budget are clean formulation patterns. Most actionable finding: a **recency-weighted / ARIMA time-series estimate of per-player points beats a flat average** — worth using as a baseline projection and as a sanity check on the ML model. Deprioritize robust optimization (marginal gains reported).

---

### 5. Dixon-Coles / Poisson fixture model — standard method + open implementations

**Access:** Original method Dixon & Coles (1997). Concrete Python walkthroughs: dashee87 [predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting](https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/) and Martin Eastwood [pena.lt/y/2021/06/24/predicting-football-results-using-python-and-dixon-and-coles](https://pena.lt/y/2021/06/24/predicting-football-results-using-python-and-dixon-and-coles/). Library: penaltyblog (§3c).

**Method (concrete, implementable):**
- **Base Poisson:** home goals `λ = exp(α_home + β_away + γ)`, away goals `μ = exp(α_away + β_home)`; α = attack, β = defence per team, γ = home advantage.
- **Dixon-Coles low-score correction** τ(x,y,λ,μ,ρ) applied only to the 2×2 corner: `(0,0)→1−λμρ`, `(0,1)→1+λρ`, `(1,0)→1+μρ`, `(1,1)→1−ρ`, else 1 — fixes Poisson's under-count of low/draw scorelines.
- **Time weighting:** downweight match log-likelihood by `φ(t) = exp(−ξt)`, t = days since match; Dixon-Coles used **ξ ≈ 0.0065** (per-day), practical range 0.0018-0.0065. ξ=0 disables.
- **Fit:** sum `φ(t)·[log τ + log Poisson(x;λ) + log Poisson(y;μ)]` over matches; maximize via `scipy.optimize.minimize` with an identifiability constraint (mean attack = 1); select ξ by rolling-window validation.
- **Derive signals:** build the `(max_goals+1)²` scoreline PMF matrix `outer(Poisson(λ), Poisson(μ))`, apply τ to the corner, then sum cells for home/draw/away, **clean-sheet** (opponent goals = 0 column/row), and expected goals-conceded — the exact inputs FPL GK/DEF/CS points need.

**Pi suitability:** Very light. penaltyblog's Cython fit is fast on ARM; even hand-rolled scipy fit is fine.

**Borrow:** Use time-weighted Dixon-Coles (via penaltyblog) as our fixture layer to produce clean-sheet probability and goals-conceded per team per fixture, then feed those into defender/GK point projections and into the optimizer's per-GW EV.

---

### 6. How these pipelines sequence the stages

Cross-referencing OpenFPL, FPL Review, and the solver, the consensus pipeline is:

1. **Data ingest** — FPL API (prices, availability tags, realized points, `ep_this`), Understat (xG/xA), bookmaker odds; backfill from vaastav. [OpenFPL §1; vaastav §3b]
2. **Fixture/team model** — Dixon-Coles (or odds-implied) → per-fixture clean-sheet, goals-for/against, win/draw/loss. Enters as team/opponent features and as the CS/GC layer. [§5, §3c]
3. **Minutes model** — xMins or FPL availability tags; gates every attacking/defensive expectation (a nailed-on starter vs a rotation risk). [OpenFPL uses public tags; FPL Review uses proprietary xMins]
4. **Player point projection** — position-specific model over a 1/3/5/10/38-window feature set producing per-player per-GW `xPts` for ~6-14 GWs. This is the central table. [OpenFPL §1; interface per FPL Review §2]
5. **Optimization** — multi-period MILP: pick 15, XI, captain/vice, bench order, transfers, chips, maximizing decayed EV under budget/quota/club/formation/FT constraints. [solver §3a; MILP formulation §4]
6. **Captain/bench decision** — falls out of the same MILP (captain doubling, bench weights, vice at 0.1), not a separate stage. [§3a, §4]

Signals enter left-to-right: odds/xG → fixture strength → minutes gate → per-player xPts → MILP objective coefficients. The minutes gate multiplies into the projection; the fixture CS probability enters both the projection (DEF/GK) and effectively the objective.

---

## Recommended stack to adopt

- **Projection layer → adopt OpenFPL's method wholesale.** Position-specific ensembles (XGBoost + Random Forest), features averaged over **1/3/5/10/38-match windows** across player/team/opponent families, **median-of-N** ensemble, and **FPL-API availability tags** in place of a proprietary xMins model. It is MIT, open, public-data-only, and benchmarked to rival FPL Review on Haulers. Ship pre-trained models to the Pi; retrain off-Pi. Evaluate on **Hauler-recall**, not just RMSE. [OpenFPL]
- **Fixture / clean-sheet layer → penaltyblog Dixon-Coles.** Time-weighted (ξ≈0.0065) Dixon-Coles with low-score correction, fed by odds-implied goal expectancies. Produces CS probability and goals-conceded to condition GK/DEF projections. MIT, Cython-fast, Pi-friendly. [penaltyblog / §5]
- **Optimizer → mirror open-fpl-solver's multi-period MILP.** Keep our PuLP formulation but adopt its concrete parameters: horizon of ~6-8 GWs, **0.84/week decay**, **bench weights {0.03, 0.21, 0.06, 0.002}**, **vice at 0.1**, **4-pt hits**, FT accumulation capped at 5 with ~1.5 FT-value, and the **four chips as mutually-exclusive constraint toggles** (WC/FH/BB/TC). If CBC is slow on the Pi, switch to **HiGHS via highspy** (the solver's engine). [open-fpl-solver §3a; formulation cross-checked with §4]
- **Baseline / sanity layer → recency-weighted or ARIMA points estimate.** Per Ramezani & Dinh, a recency-weighted/ARIMA time-series projection beats a flat average and is a cheap, leak-free baseline to validate the ML projections against. [arXiv 2505.02170]
- **Data → vaastav for history + FPL/Understat APIs live.** Mind the `ep_this`/`xP` post-deadline leakage; build leak-free labels. [vaastav]
- **Skip / deprioritize:** proprietary FPL Review internals (unavailable), robust/box-uncertainty optimization (marginal per §4), and any bespoke goals/assists/CS point-decomposition — OpenFPL shows direct point regression is competitive and simpler.

**Pi-lightweight verdict:** every recommended component is Pi-viable at inference time (XGBoost/RF predict, HiGHS/CBC MILP, Cython Dixon-Coles). The only heavy step — training the 50-model ensemble — is a one-off done off-Pi with shipped model artifacts.

---

## Sources

- OpenFPL paper: https://arxiv.org/abs/2508.09992 · https://arxiv.org/html/2508.09992v1
- OpenFPL code (MIT): https://github.com/daniegr/OpenFPL
- FPL Review Massive Data docs: https://docs.fplreview.com/the-model/projections/massive-data-model/ · https://fplreview.com/access-the-massive-data-planner/
- open-fpl-solver (Apache-2.0, ex sertalpbilal FPL-Optimization-Tools): https://github.com/solioanalytics/open-fpl-solver · solver source `dev/solver.py`: https://raw.githubusercontent.com/solioanalytics/open-fpl-solver/main/dev/solver.py
- vaastav data repo: https://github.com/vaastav/Fantasy-Premier-League
- Ramezani & Dinh MILP paper: https://arxiv.org/abs/2505.02170 · https://arxiv.org/html/2505.02170 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5337103
- Dixon-Coles Python (dashee87): https://dashee87.github.io/football/python/predicting-football-results-with-statistical-modelling-dixon-coles-and-time-weighting/
- Dixon-Coles Python (Martin Eastwood): https://pena.lt/y/2021/06/24/predicting-football-results-using-python-and-dixon-and-coles/
- penaltyblog (MIT): https://github.com/martineastwood/penaltyblog · https://penaltyblog.readthedocs.io/
