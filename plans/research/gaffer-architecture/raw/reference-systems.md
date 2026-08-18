# Reference FPL Systems — Proof Audit & Adversarial Critique (Track C)

Research for GitHub issue #9 "Decision: gaffer architecture". Scope: catalog serious autonomous/semi-autonomous FPL systems, audit how *proven* each really is, decompose what drives the good ones, map failure modes + scope to beat them, review LLM-as-manager attempts, and set a benchmark target for our gaffer.

**Evidence tiers used throughout:**
- **[proven]** — independently verifiable: peer-reviewed/preprint paper *with methodology & reproducible eval*, open code, official figures, or a checkable public FPL entry ID.
- **[standard]** — documented by a credible first-party or reputable analytics source; widely accepted but not independently audited.
- **[tier-1]** — single credible academic/official-adjacent source, not independently corroborated.
- **[tier-2/folklore]** — forum/blog/self-reported/screenshot; not verifiable.
- **[unverified]** — a live page or figure I could not render/confirm this session.

**Hard finding up front:** across the *entire* public record — commercial services, open-source solvers, academic papers, and bots — **not one system publishes a checkable FPL entry ID tied to a season-by-season overall rank.** Every "solver got me top-X" claim is self-reported. All rigorous evaluation stops at projection error (RMSE/MAE) or *backtested* hindsight points, never a live, ID-verified competitive finish. This shapes every conclusion below.

---

## Q1 — Catalog of serious autonomous / semi-autonomous FPL systems

### A. FPL Review (fplreview.com) — commercial projections + solver  `[standard]`
- **What it does:** the **Massive Data Model** (its main projection model), a **Transfer Solver** / **Linear Optimiser**, and a **Season Review** benchmarking tool; premium access via Patreon. Source: `docs.fplreview.com` — *"Massive Data Model … the sites main projection model."*
- **What's public:** *product description only.* The model page lists **inputs** — *"Integrates historical performance data, market odds, tactical analysis, and more"* and *"team strength & style, player roles, tactical changes … penalty takers/rotation … data recency"* — but **no algorithm, weights, feature list, or train/val split.** Not reproducible. `[standard]`
- **Documented results:** two first-party articles exist by title (*"A Goalscoring Model More Predictive Than Bookmakers Odds"*, *"Ultimate Truth: How FPL Models Perform Relative to a 'Perfect' Model"*) but the live pages return HTTP 403 to fetch and are self-published marketing → **[unverified]** and not independent even if reachable.
- **No self-run FPL entry ID / rank track record found.** "Season Review" is a user-facing tool (you input your own team), not a disclosure of a team the site runs. `[proven-negative]`

### B. sertalpbilal / FPL-Optimization-Tools (the "solver community" hub) — open ILP solver  `[proven]` (code)
- **Identity correction:** `github.com/sertalpbilal/FPL-Optimization-Tools` now **301-redirects** (repo id 344928234) to **`solioanalytics/open-fpl-solver`** (transferred/renamed; maintainer contact now `chris.musson@hotmail.com`, crediting Sertalp for the early tool). Verified via GitHub API: **created 2021-03-05, 182★, 61 forks, Apache-2.0, actively pushed Aug 2026.**
- **What it does:** deterministic ILP squad optimizer — README: *"uses **pandas** … and **HiGHS** via **highspy** to build and solve the optimization model … Automatically select the best FPL squad based on the given projection data."* Multi-week horizon **confirmed** (`comprehensive_settings.json: "horizon": 8`); chip modelling **confirmed** (`chip_limits`, `allowed_chip_gws`, `forced_chip_gws`, `ft_value`, `bench_weights`).
- **Crucially, it ships NO projections** — it *consumes* external CSVs. README: *"Place your projections file (e.g., `solio.csv`) in the `data/` folder."* Sertalp's own posts confirm compatibility with *"@fplreview MD, @fplreview Market Odds, @MikkelTokvam, and @theFPLkiwi"* `[tier-2, tweet-sourced]`. **The solver is projection-agnostic; projections are the differentiator, not the optimizer.**
- **Related:** `sertalpbilal/fpl_optimized` (68★) powers `fploptimized.com`, which publishes daily optimized squads — but **no public entry ID / rank record.** `[proven-negative]`

### C. OpenFPL (daniegr / Daniel Groos) — open-source ML forecasting  `[proven]`
- arXiv **2508.09992** (Aug 2025); code at `github.com/daniegr/OpenFPL` (22★). Position-specific **ensemble ML** forecasting from public FPL + Understat data. Abstract: *"comprises position-specific ensemble models optimized on … four previous seasons (2020-21 to 2023-24), and achieves accuracy comparable to a leading commercial service when tested prospectively on data from the 2024-25 season."*
- **Explicitly benchmarks FPL Review's Massive Data Model** (names it) — see Q3. Open code + prospective (not in-sample) test = strongest *projection-accuracy* evidence in the field. **No overall-rank/points claim** — accuracy only.

### D. Ramezani & Dinh 2025 — ILP + robust optimization, projection bake-off  `[proven]` (methodology; backtest only)
- arXiv **2505.02170v3** (revised Jan 2026). Deterministic + robust MILP choosing XI/bench/captain under budget/formation/club constraints; compares averaging, exponential smoothing, **ARIMA**, Monte Carlo, and a ridge-hybrid. Backtest on **2023/24** (train GW1-26, eval GW27-38). Conclusion: *"ARIMA(1,0,0) rolling and weighted-average models delivered higher cumulative scores over Gameweeks 27-38 … relatively simple forecasts can outperform more elaborate pipelines once embedded in an appropriate integer-programming formulation."* **No live rank** — backtested cumulative points only.

### E. Matthews, Ramchurn & Chalkiadakis — AAAI 2012, the one real autonomous-agent benchmark  `[proven]`
- *"Competing with Humans at Fantasy Football,"* AAAI vol. 26, pp. 1394-1400. Models FPL as a belief-state MDP; **Bayesian Q-learning** autonomous manager, trained on 2009/10, evaluated over 2010/11.
- **Verified results (Table 1):** best mean **BQL-180 = 2068.5 pts, mean rank ~26,065** (SE 8.6); best single run **2222 pts, "within the top 500"** of **2.5M** human players. Naive baseline M1 = 1981.3 (rank ~113,921). Abstract: *"rank at around the top percentile when pitched against 2.5M human players."* Percentile ranks cited ~**1.1st-1.5th**. This is the **only** autonomous system with a *contemporaneous, if self-run, percentile against the real field* — still a simulation over historical data, not a live public entry.

### F. Uppsala MSc thesis UPTEC I 25008 (May 2025) — ML + LLM assistant  `[tier-1]` `[unverified figures]`
- *"Enhancing Fantasy Premier League"* — ML point predictions feed an **LLM** that generates per-user recommendations, plus XAI + chat UI. Reported **1,293 points → "top 12%"** over a season. **Important:** the LLM is an *explanation/recommendation* layer; an ML model + optimizer does the picking. The DiVA PDF/record refused connection this session, so the 1,293 / top-12% figures are **[unverified — search-snippet only]**; treat as provisional.

### G. LLM / bot hobby projects (no track records)  `[tier-2/folklore]`
- `k1lgor/fantasy-ai` (GPT-4o Streamlit optimizer, 1★), `pizzato/roboklopp` (recommendation engine; blog claim ~top 0.5% but **no entry ID**, article 403), `enricozammitlon/FPL-Auto-Bot`, `Plastonick/fpl-bot`, `sfog17/fpl-bot` — all low-star, **none present a linked FPL entry ID + multi-GW live result.** Commercial GPT wrappers exist (ChatFPL / FantasyFootballFix, FPL Copilot) — no verified track record.
- Broader academic catalog (from Ramezani refs): Gupta 2019 (`arXiv:1909.12938`, time-series "dream team"); Santoro 2025 (Bologna MSc, `amslaurea.unibo.it/id/eprint/35674`); Bangdiwala et al. 2022 (ASIANCON, ML points); Venter & van Vuuren 2024 (ORiON, optimisation); Bhatt et al. 2019 (AAAI ICWSM, crowd captain). All `[tier-1]`, projection/optimization studies, none with a verified live rank.

---

## Q2 — Proof audit: how verifiable is each success claim?

| System | Code public? | Methodology public? | Ships projections? | VERIFIED live rank? | Best *documented* result | Tier |
|---|---|---|---|---|---|---|
| FPL Review | No (SaaS) | Described, not specified | Yes (proprietary) | **No** | Self-published accuracy articles (403/unverified) | `[standard]` |
| sertalpbilal solver | **Yes** (Apache-2.0) | **Yes** (ILP, open) | **No** (consumes CSVs) | **No** | — (tool only) | `[proven]` code |
| OpenFPL | **Yes** | **Yes** | Yes (open) | **No** (accuracy only) | ≈ FPL Review MAE/RMSE; better on high-return | `[proven]` |
| Ramezani & Dinh | Yes (linked) | **Yes** | Yes (open) | **No** (backtest) | ARIMA(1,0,0) best cumulative GW27-38 '23/24 | `[proven]` methodology |
| Matthews 2012 | No | **Yes** | Yes (own) | **Simulated** vs 2.5M | 2068.5 mean / best 2222 (top-500), ~1.1 pctile | `[proven]` |
| Uppsala LLM thesis | Unclear | Partial | Yes | **No** | 1,293 pts / "top 12%" | `[tier-1]` `[unverified]` |
| Bots (roboklopp etc.) | Yes | Partial | varies | **No** | self-reported "top 0.5%" | `[tier-2]` |

**Survivorship bias — adversarial verdict:** there is **no published distribution of solver-user finishes.** Only winners self-select into posting screenshots. Nobody publishes the losers. The rigorous literature (Ramezani, OpenFPL) evaluates on **backtested points or projection RMSE, never a live ID-verified rank.** Therefore any claim that "solver users finish top-X%" is **unsupported by any public dataset** and the survivorship bias is **unquantified and plausibly severe.** The one honest, quantified competition-against-the-field result in the whole field is Matthews 2012's ~1.1-1.5 percentile — and that is a *retrospective simulation*, not a live public entry.

---

## Q3 — What actually drives the good ones (projections vs solver vs human discipline)

**1. Solver optimality is a solved, commoditised layer.** Given a projection vector, the ILP finds the true EV-optimal squad deterministically. The open solver is projection-*agnostic* — so the optimizer is **not** where edge lives. Ramezani's headline confirms it: *"relatively simple forecasts can outperform more elaborate pipelines once embedded in an appropriate integer-programming formulation."* Corollary: **you cannot beat the references on the optimizer; everyone can run the same ILP.**

**2. Projection quality is the real differentiator — and its edge is modest and contestable.** OpenFPL (free, open) matches FPL Review's commercial Massive Data Model. Head-to-head 1-GW-ahead **MAE** (verified from arXiv HTML; lower = better):

| Bucket | OpenFPL | FPL Review MD | Winner |
|---|---|---|---|
| Zeros | 0.427 | **0.237** | FPL Review |
| Blanks | 0.749 | **0.597** | FPL Review |
| Tickers (3-4 pts) | **1.127** | 1.227 | OpenFPL |
| Haulers (≥5 pts) | **4.317** | 4.381 | OpenFPL |

(FPL Review's own RMSE table corroborates the *direction*: it wins the low-return buckets, OpenFPL edges the high-return buckets that drive rank gains.) OpenFPL abstract: *"surpasses the commercial benchmark for high-return players (>2 points), which are most influential for rank gains."* **Implication:** the commercial projection moat is thin — a free open model already matches it, and *high-return prediction* (haulers/captaincy) is where marginal edge translates to rank.

**3. Human/decision discipline is real, persistent, and measurable.** PLOS One 2021 (O'Brien et al., peer-reviewed version of `arXiv:2009.01206`), ~3M managers: cross-season points correlation **0.42**; **+22.1 points per additional year of experience** (R²=0.082); **+21.8 points per £1M** mid-season team value. Skill persists across 13 seasons. Conclusion: *"long-term planning and consistently good decision-making in the face of the noisy contests."* **Implication:** the layer above projections+solver (transfer/chip discipline, long-horizon planning) contributes real, repeatable points — this is exactly where a judgment layer can add value *if* it improves discipline rather than adding noise.

---

## Q4 — Failure modes + scope to improve

**Documented / structural weaknesses of the reference stack:**
- **Low-return / minutes-driven prediction is the hard part.** The buckets where models are *weakest relative to each other* are Zeros/Blanks (did the player even play/return?), i.e. **minutes & rotation risk** — OpenFPL is materially worse than FPL Review at Zeros (0.427 vs 0.237 MAE). Rotation/injury/benching is the dominant error source. `[proven]` (from the MAE tables) + `[standard]` (community consensus).
- **Template convergence / herding.** PLOS One documents temporary convergence to a consensus "template team" that *"does not persist in time."* A pure-EV solver naturally converges to the template, capping differentiation. `[proven]`
- **Backtest ≠ live.** Every reference validates on hindsight; **stale-projection risk near deadline** (late team-news, price/injury updates) is untested in any published eval. `[proven-negative]`
- **Over-trust in EV ties.** ILP treats near-equal EV picks as interchangeable; it has no tie-breaker for fixture swings, rotation, or ownership/risk posture. `[standard]`
- **Chip mistiming.** No reference demonstrates *validated* chip timing against a live field; Ramezani explicitly defers chips to future work. `[proven-negative]`

**Where an LLM-judgment + betting-odds layer could plausibly BEAT the references:**
- **Tie-breaking among near-equal-EV picks** using rotation/press-conference/fixture context the projection model doesn't encode.
- **Minutes/rotation qualitative signals** (manager quotes, cup congestion, "rested" hints) — the exact weakness above.
- **Risk posture / differential selection** to escape template convergence when chasing rank vs protecting it.
- **Chip-timing narrative** (double/blank gameweek foresight) layered on solver EV.
- ⚠️ **Caveat — odds are NOT a moat:** FPL Review *already ingests market odds*. Betting-odds grounding is table stakes, not a differentiator; edge must come from *how* odds are combined with judgment, not from having them.

**Where an LLM would likely do WORSE:**
- **Arithmetic / constrained optimization** — the ILP strictly dominates; never let the LLM pick the 15 or solve the knapsack.
- **Consistency / calibration** — LLM outputs vary run-to-run; the persistent-skill result (corr 0.42) rewards *discipline*, which an unconstrained LLM erodes.
- **Point projection itself** — an LLM will not out-predict a fitted ensemble on player points; keep it out of the projection numbers.

---

## Q5 — LLM-as-FPL-manager: documented attempts and honest results

- **No documented pure-LLM-as-picker with a verified competitive rank exists.** `[proven-negative]`
- **Best honest data point:** the Uppsala thesis (Q1-F) — LLM as an *explanation/recommendation* layer on top of ML+optimizer, reporting **1,293 pts / top ~12%** `[tier-1, unverified figures]`. Even here the LLM does **not** pick; the quant stack does.
- Hobby GPT bots and commercial GPT wrappers (ChatFPL, FPL Copilot, k1lgor/fantasy-ai) exist but publish **no verified track record** `[tier-2/folklore]`.
- **Honest read:** there is *zero* public evidence that an LLM alone selects an FPL team well. The only positive LLM signal is as a **judgment/explanation/tie-break layer over a quant core** — which is exactly the gaffer's proposed shape.

---

## Q6 — Benchmark targets ("beating the references")

**Champion / elite totals** (final winner totals):
- 2024/25 champion **Lovro Budišin = 2,810 pts**, won by 23, *never previously top 500k* `[standard, verified via FFScout]`.
- 2023/24 **≈ 2,799** (Jonas Sand Labakk) `[standard]`; 2022/23 **≈ 2,776** `[standard]`; 2018/19 winner **2,659** `[proven, PLOS One]`.

**Rank thresholds** (season-varying community estimates, FPL Oracle) `[standard]`:
- Top 10k (~0.1%): ~2,300-2,450 · Top 100k (~1%): ~2,150-2,250 · Top 500k (~5%): ~2,000-2,100 · Top 1M (~10%): ~1,900-2,000.

**Set-and-forget baseline** (best *static* hindsight team; upper bound of passive play) `[standard, community-computed — both figures I verified directly]`:
- 2023/24: **2,420 pts → only ~top 300k** (Palmer captain every GW).
- 2024/25: **2,531 pts** (Salah captain every GW, genetic-algorithm optimum). vs 2,810 champion → **active management added ≈ 280 pts** over the *optimal* static team.
- Naive (non-optimal) set-and-forget scores materially less; no clean public figure `[unverified]`.

**Average manager:** ~1,900-2,000 season total `[unverified precise]`; per-GW "average" ~50-55 is the top-half waterline `[standard]`.

**Perfect weekly-hindsight ceiling:** **not sourced.** Commonly-cited ~2,800-3,200 figures are `[tier-2/folklore]` / `[unverified]`. The only sourced upper bounds are the *static* optima above, which are a **lower** bound on the true ceiling.

**Autonomous SOTA bar:** Matthews 2012's RL agent hit **~1.1-1.5 percentile** (rank ~26k of 2.5M). Scaled to today's ~11M base, top-percentile ≈ **top 100k-ish**.

### Recommended benchmark target for the gaffer
1. **Primary (must-beat-references bar):** sustain **top 100k overall (≈ top 1%, ~2,150+ pts)** across multiple seasons — this matches the academic autonomous SOTA (Matthews ~1.1 pctile) and beats the average manager decisively.
2. **Necessary sanity floor:** **beat the optimal set-and-forget** (~2,420-2,531). If active management doesn't clear ~2,500+, the whole pipeline is adding noise, not value. This is the single cleanest pass/fail check.
3. **Reach goal:** **top 10k (~2,300-2,450 pts)** in a good season.
4. **Discipline metric (from PLOS):** because skill is persistent (corr 0.42), judge the gaffer on **multi-season consistency**, not one lucky year — a single top-10k could be variance.

---

## Implications for the gaffer — adopt / adapt / reject

**ADOPT:**
- **The ILP-solver shape** (sertalpbilal/OpenFPL/Ramezani). It's open, proven-correct, multi-week + chip-capable, and commoditised — no reason to reinvent. Feed it projections; let it solve the knapsack. Keeps the LLM *out* of arithmetic (Q4 weakness).
- **An open ensemble projection model in the OpenFPL mould** as the numeric core — a free open model already matches the commercial benchmark, so this is a realistic, low-cost path to benchmark-grade projections. Prioritise **high-return (hauler/captain) accuracy**, which drives rank.

**ADAPT:**
- **Betting-odds grounding** — useful but *table stakes* (FPL Review already uses odds). Differentiate on *combination with judgment*, not mere possession.
- **LLM strictly as a judgment / tie-break / explanation layer** over the solver: rotation & minutes signals (the top error source), differential vs template posture, chip-timing narrative, and human-readable rationale. This mirrors the only LLM approach with any positive evidence (Uppsala). Constrain it to *choosing among solver-proposed near-EV-tie options*, never generating the squad or the point projections.

**REJECT:**
- **Trusting any self-reported solver/bot "top-X%" claim** — the entire field lacks a single verifiable live-rank track record; assume severe survivorship bias.
- **Expecting a large projection moat** — the commercial edge is thin; don't over-invest chasing marginal MAE.
- **Letting the LLM do optimization, arithmetic, or point projection** — it will underperform the ILP and the ensemble and add run-to-run inconsistency that erodes the persistent-skill advantage.

**Benchmark to lock in:** sustained **top 100k (~top 1%, ~2,150+ pts)** as "beating the references," with a hard **must-beat-optimal-set-and-forget (~2,500 pts)** sanity floor and a **top-10k** reach goal — judged over multiple seasons, not one.

---

## Sources

**Papers (fetched / read):**
- Matthews, Ramchurn, Chalkiadakis, "Competing with Humans at Fantasy Football," AAAI 2012, vol. 26, pp. 1394-1400 (full text read from salvage; results Table 1). https://ojs.aaai.org/index.php/AAAI/article/view/8259
- Groos (daniegr), "OpenFPL: An open-source forecasting method rivaling state-of-the-art FPL services," arXiv 2508.09992v1 (abstract + HTML results verified). https://arxiv.org/abs/2508.09992 · https://arxiv.org/html/2508.09992v1 · code: https://github.com/daniegr/OpenFPL
- Ramezani & Dinh, "A data-driven framework for team selection in Fantasy Premier League," arXiv 2505.02170v3 (full text read from salvage; conclusion + refs). https://arxiv.org/abs/2505.02170
- O'Brien et al., "Identification of skill in an online game: The case of FPL," PLOS One 2021 (corr 0.42; +22.1 pts/yr; +21.8 pts/£1M; 2018/19 winner 2,659). https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0246698 · preprint https://arxiv.org/abs/2009.01206
- Uppsala MSc thesis UPTEC I 25008 (May 2025), "Enhancing Fantasy Premier League" — **[figures unverified this session; DiVA refused connection]**. https://uu.diva-portal.org/smash/get/diva2:1972615/FULLTEXT02.pdf

**Tools / repos (GitHub API + docs verified):**
- FPL Review docs: https://docs.fplreview.com/ · Massive Data Model: https://docs.fplreview.com/the-model/projections/massive-data-model/
- Solver: https://github.com/sertalpbilal/FPL-Optimization-Tools → redirects to https://github.com/solioanalytics/open-fpl-solver (182★, 61 forks, Apache-2.0, created 2021-03-05)
- sertalpbilal/fpl_optimized (68★) → https://fploptimized.com/
- Bots: https://github.com/pizzato/roboklopp · https://github.com/k1lgor/fantasy-ai · https://github.com/enricozammitlon/FPL-Auto-Bot · https://github.com/Plastonick/fpl-bot · https://github.com/sfog17/fpl-bot

**Benchmark figures (fetched):**
- 2024/25 champion (2,810 pts, won by 23): https://www.fantasyfootballscout.co.uk/2025/05/25/lovro-budisin-crowned-2024-25-fpl-champion
- Set-and-forget 2024/25 (2,531): https://www.fantasyfootballreports.com/the-best-fpl-team-of-2024-25-season/
- Set-and-forget 2023/24 (2,420 → ~top 300k) + "good score" bands (2,776 '22/23): https://www.fantasyfootballreports.com/best-fpl-team-2023-24/ · https://www.fantasyfootballreports.com/what-is-good-score-fpl/
- Rank percentile thresholds: https://fploracle.team/blog/fpl-rank-percentile
- Prediction-site comparison (single-GW, tier-2): https://fplwatchmen.substack.com/p/fpl-2025-gw1-analysis-of-prediction

**Unreachable this session (claims from these marked [unverified]):** fplreview.com article pages (403); web.archive.org; DiVA fulltext PDF; medium.com/@pizzato roboklopp write-up (403).
