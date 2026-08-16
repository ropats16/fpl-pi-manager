# The "class player" prior — concrete definition

Acceptance-criterion deliverable for [#24](https://github.com/ropats16/fpl-pi-manager/issues/24):
a definition of the class-player prior **concrete enough to apply in the GW1 run**
([#25](https://github.com/ropats16/fpl-pi-manager/issues/25)). The problem it
solves: a proven player (Haaland, Salah) must **not** be downgraded by a quiet
pre-season friendly or a two-game cold snap. The mechanism is Bayesian shrinkage —
so the math *enforces* that thin recent evidence can't move a strong prior much.

Method tag: **[standard → use]** — James–Stein / empirical-Bayes shrinkage is an
established statistical result (provably lowers MSE, most in small-sample regimes:
13.8–17.2% MSE gain vs MLE in data-limited settings,
[arXiv 1807.09236](https://arxiv.org/pdf/1807.09236);
[Efron & Morris / CASI ch.7](https://efron.ckirby.su.domains/other/CASI_Chap7_Nov2014.pdf)).
The specific parameterisation below is our synthesis, to be calibrated in backtest
(see [methods/signal-synthesis.md](methods/signal-synthesis.md)).

## The formula

For each player, project the underlying rate as a shrinkage blend of a prior and
recent observation:

```
posterior_rate = (κ · μ₀ + n · x̄_recent) / (κ + n)
```

- **μ₀ — prior mean.** The player's **minutes-weighted xGI/90 (xG + xA per 90)
  over the last 2–3 seasons** (FBref/Understat), combined with:
  - **established role** — nailed starter? penalty / set-piece taker? attacking
    position? (gates the prior by expected minutes), and
  - **historical points ceiling** — best-season FPL points / PPG (sets the upside
    of the EV distribution).
  A rolling 2–3-year window is "statistically sufficient for meaningful Bayesian
  predictions" ([Braun](https://nathanbraun.com/bayesian-fantasy-football/)).
- **κ — prior strength**, in "pseudo-games." Confidence in the prior: **large for
  long, consistent multi-season histories** (Haaland, Salah → κ ≈ 15–20 games'
  worth), small for volatile or short histories. This is the knob that makes a
  "class player" class.
- **n — recent games observed**; **x̄_recent — recent underlying rate** (xGI/90).
- Shrinkage strength ∝ `1/√games_played` — the prior dominates when `n` is tiny.

## Why it does the job

At pre-season `n ≈ 0`, and through GW1–3 `n ≤ 3`, so with κ ≈ 15–20 the posterior
stays **essentially at μ₀** — a flat friendly or a couple of blanks barely moves a
high-κ player. As real matches accrue, `n` grows and recent data organically takes
over. No hand-tuned "ignore pre-season for stars" rule is needed; the arithmetic
enforces it. This is exactly the regime Bayesian priors are "particularly practical"
for — small samples, decision-making not inference
([Frontiers Bayesian](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1486928/full)).

## A usable recipe for the GW1 run

1. **Build μ₀** for every relevant player from 2–3 seasons of minutes-weighted
   xGI/90 (Understat/FBref), tagged with role (nailed? penalty taker?) and a
   points-ceiling figure.
2. **Assign κ** by history length × consistency:
   - **κ ≈ 18** — 3+ seasons elite & consistent (the untouchable class players).
   - **κ ≈ 10** — 2 strong seasons, or 1 elite + secure role.
   - **κ ≈ 4** — short/volatile PL history, or a role change.
   - **κ ≈ 1–2** — new signing / promoted / minimal PL data (prior barely holds;
     lean on structural signals instead — see [factors/fixtures-and-context.md#team-style--usage-share](factors/fixtures-and-context.md#team-style--usage-share)).
3. **Project** `posterior_rate` with `n = 0` (pre-season) → the estimate *is* μ₀ for
   class players. Feed it into goal/assist EV, then through the minutes gate and
   fixture/odds layers like any other rate.
4. **Guardrail:** never let a single quiet friendly or 1–2 blanks move a high-κ
   player's projection more than a small fraction — the formula already enforces
   this; treat a manual override that violates it as a red flag to log.

## Interactions & caveats

- **New signings are the anti-class case.** They have no PL prior (low κ), so this
  formula won't rescue them — and it shouldn't. Apply the new-signing adaptation
  discount instead ([factors/meta-and-timing.md#behavioural--season-start-guardrails](factors/meta-and-timing.md#behavioural--season-start-guardrails))
  and don't pay the GW1 hype premium.
- **Friendlies feed role/minutes, not the rate.** Use pre-season only to confirm
  nailedness, set-piece duty, and fitness — never friendly goal tallies as x̄
  ([factors/predictive-signals.md#pre-season-friendlies](factors/predictive-signals.md#pre-season-friendlies)).
- **The prior is not a veto on selling.** A class player who *loses his role* (drops
  in the pecking order, injury, tactical change) should have κ cut — the prior
  encodes proven output *in an established role*, so a role change invalidates it.
- **Distinct from the finishing whitelist.** A separate short list of players with
  multi-season *finishing* overperformance (goals ≫ xG that persists) legitimately
  sit above xG — don't over-regress them
  ([factors/predictive-signals.md#finishing-overunder-performance](factors/predictive-signals.md#finishing-overunder-performance)).

Full evidence: [raw/cluster-A-signals.md](raw/cluster-A-signals.md) (axis 6),
[raw/followup-signal-synthesis.md](raw/followup-signal-synthesis.md) (topic 4).
