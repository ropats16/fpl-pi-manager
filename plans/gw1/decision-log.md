# GW1 2026-27 — Decision Log

The auditable record behind [brief.md](brief.md): every signal, the weight the gaffer
leaned on, the rationale, and where the assistant-manager's pushback was accepted or
rejected. This is the **baseline for post-GW review** ([#21](https://github.com/ropats16/fpl-pi-manager/issues/21)) —
outcomes get filled in after GW1.

Method + template basis:
[signal-synthesis › decision-log template](../research/team-selection/methods/signal-synthesis.md#decision-log-template-satisfies-the-25-decision-log-requirement)
· [importance-ranking](../research/team-selection/importance-ranking.md)
· [squad-construction](../research/team-selection/methods/squad-construction.md).
Map: [../map.md](../map.md). Approach: [approach.md](approach.md).

- **Model version:** one-shot Claude-Code multi-agent gaffer run (Opus 4.8 sub-agents +
  Opus 4.8 leaves). **Compiled** 2026-08-16/17. **Deadline** Fri 2026-08-21 17:30 UTC.
- **Data provenance:** live official FPL API (`bootstrap-static`, obs 2026-08-16) for
  prices/ownership/teams; live web (books, official club/PL, FFScout) for odds/fixtures/
  team-news. Local Aug-2 pipeline data used only as a cross-check.

---

## 0. Process & the weights the gaffer leaned on

**Roster.** Parent gaffer + five angle sub-agents (availability/minutes · fixtures/odds ·
talent/style/class-prior · value/price/EO · optimizer-audit), each Opus 4.8, each permitted
Opus-4.8 leaf agents under a tight-ship anti-fabrication rule (cite real URLs; verify every
leaf against a second source; never invent). Then an **assistant-manager** agent attacked
the gaffer's draft with evidence; the gaffer adjudicated. Rohit = observer (no intervention).

**Weighting philosophy (per [signal-synthesis](../research/team-selection/methods/signal-synthesis.md)):**
GW1 is a **low-information regime** — no current-season xG/form exists — so the gaffer
weighted **structural axes heaviest** (need no current-season data) behind a **hard minutes
gate**, and leaned **template** on the core + captain (rank-risk asymmetry under uncertainty).
No learned weight table (forecast-combination puzzle); near-equal weighting of de-correlated
buckets, gated on minutes.

| Bucket | GW1 weight leaned on | Why |
|---|---|---|
| **Minutes / nailedness** | GATE (hard) | #1 GW1 filter; drop below start-prob floor regardless of EV. |
| **Class-player prior / usage share** | HIGH | Structural, no current-season data needed — the strongest pre-season signal. |
| **Confirmed penalty role** | HIGH | ~+16-20 pts/season for a lead taker; only counted where UNDISPUTED. |
| **Odds-implied fixture (de-vigged)** | HIGH | Best public prior; used for CS/attack-spot ranking + captaincy. |
| **Promoted-team fragility** | MED-HIGH | Fade promoted attackers; exploit their fixtures; cheap-GK/DEFCON exceptions. |
| **Effective ownership / template** | HIGH (core+captain) | One-shot GW1 → not owning a big-EO haul is a rank loss. |
| **Optimizer xPts** | LOW (advisory) | Projection model thin (last-season, 450-min floor hides promoted/new). |
| **Form / raw last-N pts** | ~0 | No current-season data; anti-signal per research. |
| **Raw H2H** | 0 | Tier-3 noise (research); style captured at team level instead. |

---

## 1. The premise correction (assimilated mid-run)

**DECISION: reject the "corrupted local data" premise.**
The gaffer's initial brief to agents said the local team set (Coventry/Hull) and player→team
labels were corrupted. The **optimizer-audit agent falsified this** against live sources, and
the value/talent/availability agents **independently confirmed** (4 agents, incl. a direct
FPL-API pull): the data is **correct 2026-27** — Coventry/Hull/Ipswich genuinely promoted
(Hull won the playoff final); West Ham/Burnley/Wolves relegated; Guéhi→City, Senesi/Van
Hecke→Spurs are real. The gaffer's "corruption" read was itself the error (post-cutoff
unfamiliarity mistaken for corruption).
→ **Correction broadcast to all four running agents mid-run.** The *real* local-data gap is
the **projection model** (≈75% last-season pts/90; a 450-min floor hard-zeroes every
promoted-side player, new signing, and injury returnee — making them invisible), which is
why the optimizer is advisory-only and promoted/new-signing assets were surfaced by hand.
Confidence: HIGH (4 independent confirmations). *Lesson for post-GW: verify the premise, not
just the picks — the tight-ship discipline caught the gaffer.*

## The missing Aug-5 squad

**DECISION: initial build, no phantom prior.**
Acceptance criteria referenced "transfers vs the recorded Aug-5 squad," but no such squad
exists — `entered_events: []`, `current_event: null`, `season-state.json.squad: null`. This
is the season opener. Per the project's anti-fabrication rule (prior-agent fabrication
history), the gaffer did **not** invent a prior squad; the brief is an **initial 15-man
construction** and the absence is recorded. Confidence: HIGH (checked the entry JSON).

---

## 2. Per-decision records

Format: signals (bucket→value→weight→note) → synthesis → output. `EV_final = P(start) × EV`.

### DECISION: Captain — HAALAND (c), Bruno (vc)
- market: Haaland shortest anytime-scorer of GW1 (~1.75, Bet365) · **HIGH**
- fixture: Man City (H) v Bournemouth, 65% win + highest goal env O2.5 ~68% · **HIGH**
- minutes[GATE]: started Community Shield, nailed · **PASS**
- EO: 72.5% owned + captain magnet → effective ownership >100% · **HIGH** (rank-protection)
- class-prior: ~0.85 xGI/90, 27 G in 25-26 · **HIGH**
- **Synthesis:** every bucket points one way. Low-info GW1 rule = captain the field's premium.
- **Output:** (C) Haaland, (VC) Bruno Fernandes. Confidence **HIGH**. No defer.
- **AM pushback:** conceded — "textbook, no change."

### DECISION: Anchor 2 — Bruno Fernandes (MID £12.0), + Man Utd stack (Mbeumo, Shaw)
- minutes[GATE]: Bruno & Mbeumo nailed HIGH; Shaw MED (fitness) · Bruno/Mbeumo PASS, Shaw PASS w/ flag
- penalty: Bruno undisputed 1st pen (Utd); Mbeumo backup pen · **HIGH**
- usage/style: Carrick's Utd finished 3rd 25-26; most settled elite attack; Bruno 129 pts in 17 · **HIGH**
- fixture: (both) v Hull — 64% win BUT O2.5 ~40% UNDER-lean (grindy) · **MED** (floor > ceiling)
- **Synthesis:** stacked to the club cap (3 MUN) for a high-floor, settled-attack, soft-opponent bet; accepted the low goal-ceiling as the cost of the floor.
- **Output:** Bruno + Mbeumo + Shaw. Confidence **HIGH** (Bruno), **MED-HIGH** (stack).
- **AM pushback (HELD, documented):** AM flagged three MUN assets concentrated in one
  under-lean game (whole-XI covariance) vs Semenyo (MCI £8.5) in the City-Bou shootout.
  **Gaffer HELD Mbeumo** (HIGH-nailed + backup pens + free; AM itself concluded "keep for
  floor"). Covariance concern **recorded**: Semenyo = named GW2 diversification/ceiling pivot.

### DECISION: Arsenal — clean sheet only (Raya GK + Gabriel DEF), NO attacker
- fixture: Arsenal (H) v Coventry, ~82% (heaviest GW1 fav), cleanest CS spot · **HIGH**
- minutes[GATE]: Arsenal ATTACK muddled — Gyökeres benched in Shield (Havertz CF); Saka
  load-managed + Achilles; Saliba & Timber OUT · attackers **FAIL/MED the gate**
- penalty: Arsenal pen DISPUTED (Saka vs Gyökeres) · discount → no pen EV to bank
- EO: Raya 32.3%, Gabriel 27.8% (template) · **HIGH**; Saka only 10.3% · skippable
- **Synthesis:** take the CS (both pass the gate + template) and refuse the attacking guess
  (fails the gate, disputed pens). Bank the mismatch defensively.
- **Output:** Raya + Gabriel; no Arsenal attacker. Confidence **HIGH**.
- **AM pushback:** conceded — "no attacker passes the minutes gate; Saka's 10.3% EO is skippable."

### DECISION: Template forwards/mids — João Pedro, Szoboszlai
- **João Pedro (CHE £7.5):** EO 57.9% (dominant budget-fwd template) · minutes HIGH (Alonso's
  talisman) · usage HIGH → **INCLUDE, HIGH.** Unlocks the two-premium build. AM conceded.
- **Szoboszlai (LIV £7.0):** EO 41.6% (surprise-heavy template) · minutes HIGH · BUT Liverpool
  diffuse under new mgr Iraola, pen DISPUTED (vs Isak), fixture Newcastle (A) shootout (bad CS
  but he's a mid). → **INCLUDE on EO alone; pen NOT counted.** Confidence **MED**.
  AM conceded ("41.6% EO decisive; keep, don't count pen, sell GW2-4").

### DECISION: 3rd forward — Calvert-Lewin (LEE £6.0)
- penalty: Leeds 1st pen · **MED-HIGH** · EO 25.9% (cheap-striker template) · minutes MED-HIGH
- **Synthesis:** best £6.0 pen-taking template forward; no reliable sub-£5.0 nailed FWD exists
  (enable via DEF/MID). **INCLUDE.** Confidence MED. AM conceded.

### DECISION: cheap enablers + bench (the AM's main battleground)
- **Accepted #1 (free, strictly better): Thomas (COV) → Diop (IPS £4.0).** Behind fragile
  Shaw, the first autosub was a Coventry DEF being battered @ Arsenal (~1-2 pts). Diop =
  nailed £4.0 (18.3%, field-backed), home v Sunderland (coin-flip, not a battering). Diop
  ordered **1st** on the bench. Price-neutral. Rationale: realised-floor of the autosub.
- **Accepted #2: start Yates (NFO, home v Leeds), bench Hughes (CRY).** Hughes carries a
  name-collision doubt (a "Hughes" also at Hull) + thin nailedness + worst enabler fixture
  (Everton-Palace, lowest goal cluster). Flagged for deadline identity/nailedness verify.
- **Accepted #3: Shaw's deadline pivot = Kayode (BRE), not Cash (AVL).** Cash is away in the
  Brighton-Villa shootout (poor CS); Kayode is home + HIGH-nailed (better CS floor).
- Kept: Mitchell (CRY £4.5, nailed, CS-lean Everton fixture), van Ewijk (COV £4.0, deep cover),
  Palmer (IPS £4.0, backup GK).

### DECISION: £0.0 bank (tension resolved by pushback)
- Research suggests ~£0.5m bank + ≥1 FT into GW2. Draft ran £0.0.
- **AM argued AGAINST fixing it:** near-costless for an *initial* squad (no immediate transfer
  to make; ≥1 FT into GW2 is automatic), and every fix (Raya→Pickford, Szoboszlai→cheaper)
  costs template EO or the best CS fixture. **Gaffer ACCEPTED: hold £0.0**, don't churn the core.

### DECISION: Optimizer — overruled (advisory only)
- The ILP objective is structurally sound (hard rules, valuation-drives-selection) but its
  data is thin: ~75% last-season pts/90 misprices summer movers on their old club, and a
  450-min floor hard-zeroes every promoted/new/returning player. Missing entirely: DEFCON
  (2026/27 rule), EO/rank objective, de-vigged odds, set-piece/penalty boosts, class-prior.
- **Output:** used as a structural sanity check + candidate generator only; the final 15 was
  hand-layered from the Tier-0/Tier-1 signals. See [optimizer-audit](signals/optimizer-audit.md).

---

## 3. Assistant-manager pushback ledger (accept/reject summary)

| # | AM challenge | Gaffer ruling | Rationale |
|---|---|---|---|
| 1 | Bench can't cover fragile Shaw (Thomas→Diop) | **ACCEPTED** | Free, strictly-better autosub floor. |
| 2 | Hughes shaky starter (name-collision + fixture) | **ACCEPTED** | Start Yates; bench + verify Hughes. |
| 3 | Shaw pivot Cash→Kayode | **ACCEPTED** | Kayode home/HIGH-nailed; Cash in a shootout. |
| 4 | Mbeumo→Semenyo (covariance/ceiling) | **HELD** | Keep Mbeumo's floor; Semenyo = GW2 pivot. AM concurred. |
| — | £0.0 bank | **HELD** (per AM) | AM argued against fixing; costless for initial build. |
| — | Captain / Arsenal CS-only / Szoboszlai / 2-premiums / João Pedro / CL | **CONCEDED by AM** | Validated as correct. |

Full text: [assistant-manager-pushback.md](signals/assistant-manager-pushback.md).

---

## 4. Confidence & defer flags (what could still move the XI)

- **HIGH / locked:** captaincy; two-premium spine; Arsenal CS; João Pedro; team set; prices/EO.
- **MED / re-check at deadline (defer):** Shaw fitness (→Kayode); Hughes identity+nailedness;
  Yates start under Glasner; Isak/Palmer/Saka/Watkins fitness (not owned, monitor); anytime-
  scorer & CS odds boards (not posted until ~20-21 Aug — re-pull for captaincy confirmation).
- **Anti-fabrication residue:** the class-prior xGI/90 decimals are single-sourced
  (xgstat.com; FBref/Understat bot-blocked) — rankings trustworthy, exact numbers approximate.

## 5. Post-GW review hooks (fill after GW1 — for [#21](https://github.com/ropats16/fpl-pi-manager/issues/21))
- [ ] Actual points per pick vs projection; captain outcome vs alternatives.
- [ ] Did the Arsenal-CS-over-attack call pay? Did Bruno+Mbeumo's low-ceiling Hull stack return?
- [ ] Was holding Mbeumo over Semenyo right (covariance)? Was Szoboszlai's template worth it?
- [ ] Did any deferred team-news call (Shaw/Hughes/Yates) flip, and was the pivot correct?
- [ ] Were the weights leaned on (structural-heavy, template-lean) validated by outcomes?
