# Cluster C — Value, Captaincy, Portfolio + Newly Discovered Axes

**Research date:** 2026-08-16. **Operative season: 2026/27** (project targets GW1 2026/27). Defensive-contribution (DEFCON) points were introduced 2025/26 and **remain in 2026/27**; the Bonus Points System (BPS) was re-tweaked again for 2026/27 (details below). Rules verified against official premierleague.com pages — the `fantasy.premierleague.com/help/rules` page is a JS SPA and could not be scraped directly, so official PL news pages were used as the primary substitute.

Weights below are on a **0–10 relative-importance scale** for a points-maximizing model, with a note on floor vs ceiling role.

---

## Cluster C axes

### 1. Price / value & differentials (points-per-million, budget allocation, template vs differential, effective ownership) — **Suggested weight: 7 (structural, not per-pick)**

- **Points-per-million (PPM / value) is a structural budget-allocation metric, not a raw ranking metric** — it decides where you *can* afford ceiling, freeing cash for premiums elsewhere; it is a constraint layer over raw xPts, not a substitute for it. [PL glossary](https://www.premierleague.com/en/news/2683145)
- **Effective Ownership (EO) reframes every pick as a rank decision, not an absolute-points decision.** At high EO the "obvious" pick is a low-EV *rank* move because most rivals also own it — so a high-xPts template player can still be a poor differential. [FPL Oracle — Effective Ownership](https://fploracle.team/blog/effective-ownership-fpl), [FFS — using EO for differential decisions](https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions)
- **Differentials are +EV specifically when chasing rank / behind the field**, and template is +EV when protecting rank / ahead. A common decision rule: differentiate when the low-EO alternative's xPts is within ~1.5 of the favourite; stay template only if the EV gap is ≥2. [FPL Oracle — Template vs Differentials EO math](https://fploracle.team/blog/template-vs-differential-fpl)
- **Best-practice structure is a hybrid: template core + differential edge** (esp. at captain/1–2 squad slots), rather than an all-template or all-differential portfolio. [FPL Oracle — Template vs Differentials](https://fploracle.team/blog/template-vs-differential-fpl)
- **Contested/thin:** exact EO thresholds are rules-of-thumb from analytics blogs, not peer-reviewed; they shift with your rank and time of season.
- **How to apply:** Treat PPM as a budget constraint that maximizes total squad xPts subject to £100m; then apply an EO-adjusted objective — reward = xPts − (EO/100 × field_xPts) when the manager is chasing rank, and shrink toward raw xPts when protecting. Make differential aggressiveness a tunable function of current rank/gap-to-target.

### 2. Captaincy expected value (2x / 3x triple-captain) — **Suggested weight: 9 (single biggest weekly swing)**

- **The armband is the largest single weekly lever** — captaincy carries roughly 2–3× the EV impact of a routine (non-emergency) transfer, because points are doubled (tripled with the Triple Captain chip). [FPL Oracle — Captaincy framework](https://fploracle.team/blog/fpl-captaincy-strategy), [SmartPlay — how the model picks a captain](https://smartplayfpl.com/blog/how-the-model-picks-your-captain)
- **Pick by expected points (xPts)**, built from minutes probability, shot/chance quality (xG), chance-creation (xA), clean-sheet prob, fixture, and bonus patterns. The highest-xPts baseline quantifies exactly how much a differential armband is "costing." [FPL Copilot — xPts explained](https://fplcopilot.com/blog/expected-points-explained), [FPL Oracle](https://fploracle.team/blog/fpl-captaincy-strategy)
- **Odds-implied EV is a strong, cheap captain signal:** shortening anytime-goalscorer odds ⇒ higher return likelihood; sub-evens (e.g. 1.83) flags a prime captain. Convert bookmaker odds → implied probability → expected FPL points. [FPLGameweek — betting odds for captaincy](https://www.fplgameweek.com/articles/how-betting-odds-can-inform-your-fpl-captaincy-choices/), [FPLGameweek — odds explained](https://www.fplgameweek.com/articles/fpl-odds-explained-how-betting-markets-can-guide-your-fantasy-decisions/)
- **Ceiling vs floor is EO-dependent:** captain the highest-xPts template player to protect rank; captain a lower-EO high-ceiling player to *gain* rank (differential captain pays off only when it hauls). Use the xPts gap to the template captain as the price of the punt. [FPLGameweek — captaincy decisions that win weeks](https://www.fplgameweek.com/articles/captaincy-decisions-that-quietly-win-fpl-weeks/), [FPL Oracle](https://fploracle.team/blog/fpl-captaincy-strategy)
- **How to apply:** Captain = argmax of a blended captain-xPts (model xPts × odds-implied goal/assist prob), then apply an EO/rank penalty: subtract a rank-risk term for high-EO picks when chasing and add one when protecting. Gate all captain candidates on minutes probability first. Reserve Triple Captain for a double-gameweek / elite fixture with the highest ceiling.

---

## Newly discovered axes

### A. Defensive Contribution (DEFCON / CBIT) targeting — **Suggested weight: 7 (raises floor of cheap defenders & holding mids)** — VERIFIED OFFICIAL RULE

- **Official 2025/26 rule, still active 2026/27:** a **defender** earns **+2 pts** for **10+ combined clearances, blocks, interceptions, tackles (CBIT)** in a match; a **midfielder/forward** earns **+2 pts** for **12+ actions including ball recoveries (CBIRT)**. Capped +2/match. Goalkeepers not eligible. [PL — all changes 2025/26](https://www.premierleague.com/en/news/4362211/all-you-need-to-know-about-changes-to-fantasy-for-202526), [PL — what's new 2025/26](https://www.premierleague.com/en/news/4373187/whats-new-for-202526-changes-in-fantasy-premier-league), [Opta Analyst — DEFCON best picks](https://theanalyst.com/articles/fpl-defensive-contributions-2025-26-best-picks)
- **It materially changed asset value:** cheap defensive workhorses (centre-backs, ball-winning mids) now routinely out-score pricier attackers on floor. Targeting DEFCON adds ~3–4 xPts/week to previously dead budget-defender slots, compounding to 100+ pts/season. [Ingenuity Fantasy — DefCon defenders 2026/27](https://ingenuityfantasy.com/game-week-tips/the-best-fpl-defcon-picks-for-2026-27-defenders/), [Statz — DEFCON](https://blog.statz.ai/fpl-defensive-contributions/)
- **Actionable metric = threshold-hit rate, not season total:** % of starts crossing the CBIT/CBIRT line. Analysts set **>50% hit-rate** as the minimum bar to pick a player *for* DEFCON. (e.g. Lacroix ~57%, 10.79 CBIT/90; Tarkowski highest CBIT/90 24/25, 44 DC pts across 25/26.) [Ingenuity Fantasy](https://ingenuityfantasy.com/game-week-tips/the-best-fpl-defcon-picks-for-2026-27-defenders/), [WhoScored — best defenders 26/27](https://www.whoscored.com/articles/4LNanxZgwESAYZPtlq0-4Q/show/fpl-tips-10-best-defenders-to-pick-ahead-for-the-202627-season)
- **Caveat:** DEFCON should augment, not replace, clean-sheet prob / attacking threat / minutes; don't sacrifice CS probability chasing it. [Ingenuity Fantasy](https://ingenuityfantasy.com/game-week-tips/the-best-fpl-defcon-picks-for-2026-27-defenders/)
- **How to apply:** Compute per-player CBIT/90 (def) or CBIRT/90 (mid/fwd) and a **binomial threshold-hit probability** per match; add 2 × P(hit) to xPts. Only weight heavily for players with >50% historical hit-rate and secure minutes. Prefer high-volume centre-backs and deep-lying/holding midfielders.

### B. Bonus Points System (BPS) targeting — **Suggested weight: 5 (meaningful floor/ceiling add-on)** — VERIFIED OFFICIAL RULE

- **BPS = Opta-driven performance score; top 3 in a match get +3/+2/+1.** [PL — BPS 2025/26](https://www.premierleague.com/en/news/4362127/whats-new-in-202526-fantasy-changes-to-bonus-points-system)
- **2026/27 BPS changes materially shift who wins bonus** (verify these are the current rules): (1) **removed the −1 BPS for being tackled** — helps dribble-heavy wingers/full-backs; (2) **CBI ratio worsened from 1 BPS/2 CBI to 1 BPS/3 CBI** — reduces centre-back bonus dominance; (3) **GK saves restructured** — 2 BPS any save, +1 for inside-box, **+1 new "big chance" save**; **penalty save cut 8→7 BPS**. Stated aim: limit crossover between DEFCON and bonus. [PL — what's new 2026/27 BPS](https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system), [FFS — BPS tweaks effect](https://www.fantasyfootballscout.co.uk/2026/07/21/how-fpls-new-bonus-points-system-tweaks-would-have-affected-2025-26)
- **Penalty goals = 12 BPS regardless of position; goals/assists/CS still dominate BPS** — so BPS mostly correlates with the returns you already model, but tie-breaks toward high-involvement, penalty-taking, save-volume players. [Flashscore — new BPS explained](https://www.flashscore.co.uk/news/football-premier-league-new-fpl-bonus-points-system-for-2025-26-season-explained/0E5pSeKj/)
- **How to apply:** Add an expected-bonus term (0–3) estimated from a player's BPS-driver profile (goal/assist involvement, penalties, save volume for GKs, dribbles for wingers post-2026/27). Don't double-count with DEFCON. Low standalone weight — it's mostly a refinement on players already high in xPts.

### C. Goalkeeper save points & shot-stopping volume — **Suggested weight: 4 (position-specific)**

- **1 pt / 3 saves; +5 for a penalty save (none if the penalty is off-target).** [FPL Squid — GK points](https://fplsquid.com/blog/how-do-goalkeeper-points-work-in-fpl), [Official FPL tweet — no save pts if off target](https://x.com/OfficialFPL/status/863383889162665984)
- **Creates two distinct GK archetypes:** clean-sheet keepers behind elite defences vs **save-volume keepers behind shaky defences** who bank points even in defeats — value often lives in the latter, esp. cheap enablers. [WhoScored — best GKs 26/27](https://www.whoscored.com/articles/d83gMmpMeEmlAarfeyObow/show/fpl-tips-5-best-goalkeeper-picks-for-premier-league-season), [Full90 — points explained](https://full90fpl.com/fpl-points-explained/)
- **How to apply:** For GKs, xPts = CS-prob term + (expected shots-on-target-faced / 3) save term + penalty-save upside. Model opponent shot volume / team xGA explicitly; a high-xGA team's keeper can be a strong cheap pick even with low CS prob.

### D. Rotation / minutes-security ("nailed-ness") & European congestion — **Suggested weight: 8 (gate/multiplier on everything)**

- **Minutes are the master gate:** no minutes ⇒ no returns; a nailed starter is the precondition for every other axis. Track **rolling minutes**; sudden drops (45→26→18) flag rotation. [FPLForm glossary](https://fplform.com/fpl-glossary), [FPL101 — rotation risk](https://fpl101.com/articles/rotation-risk/)
- **Congestion multiplies rotation risk:** Christmas/New-Year (up to 4 games/10 days), international breaks, and **pre-Champions-League league games** where big-six managers rest starters. Squad-depth clubs (Arsenal/City) rotate more. "Pep/Maresca roulette" is the canonical unpredictable case. [FIso — Haaland minutes graphs](https://www.fiso.co.uk/erling-haaland-minutes-played-graphs-for-anticipating-pep-rotation-in-fpl/), [PremierFantasyTools — CL rotation](https://www.premierfantasytools.com/maximising-your-fpl-strategy-amidst-champions-league-fixtures/), [PL — handling congestion](https://www.premierleague.com/en/news/3787690)
- **How to apply:** Multiply every player's raw xPts by P(start) × E(minutes|start)/90, estimated from rolling minutes + injury/suspension flags + fixture-congestion calendar (flag European clubs in midweek weeks). Prefer nailed players when EV is close; down-weight rotation-prone assets in congested gameweeks.

### E. Game-state / expected game script — **Suggested weight: 5 (ceiling shaper)**

- **Projected scoreline shape changes which player type returns:** expected blowouts and open games lift attacking ceilings; a team **going ahead** opens space for fast wingers on the break, a team **chasing / behind** funnels crosses to tall target-men. [Tipsterspredicts — game state & scoring](https://tipsterspredicts.com/how-game-state-influences-scoring-patterns-the-hidden-data-guiding-football-tactics-and-betting/), [RotoWire — best attacking fixtures](https://www.rotowire.com/soccer/article/fpl-gw-18-best-attacking-fixtures-teams-to-target-liverpool-man-utd-101276)
- **Big favourites at home vs weak/promoted sides = highest expected game control ⇒ CS + goal ceiling.** Ties into odds (match-result & over/under markets encode expected game state).
- **Contested/thin:** game-script effects are directional and interact heavily with player role; weaker as a standalone signal than minutes/odds.
- **How to apply:** Derive expected game state from match/over-under/handicap odds; nudge attacker ceilings up in expected high-scoring/lopsided games, favour target-men for expected chasers and pacey wingers for expected front-runners. Use as a ceiling modifier on captaincy candidates, not a primary selector.

### F. Transfer-market signals (price momentum, ownership momentum, "eye test") — **Suggested weight: 3 (team-value / timing, weak points signal)**

- **Net-transfer momentum predicts price rises/falls** (thresholds scale with ownership: ~30k net for a 1%-owned player vs hundreds of thousands for 30%-owned). Predictive value for *price* is moderate-but-real; damped and noisy early season. [Tipmaster — price algorithm](https://www.tipmaster.de/en-gb/guide/fpl-price-changes-explained-how-the-algorithm-actually-works/), [LiveFPL — price changes](https://livefpl.com/blog/fpl-price-changes), [PL — how prices change](https://www.premierleague.com/en/news/2858775)
- **Ownership momentum ≠ points signal:** the crowd is a lagging, herd-driven indicator; useful for **team-value management and transfer timing** (buy before a rise), and as a mild prior via "eye test" corroboration, not as an independent xPts input. [PremierFantasyTools — spotting value early](https://www.premierfantasytools.com/how-fpl-managers-spot-value-before-everyone-else-does/)
- **How to apply:** Use net-transfer/price-delta prediction only for the transfer-timing/team-value module (act before rises, sell before falls). Keep it out of the core xPts objective to avoid chasing the herd; at most a small tie-break prior.

### G. Promoted-team fragility / opponent-quality prior — **Suggested weight: 4 (fixture-quality input)**

- **Newly promoted sides are systematically weaker defensively** (all three staying up is rare — twice in a decade), making their fixtures prime attacking/CS targets for opponents; their own attackers are lower-floor. [FiveThirtyEight — promoted teams](https://fivethirtyeight.com/features/the-newly-promoted-premier-league-teams-are-playing-like-they-belong), [FFS — Hull defence 26/27](https://www.fantasyfootballscout.co.uk/2026/07/28/fpl-promoted-teams-what-to-expect-from-hulls-defence)
- **But two exploitable pockets:** (1) survival-minded promoted keepers rack up **save + bonus** volume; (2) promoted **budget centre-backs are the cheapest route to DEFCON points** (e.g. Hull's Charlie Hughes at the price floor). [FFS — Ipswich defence](https://www.fantasyfootballscout.co.uk/2026/08/05/fpl-promoted-teams-who-appeals-in-ipswichs-defence), [Ingenuity Fantasy](https://ingenuityfantasy.com/game-week-tips/the-best-fpl-defcon-picks-for-2026-27-defenders/)
- **How to apply:** Add a team-strength prior (promoted/weak-team flag) that boosts opponents' attacker & CS xPts and discounts promoted attackers' floor — while separately flagging promoted GKs (save volume) and promoted budget CBs (DEFCON value) as exceptions.

### H. Expected-assist *source* (open-play vs set-play) — **Suggested weight: 3 (sustainability refinement on xA)**

- **Not all xA is equally repeatable:** set-piece-derived xA depends on corner/FK volume, delivery role and aerial targets (can inflate/be fragile if the taker role changes); open-play xA signals structural centrality to the attack and is generally more robust. [FPL Toolbox — xG/xA to pick players](https://fpltoolbox.com/blog/dont-make-uninformed-decisions-using-expected-goals-xg-and-expected-assists-xa-to-pick-fpl-players/), [Opta Analyst — set-piece takers 26/27](https://theanalyst.com/articles/fpl-set-piece-stats-projections-tips-premier-league-2026-27)
- **Assists − xA overperformance is teammate-finishing-dependent and mean-reverts** — decompose to avoid overpaying for unsustainable returns. [FPL Feed — xG/xA overperformance 24/25](https://fplfeed.substack.com/p/fpl-analysis-over-performance-in)
- **How to apply:** When available, split a creator's xA into set-play vs open-play; keep open-play xA at near-full weight and haircut set-play xA by set-piece-role security (confirmed taker? competition for the role?). Treat as a sustainability adjustment layered on the existing xA axis, not a new primary axis.

---

## Sources

Official / rules (primary):
- https://www.premierleague.com/en/news/4362211/all-you-need-to-know-about-changes-to-fantasy-for-202526
- https://www.premierleague.com/en/news/4373187/whats-new-for-202526-changes-in-fantasy-premier-league
- https://www.premierleague.com/en/news/4362127/whats-new-in-202526-fantasy-changes-to-bonus-points-system
- https://www.premierleague.com/en/news/4679946/whats-new-in-202627-fantasy-changes-to-bonus-points-system (2026/27 BPS changes)
- https://www.premierleague.com/en/news/2683145 (FPL glossary)
- https://www.premierleague.com/en/news/2858775 (price changes)
- https://www.premierleague.com/en/news/3787690 (fixture congestion)
- https://x.com/OfficialFPL/status/863383889162665984 (no save pts on off-target pen)

Tier-1 analytics / established FPL community:
- https://theanalyst.com/articles/fpl-defensive-contributions-2025-26-best-picks (Opta)
- https://theanalyst.com/articles/fpl-set-piece-stats-projections-tips-premier-league-2026-27 (Opta)
- https://www.fantasyfootballscout.co.uk/2021/03/07/how-to-use-effective-ownership-to-make-differential-fpl-decisions
- https://www.fantasyfootballscout.co.uk/2026/07/21/how-fpls-new-bonus-points-system-tweaks-would-have-affected-2025-26
- https://www.fantasyfootballscout.co.uk/2026/07/28/fpl-promoted-teams-what-to-expect-from-hulls-defence
- https://www.fantasyfootballscout.co.uk/2026/08/05/fpl-promoted-teams-who-appeals-in-ipswichs-defence
- https://fivethirtyeight.com/features/the-newly-promoted-premier-league-teams-are-playing-like-they-belong

Analytics blogs / tools (secondary, cross-referenced):
- https://fploracle.team/blog/effective-ownership-fpl
- https://fploracle.team/blog/template-vs-differential-fpl
- https://fploracle.team/blog/fpl-captaincy-strategy
- https://fplcopilot.com/blog/expected-points-explained
- https://smartplayfpl.com/blog/how-the-model-picks-your-captain
- https://www.fplgameweek.com/articles/how-betting-odds-can-inform-your-fpl-captaincy-choices/
- https://www.fplgameweek.com/articles/fpl-odds-explained-how-betting-markets-can-guide-your-fantasy-decisions/
- https://www.fplgameweek.com/articles/captaincy-decisions-that-quietly-win-fpl-weeks/
- https://ingenuityfantasy.com/game-week-tips/the-best-fpl-defcon-picks-for-2026-27-defenders/
- https://blog.statz.ai/fpl-defensive-contributions/
- https://www.whoscored.com/articles/4LNanxZgwESAYZPtlq0-4Q/show/fpl-tips-10-best-defenders-to-pick-ahead-for-the-202627-season
- https://www.whoscored.com/articles/d83gMmpMeEmlAarfeyObow/show/fpl-tips-5-best-goalkeeper-picks-for-premier-league-season
- https://fplsquid.com/blog/how-do-goalkeeper-points-work-in-fpl
- https://full90fpl.com/fpl-points-explained/
- https://fpl101.com/articles/rotation-risk/
- https://fplform.com/fpl-glossary
- https://www.fiso.co.uk/erling-haaland-minutes-played-graphs-for-anticipating-pep-rotation-in-fpl/
- https://www.premierfantasytools.com/maximising-your-fpl-strategy-amidst-champions-league-fixtures/
- https://www.premierfantasytools.com/how-fpl-managers-spot-value-before-everyone-else-does/
- https://tipsterspredicts.com/how-game-state-influences-scoring-patterns-the-hidden-data-guiding-football-tactics-and-betting/
- https://www.rotowire.com/soccer/article/fpl-gw-18-best-attacking-fixtures-teams-to-target-liverpool-man-utd-101276
- https://www.tipmaster.de/en-gb/guide/fpl-price-changes-explained-how-the-algorithm-actually-works/
- https://livefpl.com/blog/fpl-price-changes
- https://fpltoolbox.com/blog/dont-make-uninformed-decisions-using-expected-goals-xg-and-expected-assists-xa-to-pick-fpl-players/
- https://fplfeed.substack.com/p/fpl-analysis-over-performance-in
- https://www.flashscore.co.uk/news/football-premier-league-new-fpl-bonus-points-system-for-2025-26-season-explained/0E5pSeKj/
