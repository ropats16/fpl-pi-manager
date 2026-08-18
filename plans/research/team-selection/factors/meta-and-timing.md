# Factors — meta-strategy & timing

The layer *above* single-player selection: planning across gameweeks, chips,
transfer economics, and decision timing. A next-GW optimiser is structurally blind
to most of this, so it's where the biggest process edges live. Full evidence:
[../raw/discovery-practitioner.md](../raw/discovery-practitioner.md),
[../raw/discovery-quant.md](../raw/discovery-quant.md),
[../raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md).

Most of these bite from ~GW4+ — **build the machinery now, use it later**. GW1-relevant
items are flagged.

---

## Multi-week planning horizon

**Suggested weight: HIGH.**

- **Method:** optimise **cumulative** xPts over a rolling **5–6 GW** window (the solver
  standard), not one GW. A **−4 hit** must clear >4 pts over the ~3–4 GWs you'll own the
  player — "most knee-jerk transfers don't clear that bar." Value **banking free
  transfers** (hard cap 5) and fixture *swings* as options, not one-week spikes
  ([Full90](https://full90fpl.com/fpl-transfers-explained/);
  [FPL Copilot planner](https://fplcopilot.com/blog/transfer-planning-guide)).
- Concretely this is the optimiser's decay-weighted objective — see
  [../methods/squad-construction.md#optimizer-objective--constraints](../methods/squad-construction.md#optimizer-objective--constraints).

Evidence tier: **[proven/tier-1]** — solver horizon + top-50 hit discipline.

---

## Chip strategy & timing

**Suggested weight: HIGH (largest single meta swing) — [build now, bites GW4+].**

- Optimal chip **timing** is worth ~**+49 pts/season** (best case +73); best-vs-second
  chip **choice** only ~3 pts. So the EV is almost entirely in *when*, not *which*.
  **[tier-2/folklore — corrected 2026-08-18]:** these figures trace to a single vendor,
  [FPL Copilot — chip strategy](https://fplcopilot.com/blog/chip-strategy-guide) (HiGHS MIP
  over "hundreds of real squads", sample/seasons unpublished), **not** the FF Fix top-50 page
  previously cited here — that page only shows *when* top managers played chips (1st WC modal
  ~GW4, 2nd ~GW32: [FF Fix — top-50 wildcards](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-wildcards-2025-26/)).
  The qualitative "timing ≫ choice" survives; the numbers are unreproduced
  ([evidence](../../gaffer-architecture/raw/season-long-machinery.md)).
- **Method:** treat chips as a scheduled plan keyed to the fixture calendar — the
  repeatable winning sequence is **Wildcard before the biggest fixture swing → Bench
  Boost on the ensuing DGW → Free Hit on the blank**. Maintain a rolling 6-GW chip plan;
  deviate only on hard injury/DGW-confirmation news.
- **2026/27 rule context (verified official):** two chip sets (WC/FH/TC/BB each half);
  **first set expires at the GW19 deadline — 13:30 GMT, Sat 2 Jan 2027 — and cannot
  carry over**, so first-half chips must be spent. Roll up to 5 FTs; no AFCON this season
  → no bonus mid-season FTs
  ([PL — all 2026/27 changes](https://www.premierleague.com/en/news/4679873/all-you-need-to-know-about-changes-to-fpl-for-202627)).
  One nuance to verify at build time: reportedly you *keep* banked transfers when playing
  a chip.

Evidence tier: **[tier-1]** — top-50 chip study; rules **[proven]**.

---

## DGW & BGW planning

**Suggested weight: MED (HIGH mid/late season) — [build the feed now].**

- The **single best predictor of future DGWs is FA-Cup (and European) progression**:
  when a PL team advances, the displaced league fixture becomes a likely DGW later;
  knockouts/replays drive blanks
  ([FFS](https://www.fantasyfootballscout.co.uk/2026/07/20/preparing-for-an-fpl-blank-or-double-gameweek)).
- **Method:** ingest cup/European progression to **forecast** DGW/BGW gameweeks weeks
  ahead and pre-position transfers/chips — don't wait for the official reschedule
  announcement (by then DGW assets have risen and are widely owned). DGWs are TC/BB
  windows; BGWs are the classic Free Hit tool.

Evidence tier: **[tier-1]** — cup-progression method.

---

## Transfer discipline

**Suggested weight: HIGH — [GW1-relevant].**

- Top-50 transfer logs: they buy at **0/5/10/15% ownership** (before bandwagons); the
  most common previous-GW score of a player they bought was just **2 pts** (not chasing
  hauls); they decide **late (Fri/Sat, post-team-news)**, forgoing minor price gains for
  information; and they take **very few hits** all season
  ([FF Fix — transfers](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-transfers-2026-27/)).
- **Method:** default to **deferring** transfers to just before deadline; target players
  trending up in *underlying* stats while still low-owned; add an explicit
  anti-points-chasing penalty so a big previous-GW score doesn't inflate buy priority.
  Counter-momentum + late timing.

Evidence tier: **[tier-1]**.

---

## Decision-timing option value

**Suggested weight: HIGH (process factor) — [GW1-relevant].**

- The sharpest lineup/injury/rotation info and near-closing odds arrive at the final
  press conferences; committing early forfeits real option value.
- **Hard constraint:** FPL deadline is **T-90 min** before first kickoff, but confirmed
  XIs only drop **~75 min** before *each* kickoff — so at lock time **zero confirmed
  lineups exist**. You decide on predicted XIs + injury flags + pressers, never confirmed
  lineups ([PL 75-min rule](https://www.premierleague.com/en/news/4081650)).
- **Method:** architect the pipeline to **stage** decisions — pre-compute candidates
  early, finalise transfers/captaincy as late as responsibly possible (a poll+solve at
  ~T-15 to T-5 with runtime margin). Make **"wait for team news" a first-class action**;
  treat unresolved rotation as an explicit E(minutes)/variance penalty; exploit
  bench-order as the post-deadline safety net. Never block waiting for confirmed XIs.
  See [../sources/data-sources.md#deadline-timing-constraint](../sources/data-sources.md#deadline-timing-constraint).

Evidence tier: **[standard]** — CLV / information-arrival logic.

---

## Behavioural & season-start guardrails

**Suggested weight: MED (guardrail) — [GW1-relevant].**

- Consistency, not weekly luck, is the through-line of managers who stay top-10k; the
  machine's real edge over humans is that it *can* be perfectly disciplined
  ([RotoWire](https://www.rotowire.com/soccer/article/how-to-win-at-fpl-fantasy-premier-league-beginner-guide-127118)).
- **Method:** encode anti-churn guardrails — don't reverse a transfer within N GWs
  without new hard info; require multi-GW EV thresholds for any move; damp reactions to
  single-GW noise.
- **New-signing adaptation lag:** apply a first-N-GW discount to foreign arrivals (larger
  from weaker/less-physical leagues, smaller for proven PL performers or nailed
  focal-role signings) — a probabilistic discount, **not** a blanket filter (Haaland/Salah
  hit immediately). Don't pay the GW1 ownership/price hype premium; re-evaluate ~GW6–8
  ([raw/discovery-firstprinciples.md](../raw/discovery-firstprinciples.md)).
- **GW1 specifically:** the edge is **restraint and minutes-certainty**, not cleverness —
  up-weight a nailedness prior, penalise uncertainty, lean template, and keep ≥1 FT + a
  small bank into GW2 to react once real data lands. Details:
  [../methods/squad-construction.md#gw1-specific-construction](../methods/squad-construction.md#gw1-specific-construction).

Evidence tier: **[tier-2]** — top-50 consistency; adaptation lag **[tier-1]**.
