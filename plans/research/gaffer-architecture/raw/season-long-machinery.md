# Season-long FPL strategy machinery (raw research — track B)

Research for [#9 "Decision: gaffer architecture"](https://github.com/ropats16/fpl-pi-manager/issues/9).
Scope: the machinery a **38-GW campaign** needs that a single-GW selection never exercises —
multi-period transfer planning, chip timing, price/team-value, the post-GW learning loop,
season cadence, and replanning discipline. Single-GW signal axes are already covered in
[../../team-selection/](../../team-selection/) and are **not** repeated here; this extends them.

**Hard project rule throughout:** *deterministic Python computes; the LLM judges.* Every claim
traces to a primary source (URL or in-repo/clone file path). Evidence tiers:
**[proven]** (official rule / reproduced result), **[proven-as-implemented]** (read directly from
solver source), **[standard]** (established method, applied here without FPL-specific proof),
**[tier-1]** (strong academic/analytics evidence), **[tier-2/folklore]** (single-vendor or blog
opinion), **[unverified]** (could not confirm at a primary source).

> **Two corrections to existing in-repo research, surfaced by this track (details inline):**
> 1. [importance-ranking.md](../../team-selection/importance-ranking.md) & [reference-pipelines.md](../../team-selection/methods/reference-pipelines.md)
>    cite **arXiv 2505.02170 (Ramezani & Dinh)** as the "multi-period MILP" authority. The paper is
>    **single-gameweek and explicitly excludes transfers and chips** — its "rolling" variant just
>    re-optimises a fresh squad each week with *no* transfer constraints. The real multi-period
>    authorities are the **open-fpl-solver source** and **Matthews et al. AAAI 2012**. (§1)
> 2. [meta-and-timing.md](../../team-selection/factors/meta-and-timing.md) cites the **"~+49 pts
>    chip timing"** figure to a *Fantasy Football Fix top-50 wildcards* page. A direct fetch of that
>    page shows **no such number**; the figure originates from a **single-vendor FPL Copilot blog**
>    with unpublished methodology. Downgrade [tier-1] → **[tier-2/folklore]**. (§2)

---

## 1. Multi-period transfer planning

The core season-long object: instead of maximising next-GW xPts, maximise **decayed cumulative
xPts over a rolling horizon**, with free-transfer (FT) banking, the −4 hit, and chips all inside the
same optimisation. Two independent lineages agree on the shape.

### 1a. The open-fpl-solver / sertalpbilal MILP (read directly from source)

Source: local clone of `solioanalytics/open-fpl-solver` (commit `136c39c`) — the maintained
successor to `sertalpbilal/FPL-Optimization-Tools`; both ship the *same* solver code
(`dev/solver.py`, 1145 lines). Public repo: <https://github.com/solioanalytics/open-fpl-solver> ·
original: <https://github.com/sertalpbilal/FPL-Optimization-Tools>. **[proven-as-implemented]**

**Objective** (`dev/solver.py:826-844`), maximised over a HiGHS MILP:

```
maximize  Σ_w  decay_base^(w − next_gw) · gw_total[w]

gw_total[w] = gw_xp[w]
            − hit_cost · penalized_transfers[w]      # −4 per extra transfer (soft)
            + gw_ft_gain[w]                          # value of banked FTs (diminishing)
            − ft_penalty[w]                          # small per-transfer friction
            + itb_value · in_the_bank[w]             # tiny reward for money in the bank
            − cp_penalty[w]                          # optional "don't own both sides" term

gw_xp[w] = Σ_p points[p,w] · ( lineup[p,w] + captain[p,w] + vcap_weight·vicecap[p,w]
                               + use_tc[p,w] + Σ_o bench_weights[o]·bench[p,w,o] )
```

**Standard parameter values** — note a real discrepancy between the *code defaults* and the
*shipped recommended config*, so the honest "standard" is a **range**:

| Param | Code default (`solver.py:291-299`) | Shipped `comprehensive_settings.json` | Meaning |
|---|---|---|---|
| `horizon` | **3** | **8** | rolling look-ahead length (GWs) |
| `decay_base` | **0.84** | **0.9** | per-GW multiplicative discount on future xPts |
| `ft_value` | 1.5 | 1.5 + list below | flat value of a banked FT |
| `ft_value_list` | — | `{2:2.0, 3:1.6, 4:1.3, 5:1.1}` | **diminishing** marginal value of the 2nd…5th banked FT |
| `bench_weights` | `{0:0.03, 1:0.21, 2:0.06, 3:0.002}` | same | P(bench slot is needed) |
| `vcap_weight` | 0.1 | 0.1 | vice-captain fallback EV |
| `hit_cost` | 4 | 4 | points per extra transfer |
| `itb_value` | 0.08 | 0.08 | reward per £0.1m in bank |
| `ft_use_penalty` | — | 0.2 | small anti-churn friction per transfer used |
| `report_decay_base` | — | `[0.85, 1.0, 1.017]` | alternate decays the solve is *re-scored* at |

Load-bearing mechanics extracted from the source:

- **FT banking, cap 5 (matches 2026-27 rule).** FT state is an integer in `{0,1,2,3,4,5}`
  (`ft_states`, `solver.py:336`); a big-M block clamps the raw next-week count into `[1,5]`
  (`solver.py:476-500`), i.e. you can never bank past 5. The **value** of banking is explicitly
  *diminishing*: `ft_value_list` gives marginal +2.0 for reaching 2 FTs, +1.6 for the 3rd, +1.3 for
  the 4th, +1.1 for the 5th (`solver.py:815-821`). So the machinery *does* value a bank, but with
  sharply falling returns — it will spend rather than hoard toward the cap. **[proven-as-implemented]**
- **The −4 hit is a SOFT penalty, not a hard threshold.** `penalized_transfers[w] ≥
  num_transfers[w] − fts[w] − 15·use_wc[w]` (`solver.py:411,505`); each unit costs `hit_cost=4` in
  the objective. A hit is taken *iff* the decayed multi-GW EV gain exceeds 4 — exactly the
  "must clear >4 pts over the GWs you'll own the player" discipline. **[proven-as-implemented]**
- **Wildcard & chips ARE decision variables.** `use_wc, use_bb, use_fh` are per-GW binaries and
  `use_tc` is per-(player,GW) binary (`solver.py:381-384`). One chip per GW
  (`use_wc+use_fh+use_bb+use_tc ≤ 1`, `solver.py:508`). A WC/FH zeroes the transfer penalty for its
  GW and carries the FT count across unchanged via an `aux` variable (`solver.py:475-476,509-510`).
  Chip *timing* is chosen by the optimiser within a **candidate window** the user supplies
  (`allowed_chip_gws`), or pinned (`forced_chip_gws` / `use_wc=[gw]`) or banned (`no_chip_gws`),
  bounded by `chip_limits` (`solver.py:513-566`). This is the "wildcard-as-decision-variable"
  formulation the question asks about. **[proven-as-implemented]** → carries straight into §2.

### 1b. Academic MILP / MDP lineage

- **Matthews, Ramchurn & Chalkiadakis, "Competing with Humans at Fantasy Football," AAAI 2012**
  (<https://ojs.aaai.org/index.php/AAAI/article/view/8259>, PDF
  <https://eprints.soton.ac.uk/340382/1/fantasyFootball2012cr.pdf>) — the genuine multi-period paper.
  **[tier-1]**
  - **Horizon:** full 38-GW season as a belief-state MDP, made tractable by **bounded-depth
    look-ahead**; best empirical depth **d=3** and *"Performance deteriorated for d ≥ 4."* So the
    *effective* planning horizon is short even when the objective spans the season.
  - **Decay:** explicit MDP discount `γ`; *"The best discount factor … is determined to be around
    γ = 0.5."* (Much steeper than the solver's 0.84–0.9, but it compounds through Q-value recursion —
    both encode "front-load the near GWs.")
  - **−4 hit:** modelled as **soft** negative-value knapsack "dummy items" with `v = −4`
    (*"Selecting these items permits an extra exchange at the expense of a four point penalty"*) —
    same soft-penalty design as the solver.
  - **Wildcard:** granted at **fixed** GWs 8 and 23, *not* optimised as a timing variable (weaker
    than the solver here).
  - **Measured value of planning over myopia:** BQL-180 reached **~top 1.1 percentile** (rank 26,065)
    against ~2.5M human managers; the myopic one-GW baseline scored lowest; deeper look-ahead mainly
    *"reduced chance of performing poorly … the lower quartiles."* → **multi-period planning is
    primarily downside-variance reduction.** (Feeds §6.)
- **Ramezani & Dinh, arXiv 2505.02170** (<https://arxiv.org/abs/2505.02170>, v3 Jan 2026).
  **[tier-1] but single-GW.** *"special and one-time cards are not taken into account"*; no FT rule,
  no −4, no chips. Its "rolling selection" re-optimises a fresh squad each week with **no transfer
  linkage**, and the rolling-vs-static gap is *often not significant* (e.g. *"n.s. q=1.000"*). Best
  configuration: an **ARIMA(1,0,0) rolling estimator with a £70m XI budget = 704 cumulative pts**
  on 2023/24 test GW27–38. Useful as a **leak-free estimator/baseline** (as
  [reference-pipelines.md](../../team-selection/methods/reference-pipelines.md) already says) — but
  it is **not** a multi-period transfer model, so do not cite it as one.

### 1c. What horizon / decay is "standard," and the evidence for it

- **Horizon:** solver community runs **3–8 GW** (shipped default 8; Sertalp's videos and the code
  default sit at 3–6); Matthews' effective depth is **3**. Convergence: *plan the whole season but
  optimise over an effective ~3–6 GW window* — beyond that, projection noise dominates and the
  extra GWs barely move the decision. Evidence tier: solver defaults **[proven-as-implemented]**;
  the "beyond ~6 GW adds little" claim is **[standard]** (projection error grows with horizon;
  Matthews' d≥4 degradation is the one direct measurement).
- **Decay:** **0.84–0.9 per GW** is the practitioner standard (solver); Matthews' γ≈0.5 is the one
  *empirically tuned* discount but on a compounding MDP. **These specific numbers are defaults, not
  FPL-optimised constants** — treat decay as a tunable knob, tag **[standard]** not [proven].
- **FT banking value:** encode the *diminishing* schedule (§1a) rather than a flat per-FT value;
  the cap is **5** for 2026-27. **[proven-as-implemented]** for the mechanism.
- **Hit threshold:** the −4 must clear **>4 decayed points over the horizon**, which with
  `decay=0.9` over the ~3–4 GWs you'll own a player means an underlying edge of ≈1.1–1.5 xPts/GW.
  **[proven-as-implemented]** (falls out of the objective).

---

## 2. Chip-timing machinery

### 2a. MILP toggles vs Monte-Carlo — they solve *different* uncertainties

- **MILP chip toggles** (open-fpl-solver, §1a): given a *known* fixture calendar, the binary
  `use_*` variables let the solver pick the GW (within `allowed_chip_gws`) that maximises decayed
  horizon EV. This is the right tool once the DGW/BGW calendar is (probabilistically) fixed.
  **[proven-as-implemented]**
- **Monte-Carlo over fixture scenarios** (same repo, `run/simulations.py` + `data/binary_fixtures.md`):
  when *which* games form the doubles/blanks is still uncertain, the tool generates **weighted
  "binary" fixture files** — each encodes one plausible reschedule (e.g. *"expected points will be
  moved from GW33 to GW34 for Bournemouth, Man Utd, Man City, Aston Villa"*), with a weight
  (*"60% of simulations will use `binary1.csv`, 30% … 10%"*) — and solves across the weighted
  ensemble. The randomised solve also injects minutes-uncertainty noise
  (`noise = Pts·(92−xMins)/134·N(0,1)`, `solver.py:202`). **[proven-as-implemented]**
- **Synthesis:** the two are **complementary, not competing** — MC resolves *calendar* uncertainty
  (what the fixtures will be), MILP toggles resolve *timing* given a calendar. A season daemon needs
  both: a probabilistic DGW/BGW feed → weighted scenarios → per-scenario MILP → chip GW that is
  robust across scenarios (the `sensitivity.py` "% of runs a chip/player is chosen" artifact, §4).

### 2b. Measured value of chip timing — **corrected & downgraded**

- The widely-repeated **"~+49 pts from optimal chip timing, ~+3 pts from best-vs-second chip
  choice"** traces to a **single vendor**: FPL Copilot's chip-strategy blog
  (<https://fplcopilot.com/blog/chip-strategy-guide>): *"The average FPL team gains 49 points from
  optimal chip timing compared to using no chips at all,"* and *"the gap between the best and
  second-best chip strategy is only ~3 points."* Method (as stated): a HiGHS MIP over *"hundreds of
  real squads"* evaluating *"every valid chip combination."* **Sample size, seasons, and statistical
  detail are unpublished.** **[tier-2/folklore — single-vendor, not independently reproduced]**
- **Correction:** the in-repo [meta-and-timing.md](../../team-selection/factors/meta-and-timing.md)
  attributes this to *Fantasy Football Fix — top-50 wildcards*. A direct fetch of that page
  (<https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-wildcards-2025-26/>) returns **no
  such figure** — it only shows *when* top managers played chips (1st WC modal ~GW4, 2nd ~GW32).
  So: keep the qualitative claim ("timing ≫ choice"), but **downgrade the +49 to [tier-2/folklore]**
  and fix the citation.
- What survives as reliable: (i) **timing dominates choice** — directionally supported by both the
  vendor study and the top-50 behavioural data; (ii) BB/TC value roughly **doubles on a DGW**
  (FPL Copilot: single-GW BB *"averages 8-12 points"* vs DGW BB *"15-25"*). **[tier-2]**

### 2c. Community sequencing rule-of-thumb (blog consensus)

*"Wildcard before the biggest fixture swing, followed by a Bench Boost in the next double gameweek,
with the Free Hit used on the blank gameweek"*; Triple Captain on *"your best player's best double
gameweek"*; Free Hit when *"3+ missing starters"* in a blank; first WC *"typically between gameweek
7 and gameweek 12"* once form data firms up
(<https://fplcopilot.com/blog/chip-strategy-guide>). **[tier-2/folklore]** — a sensible *prior*, not
a proof; the solver should be free to overrule it.

### 2d. DGW/BGW prediction off cup progression + lead time

- **Causal chain (FFS):** FA Cup QFs (~GW31–32) and SFs (GW34 weekend) force PL postponements;
  those postponed games become the later **doubles**, and *"Any postponed league matches could yet
  stay in Gameweek 34 … if both affected teams are out of Europe"* — so **European progression is
  the swing factor**
  (<https://www.fantasyfootballscout.co.uk/2026/03/09/what-the-fa-cup-draw-means-for-blank-gameweek-34>).
  **[tier-1]**
- **Quantitative method (Ben Crellin):** convert **bookmaker cup-SF odds** into DGW probabilities
  plus fixture-move assumptions — e.g. *"calculated the DGW36 percentages using the FA Cup SF odds
  and my assumption that GW37 postponements would have a 90% chance of moving to the midweek in
  GW36 and a 10%"* elsewhere; publishes probability spreadsheets *"excluding fixture movements that
  are less than 3% likely"* (<https://x.com/BenCrellin/status/1907913456407425054>,
  <https://x.com/BenCrellin/status/1897444495026790426>). **[tier-1 — primary author]**
- **Lead time:** probabilistic forecasts exist weeks out (from cup draws + odds), but **firm**
  DGW/BGW confirmation only lands **~2–4 GW ahead** (post-QF draw / once European ties resolve).
  The "2–4 GW" is a synthesis of the sourced constraint, not a verbatim quote — **[unverified as a
  number]**; the *direction* (short, firming late) is **[tier-1]**.
- **When they fall (structural window):** a winter cluster around **GW18/19** and a spring
  congestion band **GW24–GW37** (FA Cup 5th/QF/SF + EFL Cup final). 2024/25 confirmed examples:
  DGW24, DGW25, DGW32, DGW33; BGW29, partial-BGW34 — and *no* GW36/37 double materialised that year
  (<https://www.fantasyfootballscout.co.uk/2025/04/24/when-are-the-fpl-blank-and-double-gameweeks-in-2024-25>,
  <https://www.fantasyfootballscout.co.uk/2025/05/01/confirmed-no-more-blank-or-double-gameweeks-in-2024-25>).
  **[tier-1 — historical]**
- **2026-27 chip context (official, confirmed):** 8 chips, one set of {WC,FH,TC,BB} per half; the
  first set *"must be played before the Gameweek 19 deadline"* and *"cannot be carried over"*; one
  chip per GW (<https://www.premierleague.com/en/news/4679879>). **[official-rule]** → this makes
  **chip-forcing** essential: the daemon must *spend* set-1 chips by GW19 or lose them, so the MILP
  needs a `forced_chip_gws`-style deadline constraint on the first half.

---

## 3. Price-change & team-value machinery

### 3a. How price predictors work

- **Mechanism (LiveFPL):** a running **net-transfer counter** vs a **threshold** — *"When enough
  managers transfer a player in, their price rises by £0.1m … When this total crosses the threshold …
  the price changes and the counter resets."* The threshold is **ownership-scaled** (*"A budget
  defender owned by 2% … needs far fewer transfers to change price than a premium forward owned by
  50%"*) and **decays each GW** to discount dead/inactive teams
  (<https://livefpl.com/blog/fpl-price-changes>). **[proven-mechanism]** — but the *exact* threshold
  is **secret**; every predictor (LiveFPL, FPL Statistics, FFFix, FFS) **estimates** net transfers
  from a sampled subset of public teams → all thresholds are **[estimated, not official]**.

### 3b. Official movement rules

- **±£0.1m per day**, applied overnight UK time; historically **≈£0.3m max per GW** (up to 3 daily
  steps). **50% sell-on tax:** *"you only get £0.1m of profit for every £0.2m that the player rises"*
  (buy £5.0m, rises £0.4m → others pay £5.4m, your sale price £5.2m). **Falls are untaxed** — a drop
  below buy price costs the full amount
  (<https://www.premierleague.com/en/news/2858775>). **[official-rule]**

### 3c. What team value is actually worth (both sides)

- **Pro (correlation):** Full90 finds **0.75** corr (team value ↔ total points) and **0.7** (↔ rank)
  in a public league; **0.51 / 0.49** in a cleaner overall-top-25 sample
  (verified verbatim, <https://full90fpl.com/does-team-value-matter-in-fpl/>). Community lore: top
  managers build **~£2–3m** of value over a season. **[tier-2/blog]**
- **Con (causation runs backwards):** the same source — *"this only shows correlation and not
  causation. The higher team value could be a result of managers having players that score more
  points"* — and a top finisher: *"I don't think I made a single transfer this year based solely on
  whether I was going to gain or lose team value. And I have the fourth highest team value."*
  Early value-chasers *"generally had higher team value than the average but not necessarily higher
  points or better rank."* **[tier-2/blog]**
- **Adversarial check vs solver-community practice** (the task asked for this): does the open-source
  solver treat price as more than a tie-breaker? **No.** It carries price only as a **tiny** objective
  term — `itb_value = 0.08` per £0.1m banked (`solver.py:836`) — plus buy/sell-price *constraints*
  and an optional `price_changes` list and `transfer_itb_buffer`. Price shapes **feasibility and
  tie-breaks**, never the core valuation. This **corroborates** the in-repo ranking
  ([importance-ranking.md](../../team-selection/importance-ranking.md) Tier 3: "tie-breaker only,
  subordinate to information") — it survives the adversarial check. **[proven-as-implemented] +
  [tier-2]**

### 3d. What a daily daemon should DO vs ignore

- **Do:** run a cheap **daily** price-watch; among players **already on the transfer shortlist**,
  bring a planned move forward by ≤1 day to bank a predicted rise or dodge a predicted fall; maintain
  team-value as a **flexibility buffer**, not a target.
- **Ignore / forbid:** *"Never chase team value at the cost of a decently scoring XI"*; never
  **initiate** a transfer or take a **−4** whose sole justification is price
  (<https://full90fpl.com/does-team-value-matter-in-fpl/>). **Price is an input to transfer
  *timing*, never to *selection*.** ([tier-2/blog] best-practice; the daemon spec is author-inference
  consistent with it.)

---

## 4. Post-GW learning / calibration loop

### 4a. Scoring your own predictions vs actuals

- **Regression metrics:** OpenFPL evaluates with **RMSE (primary) + MAE (secondary)** at **1/2/3-GW
  horizons, per position (GK/DEF/MID/FWD/AM)**, and — crucially — **bucketed by return tier**, being
  *"most accurate in the high-return categories, Tickers (3–4 pts) and Haulers (≥5 pts)"* with a
  clean train/test split (train 2020-21…2023-24, test GW32–38 of 2024-25)
  (<https://arxiv.org/html/2508.09992v1>). → measure **hauler-recall**, not just aggregate RMSE.
  **[tier-1]**
- **Probabilistic calls** (clean-sheet %, haul %): the forecasting standard is the **Brier score**,
  decomposed into **reliability (calibration bias) / resolution / uncertainty**, read off a
  **reliability diagram**
  (<https://journals.ametsoc.org/view/journals/wefo/23/4/2007waf2006116_1.xml>). **[standard/academic]**
- **Vendor ceiling (context, unverified):** FPL Review reportedly benchmarks against a *"perfect
  model"* ceiling of **~2.81 RMSE / 1.96 MAE** on active players — page returned **HTTP 403**, so
  **[unverified verbatim]**
  (<https://fplreview.com/ultimate-truth-how-fpl-models-perform-relative-to-a-perfect-model/>).

### 4b. What one season can and cannot support

- **Cannot re-fit a weight vector.** The **events-per-variable rule** — classic *"one-in-ten,"*
  Harrell now *"at least 20 EPV"* (<https://twitter.com/f2harrell/status/985344885938180098>,
  <https://grokipedia.com/page/One_in_ten_rule>) — means ~38 GW rows (fewer *independent* signal
  events) support only a **handful** of free parameters. High-variance football pushes the floor up:
  even detecting *one* stable relationship wants **N ≥ 25**
  (<https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0229345>). A full
  multi-signal re-fit on one season **overfits**. **[academic]**
- **Can detect aggregate bias.** Calibration bias is a **single-parameter, aggregate** question
  ("am I systematically 0.4 pts high on defenders / on home teams / in the 60-min tier?") and is
  readable from a season's worth of pooled residuals via the Brier **reliability** term — even though
  you cannot responsibly re-estimate each underlying weight. Caveat: reliability-diagram **binning is
  unstable** on small samples (<https://journals.ametsoc.org/...2007waf2006116_1.xml>). **[academic]**
- **Responsible one-season policy:** *flag* per-stratum calibration bias and apply at most a **small
  global / shrinkage correction** (Harrell: *"penalization = shrinkage … data reduction is a good
  approach"*); **do not** refit the model. → This is an **LLM-judgment gate over Python-computed
  calibration stats**, not an auto-retrain loop. **[academic] + author-inference.**

### 4c. Review artifacts reference systems keep

- **Prediction-vs-actual error table** — per-horizon × per-position × per-return-tier RMSE/MAE
  (OpenFPL's evaluation section *is* the template). **[tier-1]**
- **Decision-stability / sensitivity log** — sertalpbilal re-solves N times and records **how often
  each pick is optimal**: *"6 players … appear in optimal GW1 team more than 70% of runs: Fernandes
  100%, Zinchenko 97.5%, Mitoma 95%, Gabriel 92.5%, Rashford 87.5%, Haaland 85%"*
  (<https://x.com/sertalpbilal/status/1682981948577177601>; repo `run/sensitivity.py`,
  `ITER_SCORING = {0:10, 1:9, 2:8}`). A move chosen in 55% of runs is a coin-flip; one chosen in 95%
  is a conviction call — the daemon should log this per GW. **[proven-as-implemented / tier-1]**
- **Calibration report** — pooled reliability by stratum (position, home/away, minutes tier), updated
  weekly, read by the LLM (§4b).
- **Decision log** — the transfer/captain/chip choice + the EV margin + the sensitivity % that
  justified it (this repo already keeps a per-GW decision log, e.g. issue #25/#28).

---

## 5. Season-long cadence map (concrete scheduler table)

A wake schedule a daemon could adopt directly. "Pipeline" = deterministic Python; "Judge" = an LLM
gate on the Python output. (Deadlines are T−90min before first kickoff; team news firms ~75min
before *each* kickoff — see [meta-and-timing.md](../../team-selection/factors/meta-and-timing.md).)

| Cadence | Trigger | Machinery (Python computes) | LLM judges |
|---|---|---|---|
| **Daily** | cron ~06:00 UK (post overnight price move) | refresh prices; recompute predicted risers/fallers among shortlist; refresh injury/press feed; update team-value | only if a *shortlisted* asset hits a price cliff → "bring move forward?" (else no-op) |
| **Daily (news scan)** | injury/rotation/suspension flag on an **owned** player | re-run xMins gate + affected-player EV delta; recompute XI/bench | is the plan broken (owned premium / captain / TC target out) or hold? (§6) |
| **Weekly — plan refresh** | ~T−72h pre-deadline | full projection rebuild; multi-period MILP over 3–8 GW horizon; sensitivity re-solve (N runs); chip-window scan | sanity-check solver plan; set risk posture (template vs differential) by rank state |
| **Weekly — finalise** | ~T−30 to T−15min | re-solve on latest team news/odds; lock XI, captain, bench order, transfers | commit under uncertainty; accept/deny any −4; final captain call |
| **Weekly — review** | post-GW settle (~T+24h) | prediction-vs-actual error table; per-stratum calibration residuals; decision-stability log; realised vs modelled | read calibration flags; note bias (no refit); log lessons |
| **Fortnightly / monthly** | rolling | recompute DGW/BGW probability feed from cup draws + odds; refresh chip plan; season-to-date calibration report | update chip schedule; decide if a global bias correction is warranted (§4b) |
| **On-event — cup draw / European result** | FA Cup round, European tie result | update fixture-move scenarios (weighted binary files); re-solve chip timing under MC | re-time chips if the calendar shifted materially |
| **On-event — price flag** | predicted overnight change on owned/target | precompute both branches | act only if move already planned |
| **Hard-deadline guard** | GW19 approaching | force-spend unused **set-1** chips before the GW19 deadline (they don't carry) | choose the least-bad forced window if none is ideal |

Notes: the **daily** loop is cheap and almost always a no-op (price is a tie-breaker). The **weekly
plan→finalise→review** triad is the spine. The **on-event** wakes are what a single-GW system lacks
entirely and where most season-long edge lives (chips, DGW/BGW pre-positioning).

---

## 6. In-season replanning triggers (break the plan vs hold)

The plan is a *prior*, not a commitment. Evidence + practice on when to deviate:

**Break the plan (deviate now):**
- **Injury/suspension to an owned premium**, especially the **captain or a TC/BB target** — the EV
  hole is large and immediate; re-solve. **[tier-1]** (standard practice; the xMins gate is the #1
  filter, [importance-ranking.md](../../team-selection/importance-ranking.md) Tier 0).
- **DGW/BGW confirmation** materially changing the fixture calendar → re-time chips/transfers
  (§2d). **[tier-1]**
- **Price cliff on an asset you were *already* going to move** → bring the move forward ≤1 day
  (§3d). *Not* a reason to move an asset you weren't. **[tier-2/blog]**
- **Fixture reschedule** (rearranged game moving a player's GW) → update scenario weights, re-solve.

**Hold (resist the urge):**
- **A big previous-GW haul by a non-owned player** — counter-momentum: top-50 managers buy at
  0/5/10/15% ownership, and the modal previous score of a player they bought was just **2 pts**
  (<https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/>, via
  in-repo). Don't chase. **[tier-1]**
- **A single bad GW** from an owned player whose *underlying* xGI/minutes are intact — damp
  single-GW noise (form regresses hard, [importance-ranking.md](../../team-selection/importance-ranking.md)
  Tier 2). **[tier-1]**
- **A −4 that doesn't clear the bar** — the hit must beat 4 decayed points over the horizon (§1a).

**Anti-points-chasing discipline (encode as guardrails):**
- **Don't reverse a transfer within N GWs** without new *hard* info (injury/role change), and
  require a **multi-GW decayed EV threshold** for any move — both directly expressible via the
  objective's `decay`, `hit_cost`, and `ft_use_penalty=0.2` friction, plus a `booked_transfers` /
  no-reverse lock. **[proven-as-implemented]** for the mechanism.
- **Planning ≈ variance reduction, not upside-chasing.** Matthews' result — deeper look-ahead mainly
  raised the *lower quartiles* — is the empirical case for disciplined holding over reactive churn.
  **[tier-1]**
- The machine's structural edge over humans is that it *can* be **perfectly disciplined**
  (in-repo [meta-and-timing.md](../../team-selection/factors/meta-and-timing.md), RotoWire). Encode
  it; don't let the LLM improvise churn.

---

## Implications for the gaffer — Python pipeline vs LLM judgment

**Deterministic Python computes (the machinery):**
- The **multi-period MILP** itself: decayed cumulative objective, FT-banking (cap 5, diminishing
  value), soft −4 accounting, chip toggles as decision variables, all six rule constraints hard
  (adopt the open-fpl-solver formulation and parameters wholesale; migrate PuLP/CBC → **HiGHS** as
  [reference-pipelines.md](../../team-selection/methods/reference-pipelines.md) already flags).
- **Monte-Carlo over weighted fixture scenarios** for DGW/BGW uncertainty + minutes noise.
- **Price-predictor ingestion** and shortlist-scoped riser/faller flags.
- **DGW/BGW probability feed** from cup draws + bookmaker odds (Crellin-style).
- **Calibration & error metrics** (RMSE/MAE per horizon/position/tier; Brier + reliability),
  **decision-stability sensitivity** runs, and the **review artifacts** of §4c.
- The **cadence scheduler** of §5.

**LLM judges (the decisions under soft/late information):**
- Which **chip-timing window** to commit to, given probabilistic calendars and template pressure.
- Whether a **replanning trigger** is real (injury severity, rotation risk, DGW confirmation) vs
  noise → break or hold (§6).
- Whether to **accept a solver-proposed −4** and the **risk posture** (template vs differential) by
  rank state.
- Reading **calibration flags** and deciding whether a **small bias correction** is warranted vs
  sample noise — never authorising a weight refit (§4b).
- **Overriding price-driven moves** (enforcing "price is timing, not selection").

**The boundary:** the solver *proposes* an EV-optimal multi-period plan **plus its sensitivity**
(how robust each pick/chip GW is); the LLM *disposes* — commits under uncertainty, times to
information, and applies the anti-churn discipline the solver's parameters encode but cannot decide
to trust. The season-long layer is exactly the set of things a next-GW optimiser is *structurally
blind* to: transfer economics across weeks, chip scheduling, calendar forecasting, and the learning
loop that keeps the projections honest.

---

## Sources

Primary solver source (local clone, `solioanalytics/open-fpl-solver` @ `136c39c`; = maintained
`sertalpbilal/FPL-Optimization-Tools`):
- `dev/solver.py` — objective (`:826-844`), FT banking clamp (`:476-503`), hit penalty (`:411,505`),
  chip decision variables (`:381-384,508-566`), defaults (`:291-299`)
- `data/comprehensive_settings.json` — shipped params (horizon 8, decay 0.9, ft_value_list, ft_use_penalty)
- `run/simulations.py`, `data/binary_fixtures.md` — Monte-Carlo over weighted fixture scenarios
- `run/sensitivity.py` — decision-stability artifact
- Repos: <https://github.com/solioanalytics/open-fpl-solver> · <https://github.com/sertalpbilal/FPL-Optimization-Tools>

Academic:
- Matthews, Ramchurn & Chalkiadakis, AAAI 2012 — <https://ojs.aaai.org/index.php/AAAI/article/view/8259> · PDF <https://eprints.soton.ac.uk/340382/1/fantasyFootball2012cr.pdf>
- Ramezani & Dinh, arXiv 2505.02170 — <https://arxiv.org/abs/2505.02170>
- OpenFPL, arXiv 2508.09992 — <https://arxiv.org/html/2508.09992v1>
- PLOS ONE — minimum sample size for regression — <https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0229345>
- One-in-ten rule / EPV — <https://grokipedia.com/page/One_in_ten_rule> · Harrell (≥20 EPV, shrinkage) <https://twitter.com/f2harrell/status/985344885938180098>
- Brier decomposition / reliability — <https://journals.ametsoc.org/view/journals/wefo/23/4/2007waf2006116_1.xml> · <https://www.emergentmind.com/topics/brier-score>

Official rules:
- FPL price changes (±£0.1m/day, £0.3m/GW, 50% tax) — <https://www.premierleague.com/en/news/2858775>
- 2026-27 chips (8 chips, set-1 expires GW19) — <https://www.premierleague.com/en/news/4679879>

Analytics / practitioner:
- FPL Copilot — chip strategy (source of the +49/+3 figures; single-vendor) — <https://fplcopilot.com/blog/chip-strategy-guide>
- Fantasy Football Fix — top-50 wildcards (does *not* contain +49; correction) — <https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-wildcards-2025-26/>
- Ben Crellin — DGW odds method — <https://x.com/BenCrellin/status/1907913456407425054> · <https://x.com/BenCrellin/status/1897444495026790426>
- Fantasy Football Scout — FA Cup → BGW34 — <https://www.fantasyfootballscout.co.uk/2026/03/09/what-the-fa-cup-draw-means-for-blank-gameweek-34> · 2024/25 BGW/DGW list <https://www.fantasyfootballscout.co.uk/2025/04/24/when-are-the-fpl-blank-and-double-gameweeks-in-2024-25>
- LiveFPL — price-change mechanism — <https://livefpl.com/blog/fpl-price-changes>
- Full90 — does team value matter (correlations, causation) — <https://full90fpl.com/does-team-value-matter-in-fpl/>
- sertalpbilal — GW1 sensitivity (40 iterations) — <https://x.com/sertalpbilal/status/1682981948577177601>
- FPL Review — perfect-model backtest (403/vendor-reported) — <https://fplreview.com/ultimate-truth-how-fpl-models-perform-relative-to-a-perfect-model/>
