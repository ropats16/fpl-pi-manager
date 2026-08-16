# Squad Construction & Budget Allocation — FPL 2026/27

Research on building the 15-man squad as a **constrained-portfolio / structural** problem, distinct from per-player valuation. For the FPL autonomous-manager project (has a PuLP/ILP optimizer already).

## Verified rules baseline (FPL 2026/27)

Cross-checked against official + high-trust sources; all match the task's stated constraints:

- **£100.0m** budget; **15 players = 2 GK / 5 DEF / 5 MID / 3 FWD**. [Premier League — Scout's golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad) · [Onside — budget explained](https://onsidearena.com/guides/fpl-budget-explained)
- **Max 3 players per PL club.** [PL](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Starting XI = 11**, any formation with **≥1 GK, ≥3 DEF, ≥1 FWD** (min 2 MID in practice from position maths). [Onside](https://onsidearena.com/guides/fpl-budget-explained) · [worldinsport rules guide](https://worldinsport.com/fantasy-premier-league-rules-scoring/)
- **4 bench slots** (1 GK + 3 outfield) in a priority order; autosubs fire when a starter plays 0 minutes, respecting the order and keeping a legal formation. [Onside](https://onsidearena.com/guides/fpl-budget-explained) · [FFScout — autosubs](https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs)
- **DEFCON (2025/26+, retained 26/27):** DEF get **+2 for ≥10 CBIT** (Clearances, Blocks, Interceptions, Tackles); MID/FWD get **+2 for ≥12 CBIRT** (CBIT + Ball Recoveries). Capped at +2/match. **New for 26/27:** BPS re-weighted so clearances/blocks/interceptions give *less* bonus, reducing centre-back double-dipping but leaving defensive-mid DEFCON intact. [FPL Oracle](https://fploracle.team/blog/defensive-contributions-fpl-explained) · [Operation Sports](https://www.operationsports.com/what-is-defcon-in-fpl-defensive-contribution-points-explained/)

---

### 1. Budget-allocation shape (stars-and-scrubs vs balanced) — **Suggested heuristic: balanced-but-strategic; ~40% MID / ~28% FWD / ~25% DEF / ~7% GK of *effective* budget; concentrate premiums in MID+FWD, find value in DEF/GK. Weight: HIGH.**

- **Hard evidence from top-50 managers (2025/26 total / effective budget):** GK 9.3% / 6.4%; DEF 25.8% / 23.0%; **MID 37.5% / 40.7%**; FWD 27.3% / 29.9%. All-time top-50 nearly identical (MID 38.5% / 42.6%). This is a **balanced, value-driven** split, *not* extreme stars-and-scrubs. [FFFix — Top 50 budget](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-budget-25-26/)
- **Midfield is the value-richest position** — highest-returning players are almost always MIDs; premiums should concentrate there. [FFFix — Top 50 team setup](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-team-setup-25-26/)
- **Forwards "tend to be overpriced"** — premium FWDs appeared in only 3 of 6 optimal historical teams; loading attack beyond ~1 premium (Haaland) is often inefficient. [FantasyFootballReports — formation](https://www.fantasyfootballreports.com/best-formation-fpl/)
- **"Effective budget" reframing:** the ~£100m is really the spend on your XI; bench points are near-zero, so the true optimization target is XI xPts, not raw 15-man cost. [Onside](https://onsidearena.com/guides/fpl-budget-explained)
- **Folklore flag:** "stars and scrubs always wins" is DFS folklore (basketball/baseball auctions), not FPL evidence — the FPL top-50 data shows a *moderated* concentration (premiums in 2-3 spots, but real money still spread across a 4-MID / balanced spine). [FantasyPros — stars & scrubs](https://www.fantasypros.com/2019/06/stars-and-scrubs-or-balanced-auction-roster-how-to-decide-fantasy-football/) · [FFFix budget](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-budget-25-26/)

**How to apply:** In the optimizer, don't just cap total cost at £100m — bias the objective toward XI xPts and let premiums land in MID/FWD; treat ~£17–20m DEF and £4.0–4.5m GK as value zones. Loading premiums into attack past one anchor striker is *worse* than the same money in midfield.

---

### 2. Bench strategy & the GK question — **Suggested heuristic: cheap functional bench (£17–18m for 4) that is near-nailed enough for autosub cover, NOT dead fodder; 1 premium/mid GK + a £4.0m non-playing backup. Weight: MEDIUM-HIGH.**

- **Bench-order value is real but small:** good bench ordering is worth ~**5–10 points/season from autosubs**; most managers ignore it. Put highest-xPts, most-nailed player in bench slot 1. [FPL Copilot — xPts](https://fplcopilot.com/blog/expected-points-explained)
- **Autosub mechanics constrain "playing bench":** bench points only count if a starter plays 0 min; you can't force it (that's the Bench Boost chip's job). So paying up for a bench that plays is mostly injury/rotation insurance, not a points engine. [FFScout — autosubs](https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs) · [LiveFPL — autosubs](https://www.livefpl.com/blog/fpl-auto-subs)
- **Strong squads run "a cheap, functional bench and concentrate the money in the starting XI"** — but a *too*-cheap bench leaves you exposed to non-starters (autosubs whiff). Bench = near-nailed cheap starters, not £4.0m benchwarmers who never play. [Onside](https://onsidearena.com/guides/fpl-budget-explained)
- **GK: single reliable starter + £4.0m fodder beats a genuine rotation pair for most.** Top-50 managers "pay for one reliable GK but not two"; several £4.0m starting keepers make this cheap. [FFFix budget](https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-budget-25-26/) · [allaboutfpl — GKs 26/27](https://allaboutfpl.com/2026/08/best-fpl-goalkeepers-to-target-for-the-2026-27-fpl-season/)
- **Rotation pair (2× £4.5m) is a defensible alternative** when no clear £4.0m starter exists; saves the premium-GK spend for an outfield upgrade. [OneFPL — rotation pairs](https://onefpl.com/blog/best-fpl-goalkeeper-defender-rotation-pairs-2026-27) · [FFScout — £4.0–4.5m GKs](https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27)

**How to apply:** Encode a minimum "expected-minutes" floor on the 3 outfield bench slots (autosub insurance) but cap their cost hard. GK: model as {1 starter GK weighted at ~full xPts + 1 backup weighted ~0}; only justify a 2nd playing GK if the pair's combined xPts beats a single starter + an outfield upgrade of the saved cash.

---

### 3. Formation at season start & DEFCON shift — **Suggested heuristic: 3-4-3 / 3-5-2 as default (min 4 MID), but 4-4-2 is now genuinely competitive because DEFCON gives cheap DEF a scoring floor. Weight: MEDIUM (formation is downstream of players).**

- **6-season average of optimal teams ≈ (3.17 DEF, 4.5 MID, 2.33 FWD) → rounds to 3-5-2.** "4+ midfielders appeared in all six seasons." [FantasyFootballReports](https://www.fantasyfootballreports.com/best-formation-fpl/)
- **DEFCON revives "5 at the back?" and makes 4-4-2 a real season-start option:** £5.5–6m defenders gain reliability via CBIT floor; running 4 DEF ~£5m avg (VVD, Tarkowski, budget CBs) buys DEFCON + clean-sheet upside for ~£20m. [FantasyFootballReports](https://www.fantasyfootballreports.com/best-formation-fpl/) · [RotoWire — best formation 26/27](https://www.rotowire.com/soccer/article/best-fpl-formation-2026-27-which-shape-wins-fantasy-premier-league-127303)
- **DEFCON structurally re-prices defensive mids:** previously "overlooked entirely" DMs now score independent of attacking returns — a genuine new archetype competing for MID slots. [FFScout — DefCon revolution](https://www.fantasyfootballscout.co.uk/2026/05/24/2025-26-the-defcon-revolution-the-future-of-fpl)
- **26/27 BPS tweak trims centre-back bonus double-dip** → slightly favors DMs over pure CBs for the DEFCON+bonus stack; don't over-value CB bonus. [FPL Oracle](https://fploracle.team/blog/defensive-contributions-fpl-explained)
- **Core principle:** "It's not about the formation, but about the players" — formations sharing 9 core players perform similarly; formation is an *output* of player selection, not an input. [FantasyFootballReports](https://www.fantasyfootballreports.com/best-formation-fpl/)

**How to apply:** Don't hard-pin a formation. Let the ILP choose the XI formation freely within legal bounds (≥3 DEF, ≥1 FWD, ≥2 MID); DEFCON xPts should be *in the player scores* so the solver naturally lands 4-at-the-back when cheap DEFCON defenders out-score a 5th mid. Enforce ≥4 MID *in the 15* as a soft prior (midfield value density), not a hard XI constraint.

---

### 4. Optimizer objective & constraints (ILP encoding) — **Suggested heuristic: objective = decay-weighted, bench-weighted, captain-doubled multi-GW xPts; NOT raw single-GW sum. Weight: HIGH (this is the project's core).**

- **Gold-standard tool (sertalpbilal FPL-Optimization-Tools):** multi-period MILP solved with **HiGHS via highspy**; `solve_multi_period_fpl(horizon, objective, decay_base, bench_weights, ...)`. Objective supports a **decay_base** (future GWs discounted geometrically, commonly ~0.84–0.9) and per-slot **bench_weights** (bench players contribute fractional xPts, e.g. ~0.1–0.15) so the solver values bench cover without over-paying. [sertalpbilal — multi_period.py](https://github.com/sertalpbilal/FPL-Optimization-Tools/blob/main/src/multi_period.py) · [repo](https://github.com/sertalpbilal/FPL-Optimization-Tools)
- **Academic ILP (Ramezani & Dinh, arXiv 2505.02170):** formulates squad selection as ILP maximizing **multi-gameweek** expected points under budget + composition + club-quota constraints, **with bench weighting** and fixture-difficulty/form trajectories; shows systematic optimization beats heuristic selection. [arXiv 2505.02170](https://arxiv.org/pdf/2505.02170v3) · [HTML](https://arxiv.org/html/2505.02170v2)
- **Standard constraint set** (all linear, binary decision vars per player): Σcost ≤ 100.0; Σplayers = 15; per-position counts = 2/5/5/3; per-club Σ ≤ 3; XI: Σstart = 11, GK_start = 1, DEF_start ≥ 3, FWD_start ≥ 1, start ≤ squad; captain: exactly 1, captain ⊆ starters, +1× extra weight. [eirikur.dev — optimal team DP/ILP](https://eirikur.dev/blog/2024-08-05-fpl-and-dp/) · [spinalwiz/fpl-optimiser](https://github.com/spinalwiz/fpl-optimiser)
- **Objective beyond raw sum recommended:** (a) **captaincy** double-counts best starter; (b) **bench weight** ~0.1 keeps bench cheap-but-alive; (c) **multi-GW decay** avoids one-week fixture chasing; (d) optionally weight each player's xPts by **P(start)/expected minutes** so nailedness is priced in. [fplcopilot xPts](https://fplcopilot.com/blog/expected-points-explained) · [sertalpbilal](https://github.com/sertalpbilal/FPL-Optimization-Tools)

**How to apply:** Objective ≈ Σ_gw decay^(gw) · [ Σ_starters xPts·P(play) + captain_bonus·max_starter + bench_weight · Σ_bench xPts ]. Keep all six rule constraints as hard linear constraints; put DEFCON and minutes into the per-player xPts, not into structural constraints. This lets structure emerge from valuation rather than being hand-coded.

---

### 5. Max-3-per-club structural impact — **Suggested heuristic: hard constraint, non-negotiable; forces min ~5 clubs across 15; use it to bound stacking, not eliminate it. Weight: HIGH (constraint) / structural.**

- **Mathematical floor:** 15 players ÷ 3-per-club ⇒ **minimum 5 clubs**; the constraint caps concentration and is the main structural brake on "team stacking." [fantasyfootballbible](https://fantasyfootballbible.co.uk/how-to-play/multiple-players-one-team/)
- **Research-efficiency upside of stacking to the cap:** doubling/tripling up on a club you know deeply (line-ups, set-pieces, patterns) reduces the number of teams to model and can improve decision quality — a *structural* argument independent of covariance. [FFScout — double/triple up](https://www.fantasyfootballscout.co.uk/2021/02/11/double-or-triple-up-how-much-trust-should-fpl-managers-put-in-one-club/) · [fantasyfootballbible](https://fantasyfootballbible.co.uk/how-to-play/multiple-players-one-team/)
- **Enforcement nuance:** a mid-season transfer can leave >3 from a club without forcing an immediate sale — but the optimizer building a fresh squad must treat ≤3 as hard. [WebSearch summary; fantasyfootballbible](https://fantasyfootballbible.co.uk/how-to-play/multiple-players-one-team/)
- **ILP reality:** the club-quota is a standard linear constraint (Σ per club ≤ 3) in every serious FPL MILP. [eirikur.dev](https://eirikur.dev/blog/2024-08-05-fpl-and-dp/)

**How to apply:** Keep Σ(players per club) ≤ 3 as a hard constraint. Covariance/stacking payoff is handled elsewhere in valuation; structurally, the only knob here is whether to *allow the solver to hit 3* on strong clubs (yes) vs. artificially spreading (no — that throws away value). No tuning needed beyond the hard cap.

---

### 6. GW1-specific construction — **Suggested heuristic: template-leaning core + price-point flexibility + ~£0.5m bank; avoid early differentials/aggression; captain the premium the field owns. Weight: HIGH for the opening squad.**

- **Template core is forming early (26/27):** Haaland, B. Fernandes, João Pedro, Szoboszlai, Rogers — low information ⇒ crowd wisdom is a defensible prior for GW1. [FFFix — template 26/27](https://www.fantasyfootballfix.com/blog-index/fpl-template-team-2026-27/)
- **Price-point flexibility is the key GW1 skill:** "That £8.0m price point is crucial because it lets you transfer in almost any other midfielder in one move." Pick prices that keep one-move pivots open across the early weeks. [PL — Scout's golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Bank ~£0.5m** to ride early price rises and keep flexibility; you will *not* pick the perfect XI in GW1. [FFFix — template](https://www.fantasyfootballfix.com/blog-index/fpl-template-team-2026-27/) · [PL golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Build around GW1–5 and bank free transfers** (up to 5 stored) — construct so the squad survives to GW6 with roll-forward flexibility rather than needing early hits. [PL golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Captain the field's premium (e.g. Haaland ~74% owned):** "no need to go against him early because so many rivals adopt the same tactic" — low-info GW1 favors template captaincy to avoid rank volatility. [PL golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Pre-season fitness gate:** replace any player who doesn't start their final 1–2 friendlies (esp. post-World-Cup fatigue in 26/27). [PL golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)
- **Folklore flag:** "swing for differentials in GW1" is contrarian folklore; the evidence (low information + rank-risk asymmetry) favors template-leaning openers, saving aggression for when data accrues. [FFFix template](https://www.fantasyfootballfix.com/blog-index/fpl-template-team-2026-27/) · [PL golden rules](https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad)

**How to apply:** For GW1, blend optimizer xPts with an ownership/template prior (shrink toward the crowd under uncertainty), constrain to leave ~£0.5m bank, and prefer players at "round" price points (£8.0m mid, £4.0m fodder) so downstream single-move transfers stay open. Captain = highest-xPts premium starter; don't differential the armband in GW1.

---

## Sources

- Premier League — Scout's golden rules for opening squad: https://www.premierleague.com/en/news/4685204/the-scouts-golden-rules-for-picking-an-opening-fpl-squad
- Premier League — DEFCON explainer: https://www.premierleague.com/en/news/4361991 (404 at fetch; corroborated below)
- Onside — FPL budget/rules explained: https://onsidearena.com/guides/fpl-budget-explained
- worldinsport — 2026/27 rules & scoring: https://worldinsport.com/fantasy-premier-league-rules-scoring/
- FPL Oracle — Defensive Contributions 26/27: https://fploracle.team/blog/defensive-contributions-fpl-explained
- Operation Sports — What is DefCon: https://www.operationsports.com/what-is-defcon-in-fpl-defensive-contribution-points-explained/
- FFScout — DefCon revolution & future of FPL: https://www.fantasyfootballscout.co.uk/2026/05/24/2025-26-the-defcon-revolution-the-future-of-fpl
- FFScout — how substitutes/autosubs work: https://www.fantasyfootballscout.co.uk/2023/06/01/how-do-substitutes-work-in-fpl-and-what-are-autosubs
- FFScout — double/triple up on one club: https://www.fantasyfootballscout.co.uk/2021/02/11/double-or-triple-up-how-much-trust-should-fpl-managers-put-in-one-club/
- FFScout — best £4.0–4.5m GKs 26/27: https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27
- FFFix — Top 50 managers budget 25/26: https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-budget-25-26/
- FFFix — Top 50 managers team setup 25/26: https://www.fantasyfootballfix.com/blog-index/fpl-top-50-tips-team-setup-25-26/
- FFFix — Template team 26/27: https://www.fantasyfootballfix.com/blog-index/fpl-template-team-2026-27/
- FantasyFootballReports — best formation (DEFCON impact): https://www.fantasyfootballreports.com/best-formation-fpl/
- RotoWire — best FPL formation 26/27: https://www.rotowire.com/soccer/article/best-fpl-formation-2026-27-which-shape-wins-fantasy-premier-league-127303
- FPL Copilot — Expected Points (xPts) & bench ordering: https://fplcopilot.com/blog/expected-points-explained
- LiveFPL — auto subs: https://www.livefpl.com/blog/fpl-auto-subs
- OneFPL — rotation pairs 26/27: https://onefpl.com/blog/best-fpl-goalkeeper-defender-rotation-pairs-2026-27
- allaboutfpl — best GKs 26/27: https://allaboutfpl.com/2026/08/best-fpl-goalkeepers-to-target-for-the-2026-27-fpl-season/
- sertalpbilal — FPL-Optimization-Tools (HiGHS MILP, multi_period): https://github.com/sertalpbilal/FPL-Optimization-Tools/blob/main/src/multi_period.py · https://github.com/sertalpbilal/FPL-Optimization-Tools
- spinalwiz — fpl-optimiser (PuLP/LP): https://github.com/spinalwiz/fpl-optimiser
- eirikur.dev — picking an optimal fantasy team (ILP/DP): https://eirikur.dev/blog/2024-08-05-fpl-and-dp/
- Ramezani & Dinh — A data-driven framework for team selection in FPL (arXiv): https://arxiv.org/pdf/2505.02170v3 · https://arxiv.org/html/2505.02170v2
- fantasyfootballbible — multiple players from one club: https://fantasyfootballbible.co.uk/how-to-play/multiple-players-one-team/
- FantasyPros — stars & scrubs vs balanced (auction, folklore ref): https://www.fantasypros.com/2019/06/stars-and-scrubs-or-balanced-auction-roster-how-to-decide-fantasy-football/
