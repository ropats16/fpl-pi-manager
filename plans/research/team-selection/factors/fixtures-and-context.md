# Factors — fixtures, opponent & context

How the opponent, venue, and match context reshape a player's expected returns.
Full evidence: [../raw/cluster-B-fixtures.md](../raw/cluster-B-fixtures.md),
[../raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md),
[../raw/cluster-C-value-newaxes.md](../raw/cluster-C-value-newaxes.md).
Weights are suggested; see [../importance-ranking.md](../importance-ranking.md).

---

## Fixture difficulty done properly

**Suggested weight: HIGH — biggest lever after player quality; but replace naive FDR.**

- **The naive official FDR (1–5) is weak:** it collapses attack and defence into one
  number and ignores home/away (home teams score ~30% more)
  ([FPL Copilot](https://fplcopilot.com/blog/fpl-fixture-difficulty-rating);
  [FPL360](https://fpl360.com/2026/05/06/fpl-fixture-difficulty-rating-explained-use-fdr-for-better-transfers/)).
- **Method — split it in two, by position:** an opponent **defensive**-strength rating
  (for your attackers) and an opponent **attacking**-strength rating (for your DEF/GK),
  each from rolling xGF/xGA (recency-weighted) or **odds-implied team xG**, split
  home/away. Feed as the fixture term inside an xPts projection, not as a standalone
  score. The lag when a manager changes *is* the edge — weight recent form fast enough
  to catch it before the public FDR does
  ([Marcus Leadboot — FDR adjusted](https://medium.com/@marcusleadboot/fpl-fixture-difficulty-ratings-fdr-adjusted-for-attack-defence-6828a9713696)).
- **Reference implementation:** time-weighted **Dixon-Coles** (via `penaltyblog`) turns
  odds → goal expectancies → a scoreline matrix → clean-sheet & goals-conceded
  probabilities — the exact inputs GK/DEF points need. See
  [../methods/reference-pipelines.md#fixture--clean-sheet-layer](../methods/reference-pipelines.md#fixture--clean-sheet-layer).
- FPL Review reports a position + fixture model "far superior" to recent-goal data and
  more predictive than raw bookmaker-odds inference
  ([FPL Review](https://fplreview.com/a-goalscoring-model-more-predictive-than-inferrences-from-bookmakers/)).

Evidence tier: **[tier-1]**; Dixon-Coles method **[standard → use]**.

---

## Home / away

**Suggested weight: MED — real (~+0.25 goals) but shrinking; never zero.**

- Historically home teams won ~0.39 more pts and scored ~0.29 more goals per game;
  the COVID empty-stadium natural experiment nearly halved it (goal edge → ~0.15,
  away wins outnumbered home for the first time in PL history 2020/21) — clean causal
  evidence the crowd drives much of it
  ([Leeds](https://www.leeds.ac.uk/news-science/news/article/4894/how-empty-stadiums-affected-football-during-pandemic);
  [Significance](https://significancemagazine.com/home-advantage-whats-changed-since-covid/)).
  Current per-game home edge ≈ 0.25 goals and long-run declining.
- **Method:** apply a small venue multiplier (~+0.12–0.15 goals to home xG,
  symmetric away), team-specific, **not** a legacy flat value. Better: let the
  odds/xG-based fixture difficulty above carry the venue split natively — it's
  already priced in.

Evidence tier: **[tier-1]**.

---

## Head-to-head & matchup context

**Suggested weight: LOW — mostly narrative; small real signal in style-mismatch &
derbies, drowned in noise.**

- **Raw H2H has weak/negligible predictive power** — ~2 meetings/season means even a
  decade is ~20 games; records >5 years old are noise (different squads/managers).
  Team strength + current xG dominate
  ([Better World Master](https://www.betterworldmaster.com/blog/head-to-head-records.php);
  [MDPI Poisson](https://www.mdpi.com/2076-3417/14/16/7230)).
- **Method:** do **NOT** add an explicit H2H term to projections (overfitting risk).
  Capture opponent *style* at **team level** instead (press intensity/PPDA,
  defensive-block xGA profile from FBref) — which already feeds the fixture model
  above. Treat derby GWs as higher-**variance** (widen captaincy uncertainty), not
  higher-EV.

Evidence tier: **[tier-1]** (that it's mostly noise).

---

## Set-pieces & penalties

**Suggested weight: HIGH — penalty duty is one of the most reliable point-ceiling
boosters; verify the taker each season.**

- Penalties are near-free goals: Opta ~0.78 xG/pen, a chance quality virtually
  unattainable in open play; four-season PL conversion 81.9%. A lead taker on a
  penalty-winning side gains ~4 goals ≈ 16–20 FPL pts/season on top of open play
  ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal)).
- **Method:** maintain a per-club taker table (penalties, direct FKs, corners; **1st
  AND 2nd choice**), refreshed each GW; add an explicit boost to goal EV for the pen
  taker (~+0.05–0.08 goals/game) and a smaller corner/FK boost to assist EV. Downgrade
  **instantly** on taker change/injury — identity is volatile, so never hard-code.
- **Sourcing** (no single official feed): cross-reference FFS's per-club list,
  corroborate with Fantasy Football Fix / OneFPL, ground-truth against FBref/Understat
  penalty logs + the FPL API. Taker *identity is a current-season fact* → it belongs to
  the [#25](https://github.com/ropats16/fpl-pi-manager/issues/25) run, not this wiki.

Evidence tier: **[tier-1]** — best-quantified axis.

---

## Team style & usage share

**Suggested weight: HIGH — model the *system*, not just the player. Strong GW1 signal
(needs no current-season individual data).**

- A team's tactical structure drives the *distribution* of attacking returns: wide/
  cross-heavy sides inflate wingers & crossing full-backs; a new manager's system can
  restructure which roles accumulate points independent of transfers. Possession %
  alone is a trap ([thelivefootballapp](https://www.thelivefootballapp.com/football-stats-xg-possession/)).
- **Usage / share-of-chances (a basketball import):** prefer the player who takes a
  large **share** of his team's shots, box touches, and xG — a 45%-share player at a
  mediocre club can out-return a 20%-share player at an elite one. Standard FPL tooling
  surfaces per-90 rates, rarely share-of-team — this is a genuine gap
  ([raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md)).
- **Method:** classify each team by style archetype (possession vs counter; wing/cross
  vs central; high-press vs low-block) from FBref team profiles (crosses/90, PPDA proxy,
  shot-location share); map style → favoured positions; compute each attacker's npxG
  share / shot share / box-touch share. Penalise teams with *diffuse* output for
  captaincy.

Evidence tier: **[tier-1]**.

---

## Promoted-team fragility

**Suggested weight: MED — a fixture-quality prior available from GW1 with zero
current-season data.**

- Promoted sides systematically leak goals (Sheffield United 2023/24 conceded 2.66/game;
  relegation ≈ 60+ conceded). Structural, so it's a strong early-season signal
  ([CBS Sports](https://www.cbssports.com/soccer/news/premier-league-scoring-outbreak-explained-more-added-time-and-poor-defenses-means-more-goals);
  [FFS](https://www.fantasyfootballscout.co.uk/2026/07/28/fpl-promoted-teams-what-to-expect-from-hulls-defence)).
- **Method:** team-strength prior that boosts opponents' attacker & CS xPts vs promoted
  sides and discounts promoted attackers' floor — **with two exceptions**: survival-
  minded promoted **GKs** rack up save+bonus volume, and promoted **budget CBs** are the
  cheapest route to [DEFCON](scoring-dimensions.md#defensive-contribution-defcon) points.
  Their cheap defenders are otherwise value traps.

Evidence tier: **[tier-1]**.

---

## Congestion & days-rest

**Suggested weight: MED-HIGH during congestion; a rotation-risk filter always.**

- Two days' prep vs three cuts win probability materially; muscle/neuromuscular decline
  after congested periods is measurable; wide mids & strikers are rotated most around
  midweek European games
  ([Huddersfield study](https://www.hud.ac.uk/news/2020/november/football-fixture-congestion-new-study/);
  [ISSPF](https://www.isspf.com/articles/the-impact-of-fixture-congestion-on-elite-soccer-players/)).
- **Method:** encode a per-team days-rest and midweek-European flag each GW; fade
  starts/captaincy confidence on short turnarounds; treat "over-60-min last match +
  <72h rest" as an elevated rotation/blank flag. **International-break hangover** is the
  same mechanism: after a break, discount long-haul / two-full-internationals players'
  first GW (club/player-specific — Man City travel ~83k miles/window vs a low-travel
  side).

Evidence tier: **[tier-1]** (robust physiology).

---

## Referee tendencies

**Suggested weight: MED for penalties; LOW-MED for defender card risk — a tie-breaker.**

- Per-referee card and penalty rates vary large and persistently (~3 to ~5+ cards/match
  by official); VAR raised penalties and red-card risk
  ([tips.gg](https://tips.gg/article/most-cards-per-referee-in-the-epl-25-26-season/);
  [PMC VAR](https://pmc.ncbi.nlm.nih.gov/articles/PMC13044101/)).
- **Method:** for each fixture pull the appointed ref's penalty rate (boost the pen
  taker's EV under high-pen refs) and card rate (raise booking/red risk for aggressive
  DEF/DM under card-happy refs). Modest effect — a tie-breaker, not a driver. Ref
  appointment is public 2–3 days pre-match.

Evidence tier: **[tier-1]** (variance real); effect size modest.

---

## Game-state & script

**Suggested weight: MED — a ceiling shaper, not a primary selector.**

- **Method:** derive expected game state from match / over-under / handicap odds; nudge
  attacker ceilings up in expected lopsided/high-scoring games; favour target-men for
  expected chasers and pacey wingers for expected front-runners. Use as a captaincy
  ceiling modifier. Big favourites at home vs weak/promoted sides = highest expected
  game control → CS + goal ceiling
  ([raw/cluster-C-value-newaxes.md](../raw/cluster-C-value-newaxes.md)).

Evidence tier: **[tier-2]** — directional, interacts with role.
