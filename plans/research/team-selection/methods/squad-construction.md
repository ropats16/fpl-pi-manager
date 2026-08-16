# Method — squad construction & budget allocation

The **constrained-portfolio** problem: building the 15-man squad, distinct from
valuing individual players. This is what the [#25](https://github.com/ropats16/fpl-pi-manager/issues/25)
run and the project's existing PuLP/ILP optimiser actually do. Full evidence:
[../raw/followup-squad-construction.md](../raw/followup-squad-construction.md);
optimiser methods cross-referenced in [reference-pipelines.md](reference-pipelines.md).

## Verified rules baseline (FPL 2026/27)

£100.0m budget · 15 players = **2 GK / 5 DEF / 5 MID / 3 FWD** · **max 3 per club** ·
XI = 11 with ≥1 GK, ≥3 DEF, ≥1 FWD (≥2 MID in practice) · 4 bench slots (1 GK + 3
outfield) in priority order with autosubs
([PL — Scout's golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)).

---

## Budget-allocation shape

**Suggested heuristic: balanced-but-strategic, NOT stars-and-scrubs.**

- Hard evidence from top-50 managers (2025/26, effective budget): **GK ~6% · DEF ~23% ·
  MID ~41% · FWD ~30%**. Concentrate premiums in **midfield** (the value-richest
  position); forwards are historically overpriced past one anchor striker — loading
  premiums into attack is *worse* than the same money in midfield
  ([FF Fix — top-50 budget](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-budget-25-26/)).
- "Stars and scrubs always wins" is DFS folklore, not FPL evidence — the top-50 data
  shows *moderated* concentration (premiums in 2–3 spots, real money still spread across
  a balanced spine). **[candidate → evaluate]** as an extreme; the balanced split is
  **[tier-1]**.
- **The true target is XI xPts, not 15-man cost** — bench points are near-zero, so
  "effective budget" is the spend on your starting XI. Method: bias the objective toward
  XI xPts, treat ~£17–20m DEF and £4.0–4.5m GK as value zones.

---

## Bench & GK strategy

**Suggested heuristic: cheap-but-functional bench (near-nailed autosub cover, not dead
fodder); one reliable starter GK + £4.0m backup.**

- Bench-order value is real but small (~**5–10 pts/season** from autosubs); autosub
  points only count when a starter plays **0 min**, so a "playing bench" is injury/
  rotation insurance, not a points engine (that's the Bench Boost chip's job)
  ([FFS autosubs](https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs)).
- **Method:** encode a minimum expected-minutes floor on the 3 outfield bench slots
  (autosub insurance) but cap their cost hard; order the bench each GW by
  `P(0 min) × xPts-if-plays` respecting formation. GK: model as {1 starter at ~full xPts
  + 1 backup at ~0}; a rotation pair (2× £4.5m) is a defensible alternative only when no
  clear £4.0m starter exists. Top-50 lean: pay for one reliable GK, not two.

---

## Formation

**Suggested heuristic: don't hard-pin it — let the optimiser choose within legal bounds.**

- 6-season average of optimal teams ≈ (3.2 DEF, 4.5 MID, 2.3 FWD) → rounds to 3-5-2;
  4+ midfielders appeared every season. But **DEFCON makes 4-4-2 genuinely competitive**
  (cheap defenders gain a CBIT scoring floor) and revives defensive-mids
  ([FF Reports](https://www.fantasyfootballreports.com/best-formation-fpl/);
  [RotoWire](https://www.rotowire.com/soccer/article/best-fpl-formation-2026-27-which-shape-wins-fantasy-premier-league-127303)).
- **Method:** let the ILP choose the XI formation freely (≥3 DEF, ≥1 FWD, ≥2 MID);
  put [DEFCON](../factors/scoring-dimensions.md#defensive-contribution-defcon) xPts into
  the *player scores* so the solver lands 4-at-the-back when cheap DEFCON defenders
  out-score a 5th mid. "It's not about the formation, but about the players" — formation
  is an output of selection. Optionally enforce ≥4 MID *in the 15* as a soft prior.

---

## Optimizer objective & constraints

**Suggested heuristic: decay-weighted, bench-weighted, captain-doubled multi-GW xPts —
NOT a raw single-GW sum. [proven → adopt] (documented open solvers).**

The gold-standard open tools do **not** maximise a raw single-GW sum. Concrete,
documented parameters to adopt (from sertalpbilal's HiGHS MILP and the arXiv 2505.02170
formulation — see [reference-pipelines.md](reference-pipelines.md)):

```
maximize  Σ_gw  decay^(gw − now) · [ Σ_starters xPts·P(start)
                                     + captain_bonus · best_starter
                                     + 0.1 · vice
                                     + Σ_bench bench_weight · xPts ]
                 − 4·(hits) + ft_value·(banked FTs)
```

- **Time decay** `~0.84/week` — discounts future GWs, avoids one-week fixture chasing.
- **Bench weights** ≈ `{GK 0.03, b1 0.21, b2 0.06, b3 0.002}` — expected probability each
  bench player is needed; keeps the bench cheap-but-alive.
- **Vice** carried at `0.1` (fallback EV); **captain** doubles the best starter (`Σ c_j(x_j+y_j)`).
- **Hits** = −4 pts each beyond free; FTs accumulate +1/week capped at 5, ~1.5 pt FT-value
  for banking; the four chips as mutually-exclusive constraint toggles (WC/FH/BB/TC).
- **All six rule constraints stay hard-linear**; push DEFCON and minutes into the
  per-player xPts, **not** into structural constraints — so structure *emerges from
  valuation* rather than being hand-coded.

Baseline sanity check: a recency-weighted / ARIMA per-player points estimate beats a flat
average (arXiv 2505.02170) — cheap, leak-free, validate the ML projection against it.

---

## Max-3-per-club

Hard linear constraint (`Σ players per club ≤ 3`), forcing ≥5 clubs across 15. It's the
main structural brake on team stacking. **Method:** keep it hard; *allow* the solver to
hit 3 on strong clubs (don't artificially spread — that throws away value). The
covariance reward/risk of stacking is handled in valuation, not here — see
[../factors/value-and-ownership.md#whole-xi-covariance--portfolio-variance](../factors/value-and-ownership.md#whole-xi-covariance--portfolio-variance).

---

## GW1-specific construction

**Suggested heuristic: template-leaning core + price-point flexibility + ~£0.5m bank;
template captaincy; avoid early differentials/aggression.**

- Low information ⇒ crowd wisdom is a defensible GW1 prior; blend optimiser xPts with an
  ownership/template prior (shrink toward the crowd under uncertainty). "Swing for
  differentials in GW1" is contrarian folklore — the evidence (low info + rank-risk
  asymmetry) favours template-leaning openers, saving aggression for when data accrues.
- **Price-point flexibility** is the key GW1 skill: pick "round" price points (e.g. £8.0m
  mid, £4.0m fodder) so any single-move pivot stays open across the early weeks; keep
  **~£0.5m bank**; build for GW1–5 and roll FTs toward GW6.
- **Captain the field's premium** (don't differential the armband in GW1). Replace any
  player who doesn't start their final 1–2 friendlies (fitness gate). The specific
  template/players are a **current-season fact for [#25](https://github.com/ropats16/fpl-pi-manager/issues/25)**,
  not this wiki.

Evidence tier: **[tier-1]** — top-50 + PL golden rules.
