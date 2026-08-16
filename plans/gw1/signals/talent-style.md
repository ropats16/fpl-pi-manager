# GW1 2026-27 — Talent, team-style & class-player-prior signals

Structural (pre-season) talent layer for the [#25](https://github.com/ropats16/fpl-pi-manager/issues/25)
GW1 build. Angle: underlying multi-season quality, team tactical archetype, confirmed
penalty/set-piece takers, usage-share, and new-signing role impact — the signals that
need little-to-no current-season data. Method basis:
[class-player-prior.md](../../research/team-selection/class-player-prior.md),
[fixtures-and-context.md#team-style--usage-share](../../research/team-selection/factors/fixtures-and-context.md),
[predictive-signals.md](../../research/team-selection/factors/predictive-signals.md).

**Compiled 2026-08-16. GW1 deadline Fri 2026-08-21 17:30 UTC. Season opens 2026-08-22.**

> **Anti-fabrication note.** Every factual claim below carries a live URL. Where sources
> conflict I mark the row **DISPUTED** and do not manufacture certainty. The class-player
> xGI/90 table is **single-sourced (xgstat.com)** because FBref and Understat were bot-blocked
> at compile time — those decimals are **MEDIUM confidence / approximate**, cross-checked only
> qualitatively against independently-sourced goal tallies. Re-verify all penalty orders and
> promoted-club data against GW1 team-sheets before locking picks.

---

## 1. The 20 confirmed clubs (and a correction to the repo warning)

**Finding that overturns the brief's premise:** the repo's "Coventry/Hull" team set is **NOT
corrupted — it is correct.** Live authoritative data confirms Coventry City, Ipswich Town and
Hull City as the three promoted clubs for 2026-27; Wolves, Burnley and West Ham went down.

The 20 clubs (two independent sources):
Arsenal, Aston Villa, Bournemouth, Brentford, Brighton, Chelsea, **Coventry**, Crystal Palace,
Everton, Fulham, **Hull**, **Ipswich**, Leeds, Liverpool, Manchester City, Manchester United,
Newcastle, Nottingham Forest, Sunderland, Tottenham.
Sources: [Premier League official](https://www.premierleague.com/en/news/4673099/the-202627-premier-league-season-officially-starts/),
[Yahoo Sports teams guide](https://sports.yahoo.com/articles/2026-27-premier-league-teams-133302059.html).

### Record managerial turnover — nine new managers (biggest since 1946-47)
This is a first-order structural signal: a new manager restructures **who** accumulates
attacking returns, independent of transfers. Full line-up
([Premier League](https://www.premierleague.com/en/news/4679012/manager-line-up-complete-for-202627-season),
[Opta Analyst](https://theanalyst.com/articles/premier-league-new-managers-2026-27)):

| Club | Manager 2026-27 | New? | System implication |
|---|---|---|---|
| **Man City** | **Enzo Maresca** (← Guardiola, 10-yr reign ended) | **YES** | Full reset; ~80% squad turnover per Maresca. Attacking hierarchy in flux beyond Haaland. |
| **Liverpool** | **Andoni Iraola** (← Slot) | **YES** | High-press/transition (his Bournemouth style) + Salah gone = attack reshuffle, high uncertainty. |
| **Chelsea** | **Xabi Alonso** (PL debut) | **YES** | New system + record Rogers signing; deep, contested attack. |
| **Newcastle** | **Matthias Jaissle** (← Howe) | **YES** | New manager into a gutted attack (Isak, Gordon, Bruno G all sold). |
| **Tottenham** | **Roberto De Zerbi** (first full season) | **YES** | Possession-heavy; big midfield spend. |
| **Nott'm Forest** | **Oliver Glasner** (← Palace) | **YES** | New system; lost Elliot Anderson. |
| **Crystal Palace** | **Pierre Sage** (PL debut) | **YES** | New system. |
| **Bournemouth** | **Marco Rose** (← Iraola) | **YES** | New manager + first Euro campaign → rotation risk. |
| **Fulham** | **Álvaro Arbeloa** (PL debut) | **YES** | New system + marquee striker García he knows from Real Madrid. |
| Arsenal | Mikel Arteta | No | **Most stable top-6 attack; defending champions (won 2025-26).** |
| Aston Villa | Unai Emery | No | Stable, but lost talisman Rogers. |
| Man Utd | Michael Carrick | No | Led Utd to **3rd in 2025-26**; elite settled attack (see §4). |
| Everton | David Moyes · Brentford Keith Andrews · Brighton Fabian Hürzeler · Leeds Daniel Farke · Sunderland Régis Le Bris · Coventry Frank Lampard · Hull Sergej Jakirović · Ipswich Gary O'Neil | mixed | — |

**Takeaway:** the four clubs with the *cleanest, most stable* attacking structure for a GW1
one-shot are **Man Utd (Carrick), Arsenal (Arteta), Aston Villa (Emery) and Man City (Haaland
still the fixed point despite the Maresca reset).** Liverpool, Chelsea and Newcastle carry
new-manager + roster-churn uncertainty — avoid single-player commitment there until roles settle.

---

## 2. Class-player prior — proven-elite underlying quality

Apply the [shrinkage prior](../../research/team-selection/class-player-prior.md): these players'
selection should rest on 2-3 seasons of underlying output, **not** a quiet friendly. κ (prior
strength) is my qualitative read of history length × consistency × role security.

> **Confidence caveat:** xGI/90 figures are **single-sourced (xgstat.com, PL-only), MEDIUM
> confidence, ±0.05**. FBref/Understat were bot-blocked. Ordering triangulates with
> independently-sourced goal tallies (cited in §4/§6), so the *ranking* is trustworthy even where
> exact decimals are soft. xGI/90 = xG+xA per 90.

| Player | Team 26-27 | Pos | xGI/90 (23-24 / 24-25 / 25-26) | multi-szn xGI/90 | κ (prior strength) | Role / flag |
|---|---|---|---|---|---|---|
| **Erling Haaland** | Man City | CF | 1.02 / ~0.75 / 0.79 | **~0.85 (elite)** | **κ≈18** | Nailed 29-34 starts/szn; 27 G + 8 A, 239 pts in 25-26 — the anchor. |
| **Bukayo Saka** | Arsenal | RW | 0.76 / 0.73 / ~0.55 | ~0.68 | κ≈12 | Nailed when fit; missed chunks of 24-25/25-26. 2.47 chances created/90. |
| **Cole Palmer** | Chelsea | CAM/RW | 0.79 / 0.64 / ~0.45 | ~0.63 | κ≈12 | Creative hub + pen taker; injury-hit 25-26 (10 G, 24 apps). Multi-szn xG overperformer. |
| **Ollie Watkins** | Aston Villa | CF | 0.60 / 0.65 / ~0.60 | **~0.62 (very consistent)** | **κ≈14** | **Best minutes-security premium-ish FWD** — 33-37 starts/szn. Highest npxG/90 in £8m bracket. |
| **Alexander Isak** | Liverpool | CF | 0.69 / 0.69 / low | ~0.69 (pre-injury) | κ≈6 ↓ | 23 G at Newcastle, but 25-26 injury-wrecked (8 starts); new role behind crowded LFC front line = **role risk, κ cut**. |
| **Bryan Mbeumo** | Man Utd | RW/CF | ~0.62 / 0.52 / ~0.50 | ~0.55 | κ≈12 | Nailed 31-38 starts/szn; **biggest PL xG overperformer 2024-25 (+7.7)** — finishing-whitelist name. |
| **Matheus Cunha** | Man Utd | LW/CF/CAM | — / 0.52 / 0.36 | ~0.45 | κ≈8 | Nailed 29 starts both szns; second season at Utd. |
| **Jarrod Bowen** | West Ham* | RW/CF | 0.50 / 0.42 / ~0.40 | ~0.44 | κ≈10 | *West Ham relegated — not in PL 26-27; listed for reference only.* |
| **Morgan Rogers** | Chelsea | CAM | — / 0.33 / 0.31 | ~0.32 | κ≈9 | **Moved Villa→Chelsea (£117m).** High floor (37 starts both szns), modest per-90; usage share now contested at Chelsea. |
| **Martin Ødegaard** | Arsenal | CAM/CM | 0.39 / 0.43 / 0.28 | ~0.37 | κ≈8 ↓ | Creator not scorer; 25-26 injury-hit. Secondary pen option. |
| **Chris Wood** | Nott'm Forest | CF | 0.56 / 0.47 / low | ~0.50 | κ≈4 ↓ | **Role collapsed 25-26 (11 starts, age 34) — prior invalidated, avoid.** |
| ~~Mohamed Salah~~ | **LEFT PL** | — | 0.95 / 0.88 / ~0.50 | — | — | **Departed Liverpool on a free — NOT in FPL 26-27.** Removes the two-premium dilemma. |
| ~~Son Heung-min~~ | **LEFT PL (LAFC)** | — | — | — | — | No longer in PL — exclude. |

Primary source (all rows): xgstat.com player pages, e.g.
[Haaland](https://www.xgstat.com/players/erling-haaland?season=2023-2024&competition=premier-league)
(swap slug/season). Goal-tally corroboration cited in §4/§6.

**Finishing-overperformer whitelist** (proven multi-season goals > xG — legitimately sit above
xG, don't over-regress): **Mbeumo** (biggest PL overperformer 24-25), **Palmer** (top-4
overperformer). **Haaland** overperforms in volume but his edge is xG *quantity*, not sustained
overperformance (he underperformed slightly in 23-24) — value him on volume, not a finishing
multiplier. Source:
[Yahoo / Opta xG overperformers](https://sports.yahoo.com/premier-league-biggest-xg-overperformers-103500810.html),
[Brentford FC analysis (Mbeumo)](https://www.brentfordfc.com/en/news/article/analysis-bryan-mbeumo-brentford-premier-league-expected-goals).

---

## 3. Penalty & set-piece takers per club (2026-27)

Cross-checked across FFScout, AllAboutFPL, Fantasy Football Fix and Il Margine; disputes flagged.
Penalty duty ≈ +4 goals / +16-20 FPL pts per season for a lead taker on a pen-winning side — a
top-tier EV boost ([Opta Analyst](https://theanalyst.com/articles/premier-league-penalties-like-free-goal)).

| Club | 1st pen | 2nd pen | Corners | Direct FK | Changed summer? | Conf. |
|---|---|---|---|---|---|---|
| **Arsenal** | **DISPUTED: Saka vs Gyökeres** (Ødegaard 3rd) | — | Rice, Saka | Rice, Saka | Gyökeres arrival (25) unsettled it | **DISPUTED** |
| Aston Villa | Buendía / **Watkins** (disputed) | the other | Cash, McGinn | Buendía | Rogers (a taker) sold to Chelsea | MED |
| Bournemouth | **Kluivert** | Tavernier | Tavernier, Scott | Tavernier | **YES** — Semenyo→City; Kroupi injured | MED-HIGH |
| Brentford | **Igor Thiago** | Schade | Jensen, Damsgaard | Lewis-Potter | No (Wissa left → Thiago sole focal point) | HIGH |
| Brighton | Gross | O'Riley | Gross, Minteh | De Cuyper | No | HIGH |
| **Chelsea** | **Cole Palmer** | Enzo Fernández / João Pedro | James, Neto, Enzo | James, Enzo | No | HIGH |
| Coventry | Wright | Torp/Grimes | Grimes, Rudoni | Torp | Promoted | MED |
| Crystal Palace | **Mateta** | Sarr | Wharton, Pino | Pino | No | HIGH |
| Everton | Ndiaye | Garner | Garner, Dewsbury-Hall | Garner | No | HIGH |
| Fulham | **UNCONFIRMED** (Muniz/Iwobi/García contested) | — | Iwobi | Iwobi | **YES** — Jiménez (taker)→Wolves | **LOW** |
| Hull | McBurnie / Crooks (disputed) | the other | Giles | Belloumi | Promoted | MED-LOW |
| Ipswich | Clarke / Hirst (disputed) | Philogene | Philogene | Núñez | Promoted | MED-LOW |
| Leeds | **Calvert-Lewin** | Nmecha | Wilson, Stach | Stach | (DCL joined 25) | MED-HIGH |
| **Liverpool** | **DISPUTED: Szoboszlai (evidence-led) vs Isak (official FPL)** — Gakpo 3rd | — | Szoboszlai, Wirtz | Szoboszlai, Wirtz | **YES** — Salah gone | **MED** |
| **Man City** | **Haaland** | Marmoush | Cherki, Foden | Cherki, Reijnders | No | HIGH |
| **Man Utd** | **Bruno Fernandes** | Mbeumo | Fernandes, Mbeumo | Fernandes, Mbeumo | No | HIGH |
| Newcastle | **Woltemade** | Schär / Osula (disputed) | Hall, Schär | Hall | **YES** — Isak→LFC; Woltemade & Wissa in | MED |
| Nott'm Forest | Gibbs-White / Wood (disputed) | the other | A. Williams | Gibbs-White | No | MED-HIGH |
| Sunderland | Diarra | Le Fée | Xhaka, Le Fée | Xhaka | No | MED-HIGH |
| Tottenham | **Solanke** | Kudus | Porro, Kudus | Porro | No | HIGH |

Sources: [FFScout takers list](https://www.fantasyfootballscout.co.uk/2026/08/12/who-are-the-penalty-takers-at-all-20-premier-league-clubs),
[AllAboutFPL takers](https://allaboutfpl.com/2026/08/premier-league-penalty-set-piece-takers-2026-27-pl-season/),
[Fantasy Football Fix set-piece takers](https://www.fantasyfootballfix.com/blog-index/fpl-set-piece-takers-2026-27/),
[Il Margine per-club order](https://ilmargine.bet/penalty-takers/epl),
[Gyökeres/Saka dispute (Goal)](https://www.goal.com/en/lists/bukayo-saka-forced-hand-vital-arsenal-job-viktor-gyokeres-mikel-arteta-makes-surprise-call/bltc949cab97536689e).

**Highest-EV nailed pen takers (undisputed):** **Haaland** (City), **Bruno Fernandes** (Utd),
**Cole Palmer** (Chelsea), **Mateta** (Palace), **Igor Thiago** (Brentford), **Solanke** (Spurs),
**Calvert-Lewin** (Leeds). Arsenal and Liverpool pen EV is **split/uncertain** — discount both
takers' pen boost until GW1 team news resolves it.

---

## 4. Team-style / usage-share for high-value setups

Prefer the player who owns the **largest share** of his team's shots/xG/box-touches, not merely a
high per-90 ([method](../../research/team-selection/factors/fixtures-and-context.md#team-style--usage-share)).

- **Man City — central, Haaland-funnelled.** Haaland is the fixed goal outlet (27 G in 25-26,
  top scorer after 6 GW in all four City seasons). **Caveat:** Maresca reset + ~80% squad change
  = the *supply* structure around him is uncertain, but his share of City's box output stays
  maximal. Opening home vs Coventry & Ipswich → Triple-Captain candidate.
  [PL Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl).
- **Man Utd (Carrick, 3rd in 25-26) — genuinely elite, concentrated.** **Bruno Fernandes** is
  the creative + set-piece + penalty hub: 129 pts in 17 games under Carrick, scored/assisted in
  14 of 17, ~9 G + 24 A. **Mbeumo** is the nailed wide goal-threat (11 G, biggest overperformer
  24-25). Three forwards (Mbeumo/Cunha/Sesko) hit 10+ goals in 25-26. **Opening vs Hull &
  Ipswich = soft.** Best value-dense attack in the game.
  [PL Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl),
  [Man Utd FPL guide](https://scoutingstats.ai/articles/manchester-united-fpl-guide-2026-27).
- **Chelsea (Alonso) — talisman + creator, but deep.** **João Pedro** is the talismanic striker
  (177 FPL pts in 25-26, hat-trick in Alonso's first pre-season, 50%+ owned, £7.5m). **Palmer**
  is the creative + pen hub (injury-hit 25-26). Rogers (£117m) adds talent but **dilutes usage** —
  no single non-Pedro attacker is a safe nailed share. Opening vs Fulham/Brighton/Hull favourable.
  [João Pedro analysis](https://www.chaseyoursport.com/fantasy-football/joao-pedro-fpl-2026-27-analysis/12939).
- **Arsenal (Arteta, champions) — most stable.** **Gyökeres** the central outlet (14 G maiden
  season, 8 open-play), **Saka** the primary creator (2.47 chances/90) + shared goal threat.
  **Gabriel** owns set-piece aerial threat (3 G, 5 A, 18 CS, 209 pts). Pen identity the one wrinkle.
  [Arsenal preview](https://www.squawka.com/en/news/arsenal-premier-league-2026-27-preview/).
- **Aston Villa (Emery) — Watkins-funnelled, now more so.** Watkins is the focal striker
  (16 PL / 21 all-comp goals, highest npxG/90 in his bracket) and, with Rogers gone, the likely
  primary pen taker — **his usage share just went up.**
  [AllAboutFPL forwards](https://allaboutfpl.com/2026/08/best-fpl-forwards-at-each-price-point-for-the-2026-27-season/).
- **Brentford — Thiago is now the sole focal point.** Igor Thiago: 22 G (8 pens, 14 open play),
  2nd-best xG in the league, nailed pen taker; with Wissa sold to Newcastle his share of
  Brentford's attack is concentrated. £8.0m. Same source as above.
- **Newcastle (Jaissle) — diffuse / gutted.** Isak, Gordon and Bruno Guimarães all sold (£240m+).
  Woltemade (£69m, likely pen taker) and Wissa lead a **restructured, uncertain** attack under a
  new manager — captaincy-penalise for diffuse output.
- **Liverpool (Iraola) — diffuse / uncertain.** Salah gone, Ekitike out to 2027 (Achilles), Isak
  injury-prone, Gakpo linked away. Attacking returns spread across Isak/Wirtz/Szoboszlai/Gakpo
  with no clear GW1 focal point — **avoid single-player commitment.**
  [Opta squad audit](https://theanalyst.com/articles/liverpool-squad-audit-transfers-stats-2026-27).

---

## 5. Key summer-2026 transfers — role/usage impact

All **verified against ≥2 sources.** (Note: Mbeumo, Cunha, Isak, Wissa moved in **summer 2025**
and are established in their roles — a research leaf mislabeled them 2026; corrected here.)

**Proven-immediate role gains / concentration:**
- **Watkins (Villa)** and **Igor Thiago (Brentford)** — no move, but *gained* usage share as their
  clubs' co-focal-points departed (Rogers, Wissa). Cleaner nailed goal + pen roles.
- **João Pedro (Chelsea)** — cemented as Alonso's talisman (proven from 25-26).

**Usage LOST / diluted (avoid or downgrade):**
- **Aston Villa** lost talisman **Morgan Rogers → Chelsea (£117m British record)**; no like-for-like
  replacement as of 16 Aug — creative load redistributes.
  [Sky](https://www.skysports.com/football/news/11095/13564944/morgan-rogers-transfer-news-chelsea-complete-record-breaking-lb117m-deal-to-sign-forward-from-aston-villa).
- **Newcastle** gutted: **Gordon → Barcelona (€70m+)**, **Bruno Guimarães → Arsenal (£75m)**,
  plus Isak (2025). £240m+ sales.
  [Gordon (Al Jazeera)](https://www.aljazeera.com/sports/2026/5/30/barcelona-sign-england-winger-anthony-gordon-from-newcastle),
  [Bruno G (Sky)](https://www.skysports.com/football/news/11095/13570096/bruno-guimaraes-arsenal-sign-midfielder-in-lb75m-transfer-as-newcastle-surpass-lb240m-in-player-sales-this-summer).
- **Nott'm Forest** lost **Elliot Anderson → Man City (£116m)** + new manager.
- **Liverpool** lost **Salah** (free) — talisman + pen taker void, replacement unsigned.
- **Chelsea** attacking **glut** (Rogers in on top of Pedro/Palmer/Enzo/Estevão) → contested minutes.

**Bedding-in (don't pay GW1 hype):**
- **Gonzalo García → Fulham (~£36m, from a bit-part Real Madrid role)** — talented but adapting.
  [ESPN](https://www.espn.com/soccer/story/_/id/49523499/fulham-sign-gonzalo-garcia-real-madrid).
- **Semenyo → Man City (£64m, Jan 2026)** — settling into Maresca's system, not on pens.

**Defender & squad movers (the projection model's blind spot — see below):**
- **Marc Guéhi → Man City (£20m, completed Jan 2026)** — Palace lose their captain/CB, so
  **Palace's CS floor drops** (discount Palace DEF/GK); Guéhi becomes a potential nailed
  CS/DEFCON asset behind a City defence.
  [ESPN](https://www.espn.com/soccer/story/_/id/47630957/marc-guehi-seals-transfer-manchester-city-crystal-palace),
  [CPFC](https://www.cpfc.co.uk/news/announcement/marc-guehi-departs-crystal-palace-to-join-manchester-city/).
- **Spurs rebuilt a ball-playing back line under De Zerbi:** **Van Hecke (Brighton→Spurs, £52m)**,
  **Senesi (Bournemouth→Spurs, free)**, **Robertson (→Spurs, free)** — the two top PL
  ball-progressors last season. Van Hecke likely nailed; Spurs DEF a **new-look CS bet** if it
  gels. Correspondingly **Brighton and Bournemouth defences weakened.**
  [Van Hecke (Sky)](https://www.skysports.com/football/news/11675/13555493/jan-paul-van-hecke-tottenham-sign-brighton-defender-for-lb52m),
  [Spurs defence (PlanetFootball)](https://www.planetfootball.com/tottenham-hotspur/tottenham-dream-defence-2026-27-van-hecke-robertson).

### ⚠️ Model blind-spot: price summer movers on their NEW role, not the old one
The local projection model prices summer movers on their **old club's** usage/role, so its
class-player-prior signal is **unreliable for every player who changed clubs this window** — trust
this live-sourced layer over the model for them. Movers to re-price by NEW role/usage:
**Isak, Wissa, Woltemade** (attack); **Rogers** (Villa→Chelsea, usage *diluted*);
**Gordon, Bruno G** (left the affected clubs); **Guéhi, Van Hecke, Senesi, Robertson** (defenders);
**Gonzalo García, Semenyo** (bedding-in). Also model-invisible: **promoted-side assets** (Coventry
Haji Wright, Hull McBurnie/Charlie Hughes, Ipswich) and **new-manager systems** at nine clubs.

---

## 6. Best structural picks per position for GW1 (talent grounds, pre-price/fixture)

Anchored to the [PL Scout must-haves](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl)
and [best-by-position](https://allaboutfpl.com/2026/08/best-fpl-forwards-at-each-price-point-for-the-2026-27-season/) /
[FPL Copilot](https://fplcopilot.com/blog/best-fpl-players-2026-27).

**GKP** — David Raya (Arsenal, £6.0m, most-owned premium behind champions' defence);
budget: Verbruggen (Brighton, £4.5m, best sub-£5.0m scorer), or Petrović/Vicario/Leno £4.5m starters.

**DEF** — **Gabriel (Arsenal, £8.0m)** the standout: set-piece goal threat + CS + DEFCON, 209 pts
(3rd-best ever by a defender). Value: Mosquera (Arsenal, cheaper CS route), Neco Williams (£5.0m),
Charlie Hughes (Hull, cheapest high-volume DEFCON floor).

**MID** — **Bruno Fernandes (Man Utd, £12.0m)** — pen + set-piece + creation hub, soft opener;
the one clearly-nailed premium mid. Then **Mbeumo (Man Utd, £8.0m)** and **Palmer (Chelsea,
£9.5m, fitness bet)** / **Saka (Arsenal, £9.5m)**. Value: Anderson (£6.5m, Forest — flagged value).

**FWD** — **Haaland (Man City, £15.5m)** the non-negotiable anchor + captain (soft opening
double). Then **João Pedro (Chelsea, £7.5m)**, **Watkins (Villa, £8.0m, best minutes-security)**,
**Igor Thiago (Brentford, £8.0m, nailed + pens)**. Budget enablers: Calvert-Lewin (Leeds, £6.0m,
pens), Evanilson (Bournemouth, £6.0m), Mateta (Palace, £6.5m, pens).

**Structural verdict:** build around **Haaland (C) + Bruno Fernandes** as the twin proven anchors
(both undisputed pen takers, both soft openers), lean **Man Utd + Arsenal + Villa** for stable-
structure attack, take **João Pedro / Watkins / Thiago** as high-usage mid-price forwards, and
**underweight Liverpool, Chelsea depth pieces, and Newcastle** until new-manager roles settle.
