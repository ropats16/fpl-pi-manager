# Optimizer audit — QUANT / OPTIMIZER-AUDITOR (GW1 2026-27)

Audit date: 2026-08-16. GW1 deadline: Fri 2026-08-21 17:30 UTC.
Scope: `fpl_optimizer.py`, `fpl_projections.py`, `fpl_api.py`, `draft_board.py`,
`run_pipeline.sh` and the `data/*.csv` snapshot they run on.

> **Headline reversal.** The brief told me the optimizer's data was corrupted —
> wrong PL team set (Coventry/Hull), scrambled player→team labels (Guéhi→MCI,
> Senesi & Van Hecke→TOT). **I verified every one of those against live sources and
> they are all CORRECT for 2026-27.** The "corruption" premise is false. The
> optimizer's real weaknesses are in its *projection model and objective*, not its
> team labels. See §3.

---

## 1. How it works

### Objective (`fpl_optimizer.py:96-122`)
A single-shot binary ILP (PuLP + CBC). The objective (`:101-102`) is:

```
maximize  Σ_i  x_i · ( horizon_xpts_i  +  (gw1_weight − 1)·gw1_xpts_i )
```

- `horizon_xpts` = sum of a player's per-GW xPts over the next `HORIZON=6` GWs,
  already decay-weighted inside projections (`fpl_projections.py:129`, `DECAY=0.96`).
- `gw1_weight` (default 2.0) adds one extra copy of GW1 xPts → GW1 counts double
  relative to later weeks. A front-loading knob.
- **All 15 selected players are weighted equally.** There is **no captain doubling,
  no bench discount, and no explicit P(start) term** in the objective. Captain
  doubling and bench ordering exist only in the *display* layer (`pick_xi`,
  `report` `:125-170`), not in what the solver maximizes.

> This matters: the brief and the research page describe a *"decay-weighted,
> captain-doubled, bench-weighted xPts × P(start)"* objective
> (`methods/squad-construction.md:73-96`, `importance-ranking.md:46`). **That is the
> research IDEAL, not this code.** The actual code is materially cruder.

### Hard constraints (all correct, verified by selftest)
- Squad size 15 (`:103`); budget ≤ `--budget` (`:104`); shape 2/5/5/3 (`:105-106`);
  **max 3 per club** (`:107-108`); optional total-xmins floor `--min-xmins`
  (`:109-110`); "at most k outsiders vs current squad" for k-sweep (`:111-112`);
  `KEEP_IDS` force-include (`:113-117`).
- `selftest` (`:236-281`) passes: shape, budget, club-cap (asserts n=3 on the
  stacked test club), k-sweep monotonicity, XI formation legality, captain = XI-max.
  **The solver machinery is sound.**

### Modes (`main` `:180-233`)
- `scratch` — best 15 under budget, ignore current squad.
- `from-squad` — k-sweep: best squad with ≤ k changes vs `CURRENT_SQUAD`
  (`:29-33`), prints marginal xPts gain per change. `KEEP_NAMES` (`:27`) pins
  Haaland + B.Fernandes.
- `xi` — best GW1 XI + bench order + captain from the current squad only.
- `selftest` — offline invariants.

### XI / captain / bench logic (`pick_xi` `:125-146`)
Enumerates every legal formation (3-5 DEF, 2-5 MID, 1-3 FWD), picks the one
maximizing summed GW1 xPts; captain = highest-GW1 starter, VC = second; bench =
outfield by descending GW1 xPts then the spare GK last. Formation-free — matches
the research recommendation (`squad-construction.md:56-67`).

### Knobs (`get_args` `:173-177`)
`--budget 100.0` · `--gw1-weight 2.0` · `--min-xmins 900` · `--max-changes 8`.

### Pipeline (`run_pipeline.sh`)
`fetch|offline|selftest`. Live/offline → `fpl_api.py csv` (health-gated: refuses to
emit CSVs if the bootstrap health checks fail, `fpl_api.py:161-177`) → `fpl_projections.py`
→ `fpl_optimizer.py scratch`. `fpl_api.py` health check bounds player count 550-900
and requires 38 events (`:51-62`).

### How projections build xpts (`fpl_projections.py`) — the real engine
1. `base_rate` (`:65-74`): blend of **last-season pts/90** (`total_points/minutes·90`)
   and FPL's `ep_next`. Weight on `ep_next` is only **0.25** for established players
   (≥450 min) and 0.70 for low-minute players — so for anyone who actually plays,
   the projection is **~75% last-season FPL points-per-90**.
2. `minutes_share` (`:77-82`): minutes / (38·90), floored at `NAILED_FLOOR=0.10`,
   capped 1.0 — **but hard-zeroed below `MIN_MINUTES_FOR_HISTORY=450`** (`:79`).
3. `fixture_mult` (`:95-97`): position-split FDR 1-5 → multiplier (`:45-46`) × 1.06
   home edge.
4. `status_mult` (`:85-92`): availability haircut a/d/i/s/u; GW1 also clamps to
   `chance_of_playing_next_round/100`.
5. Per-GW: `rate · minutes_share · fixture_mult · status_mult · DECAY^i`
   (`:128-129`); horizon = sum over 6 GWs.

---

## 2. Reproduced output

`python3 fpl_optimizer.py scratch --budget 100.0` (venv, CBC):

```
=== SCRATCH optimal (budget £100.0m) ===
cost £100.0m | 6-GW xpts 314.8 | zero-projection players: 0
  GKP Kelleher      BRE  £5.0  gw1 3.66  hor 18.95
  GKP Verbruggen    BHA  £4.5  gw1 3.25  hor 17.16
  DEF Guéhi         MCI  £6.0  gw1 4.43  hor 23.50
  DEF Senesi        TOT  £6.0  gw1 4.13  hor 23.21
  DEF Tarkowski     EVE  £6.0  gw1 4.28  hor 23.05
  DEF Van Hecke     TOT  £5.0  gw1 3.44  hor 19.32
  DEF Mitchell      CRY  £4.5  gw1 3.07  hor 17.12
  MID B.Fernandes   MUN  £12.0 gw1 6.20  hor 31.66
  MID Anderson      MCI  £6.5  gw1 4.36  hor 23.11
  MID E.Le Fée      SUN  £6.0  gw1 3.75  hor 18.80
  MID Zubimendi     ARS  £5.5  gw1 3.64  hor 17.13
  MID Ampadu        LEE  £5.5  gw1 3.10  hor 17.07
  FWD Haaland       MCI  £15.5 gw1 5.92  hor 31.36
  FWD Calvert-Lewin LEE  £6.0  gw1 3.20  hor 17.61
  FWD Welbeck       BHA  £6.0  gw1 2.98  hor 15.76
  XI (4-4-2): Kelleher; Guéhi, Tarkowski, Senesi, Van Hecke; B.Fernandes (C),
              Anderson, E.Le Fée, Zubimendi; Haaland (VC), Calvert-Lewin
  bench: Ampadu, Mitchell, Welbeck, Verbruggen
```

Spend £100.0m exactly, £/xpts ≈ 0.318 m/pt. `selftest` PASSES. One matcher warning:
`AMBIGUOUS: Hughes` (two players named Hughes — name-collision risk, see §3.6).

---

## 3. Data-quality failure diagnosis

### 3.0 The brief's "corruption" claims are FALSE — verified against live sources
The `data/` snapshot reflects a legitimate early-August 2026 state with real,
completed transfers. Player *stats* in `players.csv` are real last-season (2025-26)
numbers. I checked every flagged item:

| Brief claim ("corrupted / wrong") | Reality (sourced) | Verdict |
|---|---|---|
| PL set wrong — shows Coventry/Hull | Coventry, Ipswich, **Hull all promoted** for 2026-27 | **teams.csv CORRECT** |
| Guéhi → MCI is a scramble | Guéhi **did** join Man City (official Palace announcement, Jan 2026) | **CORRECT** |
| Senesi → TOT is a scramble | Senesi **did** join Spurs (free, June 2026, De Zerbi signing) | **CORRECT** |
| Van Hecke → TOT is a scramble | Van Hecke **did** join Spurs (£52m, June 2026) | **CORRECT** |

Sources:
- Promoted trio: [premierleague.com](https://www.premierleague.com/en/news/4611805/who-will-be-promoted-from-efl-championship-to-premier-league-for-2026-27-season),
  [2026 EFL play-off final (Wikipedia)](https://en.wikipedia.org/wiki/2026_EFL_Championship_play-off_final) — Hull City 1-0 Middlesbrough.
- Relegated trio (West Ham, Burnley, Wolves — all correctly ABSENT from teams.csv):
  [PL 2025-26 final table](https://www.nbcsports.com/premier-league-table-2025-26-season-standings),
  [Wikipedia 2025-26 PL](https://en.wikipedia.org/wiki/2025%E2%80%9326_Premier_League).
- Guéhi→City: [cpfc.co.uk official announcement](https://www.cpfc.co.uk/news/announcement/marc-guehi-departs-crystal-palace-to-join-manchester-city/).
- Senesi→Spurs: [tottenhamhotspur.com](https://www.tottenhamhotspur.com/news/1072863/senesi-switch-sealed),
  [ESPN](https://www.espn.com/soccer/story/_/id/48907789/marcos-senesi-joins-tottenham-bournemouth-roberto-de-zerbi-second-signing).
- Van Hecke→Spurs: [tottenhamhotspur.com](https://www.tottenhamhotspur.com/news/1073998/van-hecke-joins-from-brighton),
  [Sky Sports](https://www.skysports.com/football/news/11675/13555493/jan-paul-van-hecke-tottenham-sign-brighton-defender-for-lb52m).

The teams.csv id→club map (`ARS=1 … Coventry=7 … Hull=11 … Ipswich=12 … Sunderland=20`)
matches the real 2026-27 20-team set. In `players.csv`, `Guéhi` has `team=15` (Man
City), `Senesi`/`Van Hecke` have `team=19` (Spurs) — **factually correct**. The
club-cap constraint is therefore operating on *correct* labels (verified in output:
Guéhi+Anderson+Haaland = 3 MCI; Senesi+Van Hecke = 2 TOT — all legal).

> **This is the most important finding of the audit.** Do not rebuild the data on the
> assumption that labels are scrambled — they are not. (This looks like the
> "prior-agent fabrication" caveat firing on the *wrong target*: the fabrication is in
> the corruption CLAIM, not the data.)

### The REAL data/model failures (these are genuine — severity flagged)

**3.1 Movers carry old-club output — HIGH severity for a fresh season.**
`base_rate` is ~75% last-season pts/90 (`fpl_projections.py:71`). For a player who
changed clubs it projects the *old* club's role/system onto the new one. Guéhi's
Palace tally (a defense that over-performed, plus his own goals) becomes `hor 23.50`
at Man City — where he faces rotation with Dias/Aké/Stones and a different scoring
profile. The label is right; the *number* is naive. Same for Senesi/Van Hecke (new
De Zerbi back line), and every summer mover. The model cannot see role change.

**3.2 The 450-minute history floor zeroes out whole cohorts — HIGH severity.**
`minutes_share` hard-returns 0 below 450 senior minutes (`:79`), which forces xpts=0
(`:128`). By construction this **excludes, and can never select**: every
Coventry/Hull/Ipswich player (no PL minutes), every foreign new signing, and anyone
injured most of 2025-26. The comment says a "news/minutes layer re-adds them" — that
layer does not exist. For an *initial* GW1 squad this is a large blind spot: nailed
promoted-side keepers, cheap DEFCON CBs, and marquee arrivals are simply invisible.
The clean `zero-projection players: 0` line is a *symptom*: the optimizer structurally
routes around the entire unproven pool.

**3.3 `chance_of_playing_next_round` empty for all 564 players — MEDIUM.**
The GW1 availability haircut (`status_mult` gw1 branch, `:88-91`) is **inert** — no
`cop_next` values in the snapshot (preseason, no injury flags posted yet). No fitness
gate. The research demands minutes-certainty as the #1 GW1 filter
(`importance-ranking.md:22-30`) and replacing anyone who misses the final 1-2
friendlies (`squad-construction.md:127`) — the model does neither.

**3.4 Snapshot is pre-final-window — MEDIUM.** Data ≈ 2026-08-02, deadline 08-21.
Missing: late-window transfers, price changes, preseason-friendly injuries, updated
ownership. `form=0.0` for everyone (preseason reset — fine, but means `ep_next` is the
only forward FPL signal and it's down-weighted to 0.25).

**3.5 FDR is the naive 1-5 — MEDIUM.** `fixture_mult` uses raw FPL difficulty
(`:45-46`); `teams.csv` `strength_*` columns are all 0 (unused). Research Tier-1 wants
position-split team-strength/odds-implied ratings (`importance-ranking.md:39`). Early-
season FDR for reshaped squads is especially unreliable.

**3.6 Name-collision matcher risk — LOW (affects from-squad/xi only).**
`match_squad` (`:73-93`) falls back to substring then best-xmins on ambiguity. `Hughes`
already warns; `Anderson`, common surnames, could mis-ID in `from-squad`/`xi` modes.
`scratch` is unaffected (it never matches by name).

### How much to distrust it
- **Team labels / club-cap / rule constraints:** TRUST — verified correct.
- **Specific projected point totals (esp. movers & mid/cheap picks):** LOW trust.
- **The unproven-player universe (promoted, new foreign, returning-injured):** the
  model is *blind* — treat absence as "not evaluated," not "not worth it."
- **Premium anchors it converges on (Haaland, B.Fernandes):** these survive on any
  method — trustworthy as template anchors, not because the model is right.

---

## 4. Method critique vs research

The ILP **spine** is exactly what the research endorses: hard-linear rule constraints,
formation emerging from selection, max-3 kept hard and allowed to bind
(`squad-construction.md:56-67,104-109`). But measured against
`importance-ranking.md` Tier-0/Tier-1, the objective is **missing almost every
value layer that matters for GW1**:

| Missing layer (research tier) | Consequence for GW1 |
|---|---|
| **DEFCON 2026/27** (+2 CBIT/CBIRT) [proven, `:44`] | Biggest repricing of cheap DEF & holding mids. Model can't see why 4-4-2 with DEFCON floor-scorers beats a 5th mid. Its 4-4-2 here is accidental, not DEFCON-driven. |
| **EO / rank objective** (`xPts − EO·field`) [tier-1, `:43`] | Optimizes raw xPts, blind to template risk. FPL is relative; not owning a 90%-EO haul is a rank loss the model never prices. |
| **Set-pieces & penalties** [tier-1, `:41`] | No boost for the confirmed pen/FK taker — a top-owned GW1 edge is invisible. |
| **De-vigged betting odds** [tier-1, `:37`] | No market prior — the most efficient public signal, and the highest-value GW1 axis in a no-data regime, is absent. |
| **Class-player prior** (Bayesian shrinkage) [`:40`] | No shrinkage; a quiet-friendly premium isn't protected, an over-performer isn't faded. |
| **Whole-XI covariance / stacking** [tier-1, `:51`] | Sums 11 means; ignores that same-team/same-match returns covary. No deliberate stack-for-rank or diversify-to-protect. |
| **Captain doubling in the objective** | Not optimized — only displayed. The squad isn't built to maximize captain EV. |
| **Bench weighting / strong-XI bias** [`:33-50`] | All 15 weighted equally → spreads value instead of "strong XI + cheap-but-alive bench." `min-xmins 900` total is a blunt proxy, not `P(0 min)·xPts` bench logic. |
| **P(start) via the 60-min kink** [Tier-0 gate, `:26`] | Uses a *linear* minutes fraction — precisely what the gate page says NOT to do. |
| **Promoted-team fragility** [tier-2, `:65`] | Moot here only because promoted players are already zeroed (3.2). |

**Where trusting it blindly hurts most:** it would (a) hand you a squad with **zero
exposure to the entire promoted / new-signing pool** and no cheap DEFCON defenders;
(b) over-commit to summer movers on stale role assumptions; (c) pick a mid/bench
purely on last-season points with no EO, odds, set-piece or fitness check; (d) give a
captain/bench that were never actually optimized. On the flip side it is directionally
right on **budget shape and premium anchoring** — see §5.

---

## 5. Salvageable structural guidance (data-independent)

Keep these — they are model *structure*, not the untrustworthy specific names:

1. **The ILP is the right spine.** Hard-linear constraints, valuation drives
   selection, formation is an output. Reusable as-is; the fix is *better per-player
   scores fed in*, not a new solver.
2. **Spend to the cap on 2-3 premiums, balanced spine.** It lands £100.0m exactly with
   Haaland (£15.5) + B.Fernandes (£12.0) as anchors and a balanced 2/5/5/3 — matches
   top-50 "balanced-strategic, not stars-and-scrubs" (`squad-construction.md:20-33`).
   Directionally correct; nudge toward the top-50 shape (MID ~41% / FWD ~30% / DEF ~23%
   / GK ~6% of *effective* budget — concentrate premiums in **midfield**).
3. **Formation-free XI.** Endorsed — let the shape emerge (`:56-67`).
4. **Multi-GW horizon + GW1 overweight.** The 6-GW decay and `--gw1-weight` lever are
   sound; consider a steeper weekly decay (research ~0.84/wk vs code's 0.96).
5. **Club-cap headroom is real.** Its max-3 stacks (3 MCI, 2 TOT here) are legal and
   the labels are correct — use it as a genuine feasibility/stacking sanity check.
6. **Premium anchors survive.** Haaland + B.Fernandes as the spine, and a GK pairing
   around one reliable starter + a £4.5 backup, are template-correct.
7. **Cheap-bench principle** (`squad-construction.md:38-50`) — build in by hand
   (the objective doesn't), but the £4.0-4.5 GK / £4.5 fodder value zones are right.

**Clearly NOT to carry forward:** the specific mid/cheap outfield names (Anderson,
E.Le Fée, Zubimendi, Ampadu, Calvert-Lewin, Welbeck, Mitchell) and the exact
captain/bench order — those are last-season-points artifacts with none of the
Tier-1 GW1 layers applied.

---

## 6. Bottom line
The optimizer is a **structurally sound ILP running on correct labels but a thin,
backward-looking projection model.** Its *rules, budget discipline, and premium
anchoring* are trustworthy; its *specific mid/bench picks, captain, and the entire
excluded unproven pool* are not. Fix by layering the missing Tier-0/Tier-1 signals
(minutes-certainty gate, DEFCON, odds, set-pieces, EO, class-prior, promoted-team
picks, final-friendly fitness) on top by hand — not by rebuilding data that is, in
fact, correct.
