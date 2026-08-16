# Importance ranking — all decision axes

The money page for [#25](https://github.com/ropats16/fpl-pi-manager/issues/25).
Every decision axis surfaced by [#24](https://github.com/ropats16/fpl-pi-manager/issues/24)
— the seed axes **and** the ones the open-ended discovery agents found — ranked by
suggested importance, **method-first** (what it *does* / how it's used, not just
that it matters). Weights are SUGGESTED and non-binding; the gaffer weighs by
judgment per decision and may overrule any row (see
[the GW1 approach note](../../gw1/approach.md)).

Columns: **Axis** · **Tier** (suggested weight) · **How it's used** (the method,
one line) · **Evidence** ([proven]/[standard]/[tier-1]/[tier-2/folklore]) ·
**Page**.

Legend for the evidence gate (see [CONVENTIONS.md](CONVENTIONS.md)): the *method*
tags **[proven → adopt] / [standard → use] / [candidate → evaluate]** live on the
method pages; here the Evidence column notes the strength of the axis's supporting
research.

---

## Tier 0 — the gate (applied before any EV)

| Axis | How it's used | Evidence |
|---|---|---|
| **Minutes / xMins / nailedness** | Master multiplicative gate: `EV_final = P(start) × E(min)-adjusted EV`; hard-drop below a start-prob floor regardless of how good the EV looks. Model via the 60-min scoring kink (P(start), P(60+)), not a linear minutes fraction. | [proven] — every serious model gates on it; OpenFPL's weakness is concentrated exactly where minutes are unknown |

Page: [factors/predictive-signals.md#minutes--xmins](factors/predictive-signals.md#minutes--xmins) ·
sourcing: [data-sources › player availability](sources/data-sources.md#player-availability-the-highest-leverage-deadline-pull)

---

## Tier 1 — high (primary drivers)

| Axis | How it's used | Evidence | Page |
|---|---|---|---|
| **Betting odds (de-vigged)** | Convert clean-sheet / anytime-scorer / 1X2 odds → fair probabilities (strip overround: multiplicative for 1X2, Shin/power for skewed scorer/CS markets); use directly for CS & goal EV. Treat the **closing line as the prior your model must beat**, not echo. | [tier-1] — odds well-calibrated, improving; academic + betting lit | [predictive-signals](factors/predictive-signals.md#betting-odds) |
| **xG / xA (underlying talent)** | Use per-90 xG/xA (shrunk by shot volume) as the finishing/creation estimator that feeds goal & assist EV, in preference to raw past FPL points. | [tier-1] — xG stabler & more predictive than past goals (ElHabr, StatsBomb) | [predictive-signals](factors/predictive-signals.md#xg--xa) |
| **Fixture difficulty (done properly)** | Replace naive 1–5 FDR with **two** position-split ratings — opponent defensive strength (for your attackers) and attacking strength (for your DEF/GK) — built from rolling xGF/xGA or odds-implied team xG, split home/away. | [tier-1] — FPL Review model beats raw-goal & odds inference; Dixon-Coles standard | [fixtures-and-context](factors/fixtures-and-context.md#fixture-difficulty-done-properly) |
| **Class-player prior** | Bayesian shrinkage: `posterior = (κ·μ₀ + n·x̄)/(κ+n)`, μ₀ = 2–3-season minutes-weighted xGI/90 + role + ceiling, κ large for long consistent histories. Keeps a quiet-friendly Haaland priced as Haaland. | [standard] — James–Stein / empirical Bayes; 13.8–17.2% MSE gain in data-limited settings | [class-player-prior](class-player-prior.md) |
| **Set-pieces & penalties** | Add an explicit boost to goal EV for the confirmed penalty taker (~0.78 xG/pen; a lead taker ≈ +4 goals/season) and to assist EV for corner/FK takers. Track 1st **and** 2nd choice; re-verify each season. | [tier-1] — Opta penalty xG/conversion | [fixtures-and-context](factors/fixtures-and-context.md#set-pieces--penalties) |
| **Captaincy EV** | Single biggest weekly swing (~15–20% of score variance). `argmax` of blended captain-xPts (model × odds-implied goal prob), gated on minutes, then an EO/rank adjustment (template to protect, differential to climb). | [tier-1] — variance decomposition; odds-implied EV | [value-and-ownership](factors/value-and-ownership.md#captaincy-ev) |
| **Effective ownership / rank objective** | FPL is relative: optimise `xPts − EO·field_xPts` (or expected rank), not raw xPts. EO = start% + captain%. Not owning a 90%-EO haul is a rank loss even when your score is fine. | [tier-1] — EO framework; game-theoretic | [value-and-ownership](factors/value-and-ownership.md#effective-ownership--the-rank-objective) |
| **Defensive contribution (DEFCON)** | 2026/27 rule: +2 for DEF ≥10 CBIT / MID·FWD ≥12 CBIRT. Model as `2 × P(hit)` via a per-match binomial on CBIT/90; pick only >~50% hit-rate players. Reprices cheap DEF & holding mids. | [proven] — official rule; Opta best-picks data | [scoring-dimensions](factors/scoring-dimensions.md#defensive-contribution-defcon) |
| **Squad construction / budget shape** | Balanced-strategic, not stars-and-scrubs: top-50 ≈ 41% MID / 30% FWD / 23% DEF / 6% GK (effective budget); concentrate premiums in **midfield**. Let the optimizer objective (below) place them. | [tier-1] — top-50 budget data | [squad-construction](methods/squad-construction.md) |
| **Optimizer objective** | Multi-period MILP: decay-weighted + captain-doubled + bench-weighted xPts, each scaled by P(start). Push DEFCON/minutes into the *scores*, keep rules as hard constraints — structure emerges from valuation. | [proven] — sertalpbilal solver, arXiv 2505.02170 MILP | [squad-construction](methods/squad-construction.md#optimizer-objective--constraints) |
| **Signal synthesis (how axes combine)** | Bucket correlated signals (odds already ≈ xG+home/away+fixtures), combine one-per-bucket by near-equal / inverse-variance **linear** pool, recalibrate, gate on minutes. **Do not learn "optimal" weights** on <2 seasons. | [standard] — forecast-combination puzzle, opinion pooling | [signal-synthesis](methods/signal-synthesis.md) |
| **Multi-week planning horizon** | Optimise cumulative xPts over a rolling 5–6 GW window; a −4 hit must clear >4 pts over ~3–4 GWs; value banking FTs (cap 5) and fixture *swings*, not one-week spikes. | [proven/tier-1] — solver horizon; top-50 hit discipline | [meta-and-timing](factors/meta-and-timing.md#multi-week-planning-horizon) |
| **Chip timing** | Schedule chips to the fixture calendar (WC before a swing → BB on the DGW → FH on the blank). Timing worth ~+49 pts/season; *choice* only ~3. Machinery to build now, bites from ~GW4+. | [tier-1] — top-50 chip study | [meta-and-timing](factors/meta-and-timing.md#chip-strategy--timing) |
| **Team style / usage share** | Classify each team's tactical archetype (wing/cross vs central, press vs low-block) and prefer the player who owns a large **share** of his team's shots/xG, not just high per-90. Strongest kind of GW1 signal (no current-season data needed). | [tier-1] — FBref style data; "usage" import | [fixtures-and-context](factors/fixtures-and-context.md#team-style--usage-share) |
| **Whole-XI covariance** | Judge the XI's *distribution*, not the sum of 11 means: same-team/same-match returns covary. Raise stacking (to the max-3 cap) when chasing rank; diversify across matches when protecting. | [tier-1] — variance/MC sim tools | [value-and-ownership](factors/value-and-ownership.md#whole-xi-covariance--portfolio-variance) |

---

## Tier 2 — medium

| Axis | How it's used | Evidence | Page |
|---|---|---|---|
| **Home / away** | Small venue multiplier (~+0.25 goals to home xG, and shrinking) — better still, let odds/xG fixture difficulty carry the split natively since it's already priced. | [tier-1] — COVID natural experiment | [fixtures-and-context](factors/fixtures-and-context.md#home--away) |
| **Form recency** | Mild geometric decay over ~4–6 games on *underlying* metrics (xG/xA/minutes), never on raw points; always regress toward the season mean. | [tier-1] — recency real but regresses hard | [predictive-signals](factors/predictive-signals.md#form-recency) |
| **Finishing over/under-performance** | Fade signal: rank on xG, treat goals ≫ xG as a sell (regression coming), goals ≪ xG as a buy. Keep a whitelist of multi-season proven outperformers. | [tier-1] — GAX doesn't persist (KU Leuven, ASA) | [predictive-signals](factors/predictive-signals.md#finishing-overunder-performance) |
| **BPS targeting** | Expected-bonus term from a player's BPS-driver profile (goals/assists/penalties, save volume, dribbles post-2026/27). Refit weights to the *current* ruleset; don't double-count with DEFCON. | [proven] — official rule (2026/27 reworked) | [scoring-dimensions](factors/scoring-dimensions.md#bonus-points-system-bps) |
| **GK save-volume archetype** | For GKs, `xPts = CS term + E(shots-on-target/3) + pen-save upside`; a high-xGA team's keeper can be a strong cheap pick even with low CS prob. | [tier-1] — 1pt/3 saves rule + shot-volume | [scoring-dimensions](factors/scoring-dimensions.md#goalkeeper-save-volume) |
| **Game-state / game script** | Derive expected game state from match/OU/handicap odds; nudge attacker ceilings up in lopsided games; favour target-men for expected chasers, pacey wingers for front-runners. Ceiling modifier, not a primary selector. | [tier-2] — directional | [fixtures-and-context](factors/fixtures-and-context.md#game-state--script) |
| **Promoted-team fragility** | Team-strength prior: boost opponents' attack & CS vs promoted sides; discount promoted attackers' floor — but flag their save-volume GKs and cheap DEFCON CBs as exceptions. Structural, available from GW1. | [tier-1] — base-rate concession data | [fixtures-and-context](factors/fixtures-and-context.md#promoted-team-fragility) |
| **Transfer discipline** | Default to *deferring* transfers to just before deadline (post-team-news); target players trending up in underlying stats while still low-owned; penalise buying on last-GW hauls (counter-momentum). | [tier-1] — top-50 transfer logs | [meta-and-timing](factors/meta-and-timing.md#transfer-discipline) |
| **DGW / BGW planning** | Ingest FA-Cup / European progression to *forecast* doubles/blanks weeks ahead and pre-position transfers/chips, rather than reacting to the reschedule announcement. | [tier-1] — cup-progression method | [meta-and-timing](factors/meta-and-timing.md#dgw--bgw-planning) |
| **Congestion & days-rest** | Per-team days-rest + midweek-European flag each GW; fade starts/captaincy confidence on short turnarounds; "over-60-min last match + <72h rest" = elevated rotation/blank risk. | [tier-1] — fatigue physiology | [fixtures-and-context](factors/fixtures-and-context.md#congestion--days-rest) |
| **Decision-timing option value** | Treat "wait for team news" as a valued action: stage decisions, finalise as late as responsibly possible (deadline is T-90min; **no confirmed XIs exist at lock time**). | [standard] — CLV / information arrival | [meta-and-timing](factors/meta-and-timing.md#decision-timing-option-value) |
| **Bench order & autosubs** | Order bench each GW by `P(0 min) × xPts-if-plays` respecting formation; choose formation that maximises *realised* points incl. autosub option value. Free but small (~5–10 pts/season). | [tier-1] — autosub mechanics | [squad-construction](methods/squad-construction.md#bench--gk-strategy) |
| **Referee tendencies** | Per-fixture: appointed ref's penalty rate (boost pen-taker EV) and card rate (raise booking/red risk for aggressive DEF/DM). Modest tie-breaker. | [tier-1] — per-ref variance real | [fixtures-and-context](factors/fixtures-and-context.md#referee-tendencies) |

---

## Tier 3 — low / secondary

| Axis | How it's used | Evidence | Page |
|---|---|---|---|
| **Head-to-head (raw history)** | **Do not** add an explicit H2H term (overfits noise; ~20 games/decade). Capture opponent *style* at team level instead; treat derbies as higher-variance, not higher-EV. | [tier-1] — sample-size kills it | [fixtures-and-context](factors/fixtures-and-context.md#head-to-head--matchup-context) |
| **Price / team-value momentum** | Tie-breaker only: prefer moves that catch predicted rises / dodge drops; front-load early-season. Keep out of the core xPts objective (lagging herd signal). Value compounds ~£2–3m/season but is subordinate to information. | [tier-1] — price algorithm; top-50 subordinate price to info | [value-and-ownership](factors/value-and-ownership.md#price-value--differentials) |
| **xA source (open vs set-play)** | Sustainability haircut on the xA axis: keep open-play xA at full weight, discount set-play xA by taker-role security. Not a standalone axis. | [tier-2] — sustainability refinement | [predictive-signals](factors/predictive-signals.md#xg--xa) |
| **International-break hangover / travel** | After a break, discount long-haul / two-full-internationals players' first GW (higher blank/injury/rotation risk). Club/player-specific. | [tier-1] — travel-load physiology | [fixtures-and-context](factors/fixtures-and-context.md#congestion--days-rest) |
| **New-signing adaptation lag** | Probabilistic first-N-GW discount on foreign arrivals (larger from weaker leagues), *not* a blanket filter — proven-league / nailed-role signings can hit immediately. Don't pay the GW1 hype premium. | [tier-1] — bedding-in distribution shift | [meta-and-timing](factors/meta-and-timing.md#behavioural--season-start-guardrails) |
| **Behavioural discipline** | Encode anti-churn guardrails: don't reverse a transfer within N GWs without new hard info; require multi-GW EV thresholds; damp single-GW noise. The machine's edge is being *perfectly* disciplined. | [tier-2] — top-50 consistency | [meta-and-timing](factors/meta-and-timing.md#behavioural--season-start-guardrails) |

---

## Anti-signals — sound smart, weak/no signal (do NOT build features on these)

From the discovery agents' explicit "sounds smart but no signal" findings. Keep
them here so the gaffer doesn't waste modelling effort or, worse, add noise.

| Non-signal | Why it fails | Do instead |
|---|---|---|
| **Possession %** as a points driver | Counter-attacking sides win with <50%; weak outcome predictor alone | Use shot volume/location + style archetype |
| **Weather** (routine) | Real only at extremes (heavy rain ~14% fewer goals, strong wind); forecasts days out unreliable | Rare tail adjustment for a genuine storm, not a standing feature |
| **Kickoff time-of-day** | No signal separable from opponent/congestion; "Tuesday night" is European-load confound | Ignore; model congestion instead |
| **Raw last-N points** as forward predictor | Backward-looking, finishing-luck-driven, regresses hard | Use underlying xGI + fixtures |
| **"New-manager bounce"** as bankable boost | Real ~+41% PPG but priced in by ~match 7 | Bet the *role/system change* (who benefits), not the bounce |
| **Blanket "fade all foreign signings"** | Adaptation lag is a distribution shift, not a rule | Probabilistic discount, keep a proven-immediate whitelist |
| **Chip *choice*** (which chip) | Best-vs-second ≈ 3 pts | Spend effort on chip *timing* (~+49 pts) |
| **Random / unearned differentials** | Low EO adds EV only with genuine underlying stats | Differentiate on real xGI/DEFCON + fixtures, sized to rank need |

---

## How the tiers map to the GW1 run (#25)

Pre-GW1 is a **low-information regime** — this-season xG/form don't exist yet — so
weight the **structural** axes heaviest (they need no current-season data):
class-player prior, team style/usage, promoted-team fragility, set-piece/penalty
roles, home/away, de-vigged odds. Gate hard on **minutes-certainty** (the #1 GW1
filter). Lean **template** on the core and on captaincy (rank-risk asymmetry under
uncertainty). Keep ~£0.5m bank + ≥1 FT into GW2. Friendlies inform *role/minutes*
only — never friendly goal tallies. Details: [factors/predictive-signals.md#pre-season-friendlies](factors/predictive-signals.md#pre-season-friendlies)
and [methods/squad-construction.md#gw1-specific-construction](methods/squad-construction.md#gw1-specific-construction).
