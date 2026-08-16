# GW1 2026-27 — Fixtures & Betting-Odds Signals

**Analyst:** Fixtures & Betting-Odds sub-agent · **For:** GW1 2026-27 initial 15-man squad (#25)
**Observation window:** 2026-08-16 (odds re-checkable until the Fri 2026-08-21 17:30 UTC deadline)
**Method refs:** [predictive-signals › betting-odds](../../research/team-selection/factors/predictive-signals.md#betting-odds) (de-vig),
[fixtures-and-context](../../research/team-selection/factors/fixtures-and-context.md) (position-split FDR, promoted fragility, home/away, style),
[importance-ranking](../../research/team-selection/importance-ranking.md).

> **Data provenance.** This report uses LIVE web sources only; every fixture and odd is
> URL-cited with an observation date. The earlier "corrupted team set" warning has been
> RETRACTED by the gaffer: the local FPL-API team set is CORRECT 2026-27 data and usable
> as a cross-check. Live web sources independently confirm the 20-team set below —
> **Coventry City, Hull City and Ipswich Town are the three genuine promoted sides**
> (Hull won the playoff final); West Ham, Burnley and Wolves went down. Local set and
> live sources agree.

---

## 1. Confirmed 20 teams (2026-27)

Arsenal, Aston Villa, Bournemouth, Brentford, Brighton & Hove Albion, Chelsea,
**Coventry City**, Crystal Palace, Everton, Fulham, **Hull City**, **Ipswich Town**,
Leeds United, Liverpool, Manchester City, Manchester United, Newcastle United,
Nottingham Forest, Sunderland, Tottenham Hotspur.

- **Promoted (fragility candidates):** Coventry City (up after 25 yrs), Ipswich Town (up after 1 yr / immediate return), Hull City (up after 9 yrs).
- **Relegated (gone):** Wolverhampton Wanderers, Burnley, West Ham United.
- Leeds United and Sunderland are NOT newly promoted this year — they came up in 2025-26 and survived; treat as established (2nd-season) sides, not fragility targets.

Source: [Wikipedia — 2026-27 Premier League](https://en.wikipedia.org/wiki/2026%E2%80%9327_Premier_League) (obs. 2026-08-16);
corroborated [Premier League](https://www.premierleague.com/en/news/4673099/the-202627-premier-league-season-officially-starts/),
[Yahoo Sports](https://sports.yahoo.com/articles/2026-27-premier-league-teams-133302059.html).

---

## 2. Confirmed GW1 fixtures

All times BST (UTC+1). GW1 deadline: **Fri 2026-08-21 17:30 UTC** (18:30 BST) — i.e. before the Fri opener.

| # | Home | Away | Date | KO (BST) |
|---|------|------|------|----------|
| 1 | Arsenal | Coventry City | Fri 21 Aug | 20:00 |
| 2 | Hull City | Manchester United | Sat 22 Aug | 12:30 |
| 3 | Everton | Crystal Palace | Sat 22 Aug | 15:00 |
| 4 | Ipswich Town | Sunderland | Sat 22 Aug | 15:00 |
| 5 | Nottingham Forest | Leeds United | Sat 22 Aug | 15:00 |
| 6 | Brentford | Tottenham Hotspur | Sat 22 Aug | 17:30 |
| 7 | Brighton & Hove Albion | Aston Villa | Sun 23 Aug | 14:00 |
| 8 | Manchester City | Bournemouth | Sun 23 Aug | 14:00 |
| 9 | Newcastle United | Liverpool | Sun 23 Aug | 16:30 |
| 10 | Fulham | Chelsea | Mon 24 Aug | 20:00 |

Source: [Sports Mole full fixture list](https://www.sportsmole.co.uk/football/feature/premier-league-2026-27-fixtures-full-list-tv-schedule-kickoff-times_603015.html) (obs. 2026-08-16);
corroborated per-match by [wincomparator](https://www.wincomparator.com/) and [Pinnacle](https://www.pinnacle.com/) match pages (dates/venues, obs. 2026-08-16).

> **Deadline note:** the Fri 21 Aug 20:00 Arsenal-Coventry match kicks off AFTER the
> 17:30 UTC deadline, so all 10 fixtures are live for GW1 selection. No blanks/doubles.

---

## 3. Per-match de-vigged probabilities

All odds observed **2026-08-16** (Arsenal row cross-checked to 08-17). 1X2 de-vigged
**multiplicatively** (fair_p = raw_p / Σ raw_p). Every match's line was cross-checked
against a SECOND independent source before inclusion (verification log at foot of section).
Book noted per row; where only mixed-book prices existed, flagged.

**1X2 (fair, de-vigged):**

| Match (H v A) | Book (raw H/D/A) | Overround | **Home %** | **Draw %** | **Away %** | Favourite |
|---|---|---|---|---|---|---|
| Arsenal v Coventry | mixed¹ 1.16 / 8.5 / 19.0 | ~3.9% | **~82** | ~12 | **~6** | Arsenal (heaviest of GW1) |
| Hull v Man Utd | Pinnacle 6.80 / 4.23 / 1.458 | 6.9% | 13.8 | 22.1 | **64.1** | Man Utd |
| Everton v Crystal Palace | Bet365 2.10 / 3.40 / 3.20 | 8.3% | **44.0** | 27.2 | 28.8 | Everton (thin) |
| Ipswich v Sunderland | Bet365 2.63 / 3.20 / 2.55 | 8.5% | 35.0 | 28.8 | 36.2 | ~pick'em (Sunderland nudge) |
| Nott'm Forest v Leeds | DraftKings 2.20 / 3.45 / 3.10 | 6.7% | **42.6** | 27.2 | 30.2 | Forest |
| Brentford v Tottenham | oddschecker 2.45 / 3.60 / 2.875 | 3.4% | **39.5** | 26.9 | 33.6 | Brentford (thin) |
| Brighton v Aston Villa | Bet365 2.25 / 3.60 / 2.88 | 6.9% | **41.6** | 26.0 | 32.5 | Brighton (thin) |
| Man City v Bournemouth | Bet365 1.44 / 5.00 / 6.00 | 6.1% | **65.4** | 18.8 | 15.7 | Man City |
| Newcastle v Liverpool | oddschecker 3.70 / 4.00 / 1.95 | 3.3% | 26.2 | 24.2 | **49.6** | Liverpool |
| Fulham v Chelsea | Bet365 3.25 / 3.60 / 2.00 | 8.6% | 28.3 | 25.6 | **46.1** | Chelsea |

¹ Arsenal row is mixed-book (Arsenal 1.16 Sports-King, Coventry 19.0 Bet365, Draw ~8.5 aggregate) so the overround/split is approximate; the ~82/12/6 split is corroborated by Dimers' model (81.5/13.1/5.3). Confidence HIGH on direction, MED on exact split.

**Goals & clean-sheet proxies** (standalone team clean-sheet Yes/No markets were **not open** at any reachable book 5-6 days out — confirmed independently by all 5 gathering agents; scorer markets likewise not posted. CS ranked in §5 from O/U + win-to-nil + opponent quality):

| Match | Over 2.5 (de-vig) | Goal env | BTTS Yes | Win-to-nil (proxy) | Notable scorer price |
|---|---|---|---|---|---|
| Arsenal v Coventry | ~60% | High, one-sided | No 1.50 (Ars keep out) | — | Gyökeres/Saka/Havertz shortest (unpriced²) |
| Hull v Man Utd | **~40% (UNDER-lean)** | Low / grindy | — | Man Utd correct-score 0-2 @7.1, 0-1 @7.5 | Šeško/Cunha/Mbeumo (unpriced²) |
| Everton v Crystal Palace | ~50% | **Lowest cluster** | Yes 1.75-ish | — | Beto +250, Mateta +195 |
| Ipswich v Sunderland | ~50% | Low | Yes 1.75 | Ips 4.50 / Sun 4.33 | not posted² |
| Nott'm Forest v Leeds | ~51% | Low-mid | Yes 1.67 | — | not posted² |
| Brentford v Tottenham | ~57% | Mid | Yes 1.53 | Bre 4.50 / Tot 5.00 | not posted² |
| Brighton v Aston Villa | ~59% | Mid-high | Yes 1.50 | — | Watkins ~2.63, Welbeck ~2.75 |
| Man City v Bournemouth | **~68% (highest)** | High | Yes 1.57 | **City 3.00** / Bou 13.0 | **Haaland 1.75** (shortest of GW1), Marmoush 3.00, Semenyo 2.75 |
| Newcastle v Liverpool | **~66%** | **High, two-way** | Yes ~1.44 | New 7.00 / Liv 3.33 | Salah = bookies' fav (unpriced²); Isak rumour³ |
| Fulham v Chelsea | ~59% | Mid-high | Yes 1.53 | — | João Pedro ~2.40 (tentative²) |

² Anytime-goalscorer boards do not post until ~1-2 days pre-kickoff (~20-21 Aug). Re-pull then; treat all named players here as unpriced favourites, NOT odds.
³ Unverified media report of an Isak availability/strike situation at Newcastle surfaced in scorer research — flagged and PASSED THROUGH to the minutes/availability analyst; not relied on here.

**Verification log (each match, 2 independent sources):** Arsenal-Cov: Sports-King + Dimers(Bet365) + Wincomparator. Hull-MUN: Pinnacle (my own fetch) + Betfair + Wincomparator. Everton-CP: statsinsider(Bet365) + Dimers + Betfair. Ipswich-Sun: Kickoff(Bet365/Coral) + Oddschecker + ESPN(DraftKings). Forest-Leeds: Oddschecker + ESPN(DraftKings) + Betfair. Brentford-Spurs: Oddschecker + Dimers(Bet365) + Kickoff. Brighton-Villa: statsinsider(Bet365) + ESPN(DraftKings) + Dimers. ManCity-Bou: Kickoff(Bet365/Coral) + Dimers + my own statsinsider anchor. Newcastle-Liv: Oddschecker + Dimers(Bet365) + Betfair/Betfred. Fulham-Che: Kickoff(Bet365/Coral) + Wincomparator + Dimers. All directions agreed across sources.

---

## 4. Ranked best-attacking spots (GW1)

Rank = P(win/control) × goal environment (de-vig O2.5) × opponent defensive fragility.
"Target the ATTACKERS of…":

| Rank | Team (venue) | Opponent | Why | Ceiling flag |
|---|---|---|---|---|
| **1** | **Man City (H)** | Bournemouth | 65% win **and** highest goal env of GW1 (O2.5 ~68%); Haaland shortest scorer price (1.75). Best control-×-goals combo. | **Elite** — captaincy anchor |
| **2** | **Arsenal (H)** | Coventry | Heaviest favourite of the week (~82%) vs a 25-yr-absent promoted defence. Goals slightly less certain (O2.5 ~60%) but total dominance; premium + budget Arsenal attackers both live. | **Elite** — captaincy anchor |
| **3** | **Liverpool (A)** | Newcastle | Joint-highest goal env (O2.5 ~66%); Liverpool attackers (Salah) huge ceiling. BUT away at a top-6 side, 50% win = higher variance. | High / volatile |
| **4** | **Man Utd (A)** | Hull | 64% win vs promoted defence — but **UNDER-lean line** (O2.5 ~40%), a grindy/controlled game script caps the ceiling. Good floor, muted explosion. | Good, capped |
| **5** | **Chelsea (A) / Brighton (H) / Villa (A)** | Fulham / Villa / Brighton | Open games (O2.5 ~59%), moderate favourites/near-even. Secondary attacking targets, not premiums-to-captain. | Moderate |

**Newcastle attackers** = a separate high-ceiling-high-variance case: 66% goal env but only 26% win (likely chasing) — game-state theory favours pacey/wide Newcastle attackers for a shootout, but the Isak rumour (§3, note ³) muddies it; defer to availability analyst.

**Attackers to FADE (promoted, wrong side of fragility):** Coventry, Hull, Ipswich forwards/mids — low floors. Also low-ceiling non-promoted spots: Everton/Palace and Ipswich/Sunderland attackers (bottom goal cluster).

---

## 5. Ranked best-clean-sheet spots (GW1)

Standalone CS Yes/No odds were **not posted** this far out (confirmed across all sources),
so ranking uses de-vig win%, O2.5 goal env, win-to-nil proxy, and opponent attack quality.
"Target the DEFENCE/GK of…":

| Rank | Team (venue) | Opponent | CS case |
|---|---|---|---|
| **1** | **Arsenal (H)** | Coventry | Cleanest CS spot of GW1: heaviest favourite vs weakest promoted attack; Coventry's expected goals-for is the lowest in the round. Elite Arsenal back line. |
| **2** | **Man City (H)** | Bournemouth | Win-to-nil 3.00 (best in GW1); high control. Caveat: high overall goal env (O2.5 68%) means Bournemouth *can* nick one on the counter — strong but not lock. |
| **3** | **Man Utd (A)** | Hull | UNDER-lean line (O2.5 ~40%) + promoted opponent favours CS; docked for being **away**. Best-value CS if Man Utd defenders are cheap. |
| **4** | **Forest (H) / Everton (H) / Crystal Palace (A)** | Leeds / Palace / Everton | Low goal-env cluster (O2.5 ~50%). Forest at home the pick; Palace (Glasner low-block) a live *away* CS differential; Everton home moderate. Coin-flip CS, budget-enabler tier. |
| **5** | **Ipswich (H) / Sunderland (A)** | each other | Low goals but both weak defensively — marginal, not recommended over the above. |

**CS spots to AVOID:** **Newcastle v Liverpool** (O2.5 ~66%, both defences exposed — neither GK/defence), **Brighton v Aston Villa** (~59%, BTTS 1.50), **Brentford v Tottenham** (~57%, both leak). Do not source clean sheets from these three matches.

---

## 6. Promoted-team fragility — GW1 exploit list

The three promoted sides and who is best-placed to exploit them in GW1
(method: [promoted-team fragility](../../research/team-selection/factors/fixtures-and-context.md#promoted-team-fragility) —
boost opponents' attack + CS xPts vs promoted; discount promoted attackers' floor;
EXCEPTIONS = promoted survival-GKs for save volume, cheap promoted CBs for DEFCON).

| Promoted side | GW1 fixture | Exploiter | Exploit type |
|---|---|---|---|
| **Coventry City** (up 25 yrs, weakest top-flight pedigree) | @ Arsenal (A) | **Arsenal** | Attack (soft defence) + **CS** (Arsenal keep out promoted side at home) — the single cleanest exploit of GW1 |
| **Hull City** (up 9 yrs) | vs Man United (H) | **Manchester United** | Attack (Man Utd forwards vs promoted defence); Man Utd CS is the softer half — away, and Hull carry some home threat |
| **Ipswich Town** (immediate return, most PL-battle-hardened of the three) | vs Sunderland (H) | (weak exploit) | Sunderland's attack is itself modest; this is the LEAST exploitable promoted fixture — no elite exploiter. Ipswich attackers to FADE, not a strong "attack Ipswich" spot |

- **Promoted attackers to fade** for GW1 floor: Coventry, Hull and Ipswich forwards/mids all carry low floors vs the base-rate concession asymmetry (they are on the wrong side of it).
- **Promoted-side EXCEPTIONS worth a look** (structural, from research): a nailed **budget Hull/Coventry/Ipswich GK** can bank save+bonus volume behind a leaky defence; a cheap nailed **promoted CB** is a candidate DEFCON route. These are value plays, not their outfield attackers.

---

## 7. Team-style / matchup notes for GW1

Style captured at TEAM level only (raw H2H history is tier-3 noise per research — deliberately excluded).

- **Arsenal vs Coventry** — champions vs newly-promoted at home = maximum expected game control → highest joint CS + goal-ceiling fixture of the week ([game-state](../../research/team-selection/factors/fixtures-and-context.md#game-state--script)). Prime captaincy/CS stack.
- **Man City vs Bournemouth** — City big home favourite; Bournemouth ship chances on the counter. High City goal ceiling; strong (but not elite-lock) CS.
- **Newcastle vs Liverpool** — two high-press, front-foot sides → **highest expected goals of GW1** (over 2.5 ~66% implied). This is a HIGH-VARIANCE fixture: good for attacker ceilings on BOTH sides, BAD for clean sheets. Derby-like intensity = widen captaincy uncertainty, do NOT treat as higher-EV.
- **Everton vs Crystal Palace** — two organised low-block-ish defences (Palace especially under Glasner); lowest expected goals cluster (under 2.5 favoured). A CS-lean, low-ceiling attacking fixture — a defence/GK spot, not an attack spot.
- **Nottingham Forest vs Leeds** — Forest slight home favourite; goals lean UNDER. Modest CS spot for Forest; low attacking ceiling.
- **Brentford vs Tottenham** — near coin-flip; Brentford's set-piece threat + Spurs transition = mid goals. No strong CS lean either way.
- **Brighton vs Aston Villa** — two possession/attacking sides, near-even; goals lean slightly over. Attacker ceilings ok on both, weak CS for both.
- **Ipswich vs Sunderland** — two weaker sides, near coin-flip, low ceiling. Nothing to target on attack; marginal CS.
- **Fulham vs Chelsea** — Chelsea slight away favourite; open game (over 2.5 leans ~60%). Chelsea attack the play; weak-to-moderate CS for both.
- **Congestion / travel:** GW1 is post-summer with no midweek European load and follows a summer without a major international tournament final-week — no acute congestion flags. International-break hangover is NOT in play for GW1 (break is later). Rotation risk is the usual opening-weekend "manager still settling XI" uncertainty — gate on team news near deadline.

---

## Sources & method notes

- **De-vig method:** 1X2 stripped **multiplicatively** (fair_p = raw_p / Σraw_p), per the research's guidance for balanced markets. Skewed markets (anytime-scorer, clean-sheet) carry favourite-longshot bias — noted as a skew caveat rather than fully Shin-corrected where only a single book's price was reachable.
- **Closing line as prior:** odds treated as the prior to beat, not echoed. Player-prop (scorer/CS) markets are the softest and most beatable, especially GW1.
- Every number below is cited with source + observation date. Where only aggregator "best odds across books" were reachable (which don't form a clean single-book overround), the de-vig is approximate and flagged.
</content>
</invoke>
