# Factors — value, captaincy & ownership

The axes that make FPL a *relative, budget-constrained* game rather than a raw
points-maximisation. Full evidence:
[../raw/cluster-C-value-newaxes.md](../raw/cluster-C-value-newaxes.md),
[../raw/discovery-quant.md](../raw/discovery-quant.md),
[../raw/discovery-practitioner.md](../raw/discovery-practitioner.md),
[../raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md).

---

## Effective ownership & the rank objective

**Suggested weight: HIGH — the objective the whole engine should optimise.**

- FPL is played vs a field of millions, so **maximising rank ≠ maximising raw expected
  points.** Shared/template players give everyone identical points; you only move rank
  on players you own *differently* from the field. **Effective Ownership (EO) = start%
  + captain%** (captaincy can push a premium's EO past 90%). Not owning a 90%-EO haul is
  a rank loss even when your own score is fine
  ([FPL Oracle](https://fploracle.team/blog/effective-ownership-fpl)).
- **Method:** make the optimiser objective **rank-adjusted**: reward ≈
  `xPts − EO/100 × field_xPts` when chasing rank, shrinking toward raw xPts when
  protecting. Elite structure ≈ **60–70% template + 2–3 genuine low-EO upside picks**;
  differentiate when the low-EO alternative's xPts is within ~1.5 of the favourite,
  stay template only if the gap is ≥2. Make differential aggressiveness a tunable
  function of current rank/gap-to-target.
- **Earned vs unearned differentials:** low EO adds EV *only* when backed by genuine
  underlying stats — random differentials are just variance
  ([raw/discovery-practitioner.md](../raw/discovery-practitioner.md)).

Evidence tier: **[tier-1]** — game-theoretic; EO framework.

---

## Captaincy EV

**Suggested weight: HIGH — the single biggest weekly swing (~15–20% of score
variance; ~2–3× a routine transfer's EV).**

- **Method:** captain = `argmax` of a blended captain-xPts (model xPts × odds-implied
  goal/assist prob), **gated on minutes first**, then an EO/rank adjustment: captain
  the highest-xPts template player to protect rank; captain a lower-EO high-ceiling
  player to *gain* rank (differential armband pays off only when it hauls — price the
  punt by the xPts gap to the template captain). Reserve **Triple Captain** for a DGW /
  elite fixture on a near-zero-rotation premium
  ([FPL Oracle](https://fploracle.team/blog/fpl-captaincy-strategy);
  [FPLGameweek — odds for captaincy](https://www.fplgameweek.com/articles/how-betting-odds-can-inform-your-fpl-captaincy-choices/)).
- Run captaincy as its **own** EO-adjusted optimisation, not "highest-xPts starter by
  default." Averaging 8 vs 5 pts/captain ≈ 114 pts/season ≈ 200k+ ranks.

Evidence tier: **[tier-1]**.

---

## Whole-XI covariance & portfolio variance

**Suggested weight: HIGH — judge the XI's *distribution*, not the sum of 11 means.**

- Most optimisers "assume players do not have correlated errors and ignore covariance"
  — an exploitable blind spot. Same-team/same-match returns covary: two teammates are
  positively correlated on clean-sheet/winning scripts (raises XI variance — good
  chasing, bad protecting); a defender vs an opposing attacker are negatively correlated
  (a natural hedge) ([FF Reports](https://www.fantasyfootballreports.com/variance-fpl/);
  [FPL Optimized MC sims](https://fploptimized.com/scenarios.html)).
- **Method:** after picking on mean xPts, evaluate the covariance structure — count
  same-team doubles/triples (up to the max-3 cap), captain-on-a-stack, and DEF/attacker
  pairs in the same match. **Deliberately raise stacking + team variance when chasing
  rank; diversify across matches to lower variance when protecting.** Score distributions
  are right-skewed (rigid floor, open ceiling), so store a ceiling/floor or P(haul), not
  just a mean — pick captains/differentials on ceiling, set-and-forget picks on floor.
- Squad-level structural handling of the max-3 constraint:
  [../methods/squad-construction.md#max-3-per-club](../methods/squad-construction.md#max-3-per-club).

Evidence tier: **[tier-1]**.

---

## Price, value & differentials

**Suggested weight: MED as structure (budget allocation); LOW as a points signal
(price momentum).**

- **Points-per-million / value** is a **structural budget-allocation** metric — it
  decides where you can afford ceiling, freeing cash for premiums elsewhere. A constraint
  layer over raw xPts, not a substitute. Concentrate premiums in midfield; see
  [../methods/squad-construction.md#budget-allocation-shape](../methods/squad-construction.md#budget-allocation-shape).
- **Price/team-value momentum is weak as a points signal** — a lagging, herd-driven
  indicator. Net-transfer momentum predicts price *changes*, useful for team-value
  management and transfer *timing* (buy before a rise), not for xPts. Team value can
  compound ~£2–3m/season (with a 50% sell-tax), a late-season enabler — but elite
  managers **subordinate price to information** (many of their transfers-out had no
  price change; they forgo £0.1m gains for better team news)
  ([FF Fix — transfers](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/)).
- **Method:** use price/net-transfer prediction only in the transfer-timing / team-value
  module as a **tie-breaker**; keep it out of the core xPts objective to avoid chasing
  the herd.

Evidence tier: **[tier-1]** — value structural; price momentum a lagging signal.
