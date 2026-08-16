# Factors — scoring dimensions (2026/27 rules)

Axes that exist because of the FPL scoring rules themselves — verified against
official Premier League pages for **2026/27**. These reprice whole player
archetypes and are easy to under-model. Full evidence:
[../raw/cluster-C-value-newaxes.md](../raw/cluster-C-value-newaxes.md),
[../raw/discovery-practitioner.md](../raw/discovery-practitioner.md),
[../raw/discovery-quant.md](../raw/discovery-quant.md).

---

## Defensive contribution (DEFCON)

**Suggested weight: HIGH — raises the floor of cheap defenders & holding mids; a
genuine value-shifter.**

- **Official rule (2025/26, retained 2026/27):** a **defender** earns **+2** for
  **10+ CBIT** (clearances, blocks, interceptions, tackles); a **midfielder/forward**
  earns **+2** for **12+ CBIRT** (adds ball recoveries). Capped +2/match. GKs excluded
  ([PL — changes for 2025/26](https://www.premierleague.com/en/news/4362211/all-you-need-to-know-about-changes-to-fantasy-for-202526);
  [PL — DEFCON 2026/27](https://www.premierleague.com/en/news/4361991/whats-happening-with-defensive-contribution-points-in-202627-fantasy)).
- **Method:** compute per-player **CBIT/90 (DEF)** or **CBIRT/90 (MID/FWD)** and a
  **binomial threshold-hit probability** per match; add `2 × P(hit)` to xPts. Only
  weight heavily for players with **>~50% historical hit-rate** and secure minutes.
  Prefer high-volume centre-backs and deep-lying/holding midfielders.
- **Impact:** ~3–4 xPts/week added to previously-dead budget slots; of the top-10 DEFCON
  accumulators in 2025/26, 5 were CBs and 5 were DMs. Makes 4-4-2 competitive and
  revives defensive-mids as an archetype
  ([Opta Analyst](https://theanalyst.com/articles/fpl-defensive-contributions-2025-26-best-picks);
  [FPL Oracle](https://fploracle.team/blog/defensive-contributions-fpl-explained)).
- **Caveats:** augment, don't replace, clean-sheet prob / attacking threat / minutes.
  The **2026/27 BPS rework** trims CB double-dipping (see below), so lean slightly toward
  DMs for the DEFCON+bonus stack.

Evidence tier: **[proven]** — official rule + Opta best-picks data.

---

## Bonus points system (BPS)

**Suggested weight: MED — meaningful (15–20% of a season's total) but rule-volatile.**

- BPS is an Opta-driven within-match performance score; top 3 get +3/+2/+1. Goals/
  assists/CS/penalties dominate it, so it mostly correlates with returns you already
  model — but it tie-breaks toward high-involvement, penalty-taking, save-volume players
  ([PL — BPS](https://www.premierleague.com/en/news/4362127/whats-new-in-202526-fantasy-changes-to-bonus-points-system)).
- **2026/27 changes (verified):** removed −1 for being tackled (helps dribble-heavy
  wingers/full-backs); CBI ratio worsened 1/2 → 1/3 (reduces CB bonus dominance); GK
  saves restructured (2 BPS/save, +1 inside-box, +1 new "big-chance" save; penalty save
  8→7). Stated aim: limit DEFCON/bonus double-dipping
  ([PL — 2026/27 BPS](https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system)).
- **Method:** add an expected-bonus term (0–3) estimated from a player's BPS-driver
  profile, modelled as a **within-match rank** of BPS components (not a per-player
  constant). **Refit BPS weights to the current ruleset** — a model trained on old
  seasons is miscalibrated. Don't double-count with DEFCON. Low standalone weight — a
  refinement on players already high in xPts.

Evidence tier: **[proven]** rule; combination method **[candidate → evaluate]**.

---

## Goalkeeper save volume

**Suggested weight: MED — position-specific value archetype.**

- 1 pt / 3 saves; +5 for a penalty save (none if off-target). Creates two GK archetypes:
  clean-sheet keepers behind elite defences vs **save-volume keepers behind shaky
  defences** who bank points even in defeats — value often lives in the latter, cheap
  ([FPL Squid](https://fplsquid.com/blog/how-do-goalkeeper-points-work-in-fpl);
  [WhoScored](https://www.whoscored.com/articles/d83gMmpMeEmlAarfeyObow/show/fpl-tips-5-best-goalkeeper-picks-for-premier-league-season)).
- **Method:** `GK xPts = CS-prob term + (E[shots-on-target-faced] / 3) save term +
  penalty-save upside`. Model opponent shot volume / team xGA explicitly; a high-xGA
  team's keeper can be a strong cheap pick even with low CS prob. Ties to
  [promoted-team fragility](fixtures-and-context.md#promoted-team-fragility) (promoted
  GKs = save volume).

Evidence tier: **[tier-1]**.

---

Squad-level consequences of these axes (formation, budget, bench) live in
[../methods/squad-construction.md](../methods/squad-construction.md).
