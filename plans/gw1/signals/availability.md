# GW1 2026/27 — Availability & Minutes Signal

**Scout angle:** the #1 GATE — expected minutes, nailedness, injuries, suspensions,
rotation risk, pre-season friendly MINUTES. Method basis:
[predictive-signals.md#minutes--xmins](../../research/team-selection/factors/predictive-signals.md#minutes--xmins),
[data-sources.md#player-availability](../../research/team-selection/sources/data-sources.md#player-availability-the-highest-leverage-deadline-pull),
[importance-ranking.md](../../research/team-selection/importance-ranking.md) (Tier 0 gate).

- **Compiled:** 2026-08-16 (Community Shield day). **GW1 deadline:** Fri 2026-08-21
  17:30 UTC (Arsenal v Coventry, Fri 20:00 BST opener).
- **Live web data is authoritative; local pipeline data (dated 2026-08-02) was NOT used.**
- **Anti-fabrication:** every factual row carries a source URL. Items not confirmable
  against a live 2026-27 source are marked **LOW** and flagged for a deadline re-check.
  Sub-agent ("leaf") claims were independently re-checked against a second live source
  before inclusion; where a leaf was wrong, the correction and reason are noted.
- **Timing rule:** at lock (T-90) *zero* confirmed XIs exist (PL confirms XIs ~75 min
  pre-kickoff). Everything below is *predicted* — treat unresolved rotation as an
  E(min)/variance penalty and re-poll team news T-15→T-5.

---

## 0. Local data is NOT corrupted — the real gap is the projection model

The task brief said local data showing **Coventry / Hull** in the PL is corruption.
**It is not.** Coventry, Hull and Ipswich are genuinely the 2026/27 promoted trio
(Hull won the playoff final); West Ham, Burnley, Wolves went down. Independently
confirmed here and by a peer agent against the live FPL API.
[Wikipedia 2026-27 PL](https://en.wikipedia.org/wiki/2026%E2%80%9327_Premier_League) ·
[PL fixtures](https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-202627-premier-league-season)

So the local **team set and player→team labels are CORRECT** — you can trust local team
assignments (summer movers like Guéhi→City, Senesi/Van Hecke→Spurs are real and reflected).
Do NOT down-weight Coventry/Hull as "phantom" clubs.

**The real local-data gap is the projection model, not the labels** (per the gaffer):
(a) it is ~75% last-season pts/90, so it **misprices summer movers on their OLD club**;
and (b) a **450-minute floor HARD-ZEROES every promoted-side player, new signing, and
injury returnee** — so those assets are *invisible* to the local model. **That blind spot
is exactly this angle's job to cover** — promoted-team and new-signing minutes/nailedness
are handled explicitly in §3 (new signings) and §5 (cheap enablers, incl. promoted-side
defenders), and summarised in the blind-spot box below. Still pull **live prices +
team-news** at the deadline; do not price off the local model for movers/returnees.

> **BLIND-SPOT COVERAGE (assets the local model zeroes):**
> - **Nailed & worth surfacing anyway:** Bruno Guimarães (ARS, new, started Shield) ·
>   Verbruggen (BHA #1) · Van Hecke & Senesi & Robertson (TOT, new backline — proven-PL,
>   likely nailed, but new-unit CS risk) · van Ewijk (COV, promoted RB) · Xhaka (SUN,
>   promoted, DEFCON) · Igor Thiago (BRE) · Semenyo (MCI, mover — started Shield).
> - **Zeroed AND genuinely risky (correct to fade):** Šeško (returnee, may not start) ·
>   Gyökeres (mover, benched in Shield) · Isak (returnee, sharpness) · promoted-side
>   attackers generally · Newcastle's unsettled No.9.

---

## 1. Confirmed 20 PL clubs — 2026/27

Source: [Wikipedia 2026-27 PL](https://en.wikipedia.org/wiki/2026%E2%80%9327_Premier_League),
cross-checked vs [PL official fixtures](https://www.premierleague.com/en/news/4675097/all-380-fixtures-for-202627-premier-league-season).

Arsenal · Aston Villa · Bournemouth · Brentford · Brighton · Chelsea · **Coventry City**
· Crystal Palace · Everton · Fulham · **Hull City** · **Ipswich Town** · Leeds United ·
Liverpool · Man City · Man Utd · Newcastle · Nottingham Forest · Sunderland · Tottenham.

Promoted: Coventry (25-yr absence), Ipswich (1 yr), Hull (9 yr). Relegated: West Ham,
Burnley, Wolves.

### Three structural forces reshaping the minutes picture this year

- **A 2026 FIFA World Cup happened this summer.** WC-deep players returned late/fatigued
  — a real GW1 rotation & injury driver (it is what caused Saliba's back injury, and the
  managed-minutes bench lists in today's Community Shield). Re-check WC finalists' minutes
  at the deadline.
  [Sky – Saliba](https://www.skysports.com/football/news/11670/13566125/william-saliba-injury-arsenal-confirm-france-international-will-miss-extended-period-after-returning-from-world-cup-with-back-problem)
- **Record NINE new permanent managers** for 2026/27 — the most ever on an opening
  weekend. New systems = elevated rotation uncertainty, especially for non-nailed/cheap
  assets. **Confirmed (official):** Man City → **Enzo Maresca** (Guardiola resigned),
  Liverpool → **Andoni Iraola** (Slot sacked), Chelsea → **Xabi Alonso**, Man Utd →
  **Michael Carrick** (permanent).
  [PL – manager line-up complete](https://www.premierleague.com/en/news/4679012/manager-line-up-complete-for-202627-season) ·
  [Liverpool FC official – Iraola](https://www.liverpoolfc.com/news/liverpool-fc-appoint-andoni-iraola-new-head-coach)
  · *(Note: two leaf agents wrongly dismissed these as "garbled" against stale priors; I
  verified them against official club/PL sources — they are correct. The manager carousel
  is just unusually large this year.)*
- **Heavy top-club roster churn** — several assets are at NEW clubs vs any stale dataset:
  **Salah left the PL** (Liverpool → Trabzonspor, free); **Semenyo** Bournemouth → **Man
  City** (£64m, Jan 2026); **Bruno Guimarães** Newcastle → **Arsenal** (£75m, 8 Aug 2026);
  **Morgan Rogers** Aston Villa → **Chelsea** (LOW-MED, see §3). Verify every player's
  club against live data.

---

## 2. The minutes GATE — premium / popular assets

Tiers: **HIGH** = nailed starter, no flag · **MED** = likely starts but
rotation/fitness/role doubt (apply variance penalty, monitor) · **LOW/OUT** =
doubtful/injured/suspended/contested role (gate out or bench-only).

| Player | Team | Pos | Tier | Note | Source |
|---|---|---|---|---|---|
| Erling Haaland | Man City | FWD | **HIGH** | Template captain £15.5m, ~75% owned; **started** Community Shield; penalty taker. The one non-negotiable. | [PL The Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl) · [Shield XI (Sky)](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Bruno Fernandes | Man Utd | MID | **HIGH** | £12.0m, most-owned mid (~49%); nailed under Carrick; penalty taker. | [PL The Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl) |
| João Pedro | Chelsea | FWD | **HIGH** | £7.5m, ~50% owned; strong pre-season under Alonso; template forward. (Est. since 2025 — not new.) | [PL The Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl) |
| Gabriel Magalhães | Arsenal | DEF | **HIGH** | £8.0m nailed CB, set-piece goal threat; **started** Shield; MORE important with Saliba/Timber out. | [PL The Scout](https://www.premierleague.com/en/news/4681709/the-scouts-must-haves-for-start-of-202627-fpl) · [Shield XI](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Igor Thiago | Brentford | FWD | **HIGH** | Undisputed starter, primary pen taker; £8.0m (up £2m); 22 goals 2025-26. | [Brentford FC](https://www.brentfordfc.com/en/news/article/fpl-scout-2026-27-season-preview-fantasy-premier-league-hints-tips-advice) · [AllAboutFPL pens](https://allaboutfpl.com/2026/08/premier-league-penalty-set-piece-takers-2026-27-pl-season/) |
| Bruno Guimarães | Arsenal | MID | **HIGH** | New (£75m from Newcastle, 8 Aug); proven-immediate — **started** Shield CM. Nailed but crowds an already deep Arsenal midfield (Rice/Zubimendi benched). | [Sky](https://www.skysports.com/football/news/11095/13570096/bruno-guimaraes-arsenal-sign-midfielder-in-lb75m-transfer-as-newcastle-surpass-lb240m-in-player-sales-this-summer) · [Shield XI](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Cole Palmer | Chelsea | MID | **MED-HIGH** | Chelsea creative hub + pen taker. Minor precautionary knock in pre-season ("not serious"). **Monitor.** | [FFS](https://www.fantasyfootballscout.co.uk/2026/08/06/fpl-pre-season-palmer-colwill-injury-latest-pedro-in-the-10) |
| Bukayo Saka | Arsenal | MID | **MED-HIGH** | Managing an Achilles issue; **benched** in Shield as load-management, not a role loss; Arteta expects him for GW1. Pen taker. **Monitor.** | [Arsenal.com](https://www.arsenal.com/news/artetas-update-on-rice-saka-saliba-and-timber-apAqr8i40BvM) |
| Florian Wirtz | Liverpool | MID | **HIGH** | Back in full training post-WC; expected No.10 under Iraola. | [liverpool.com](https://www.liverpool.com/liverpool-fc-news/features/iraola-preseason-isak-wirtz-gravenberch-34318805) |
| Bryan Mbeumo | Man Utd | FWD/MID | **HIGH** | Established starter (2025 from Brentford); backup pen/set-pieces behind Bruno. | [manutd.com](https://www.manutd.com/en/teams/mens-team/bryan-mbeumo) |
| Alexander Isak | Liverpool | FWD | **MED-HIGH** | Liverpool's lead striker (Ekitiké out), named pen taker; reports he's fit, but off a long 2025-26 layoff + thin pre-season + new system → 90-min sharpness a doubt. **Monitor.** | [thisisanfield](https://www.thisisanfield.com/2026/08/alexander-isak-fitness-update-liverpool-pre-season/) |
| Antoine Semenyo | **Man City** | FWD/MID | **MED** | **NOT Bournemouth** — moved to City (£64m, Jan 2026). **Started** Shield RW (integrated), but a deep City attack under Maresca = rotation risk over a season. | [Sky – Semenyo to City](https://www.skysports.com/football/news/11095/13491956/antoine-semenyo-joins-man-city-bournemouth-forward-signs-in-lb64m-transfer-to-take-city-spending-over-lb425m-in-12-months) · [Shield XI](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Viktor Gyökeres | Arsenal | FWD | **MED — ROLE TRAP** | **Benched in today's Community Shield; Havertz started CF.** Quality is not in doubt, but his GW1 nailedness IS. Do NOT captain/assume-start on faith. **Defer to team news.** | [Shield XI + bench (Sky)](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) · [Yahoo](https://sports.yahoo.com/articles/arsenal-team-face-man-city-135500728.html) |
| Kai Havertz | Arsenal | FWD/MID | **MED** | **Started CF ahead of Gyökeres** in the Shield — the live signal for Arsenal's GW1 No.9. Cheaper route to the Arsenal attack IF it holds. Confirm at deadline. | [Shield XI](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Ollie Watkins | Aston Villa | FWD | **MED** | No pre-season minutes (WC); may still start opener at Brighton due to other Villa FWD injuries. **NOT** the pen taker (Buendía is). **Monitor.** | [FFS 16 Aug](https://www.fantasyfootballscout.co.uk/2026/08/16/fpl-pre-season-villa-injuries-another-ndiaye-pen-no-norgaard) |
| Benjamin Šeško | Man Utd | FWD | **LOW-MED** | Shin injury; "confident fit for squad" but **"unlikely to start vs Hull"** (MEN). Bench/doubt. | [Goal](https://www.goal.com/en/lists/benjamin-sesko-shin-injury-recovery-man-utd-pre-season/blt677d35b5df9283c0) · [United in Focus](https://www.unitedinfocus.com/news/benjamin-sesko-shin-injury-update-when-the-man-united-striker-will-return-in-pre-season/) |
| William Saliba | Arsenal | DEF | **OUT** | Back (2026 WC); "extended/long-term", misses PL start; Mosquera started Shield in his place. **AVOID.** | [Sky](https://www.skysports.com/football/news/11670/13566125/william-saliba-injury-arsenal-confirm-france-international-will-miss-extended-period-after-returning-from-world-cup-with-back-problem) |
| Jurriën Timber | Arsenal | DEF | **OUT** | Groin; out for the start. **AVOID.** | [FFS](https://www.fantasyfootballscout.co.uk/2026/08/14/saliba-timber-injury-latest-arteta-on-saka-rice) |
| Hugo Ekitiké | Liverpool | FWD | **OUT** | Ruptured Achilles (Apr 2026); not back until ~Dec 2026/Jan 2027. In squad to rehab only. **AVOID.** | [ESPN](https://www.espn.com/soccer/story/_/id/48510496/liverpool-hugo-ekitike-come-back-stronger-devastating-injury-arne-slot) |
| Mohamed Salah | — | — | **GONE — not in PL** | Left Liverpool end 2025-26 (free) → **Trabzonspor**. Not selectable. Any local data listing him is stale. | [Sky – Salah to Trabzonspor](https://www.skysports.com/football/news/11095/13570282/mohamed-salah-former-liverpool-forward-joins-turkish-club-trabzonspor-on-free-transfer-after-leaving-anfield) |

### Confirmed first-choice penalty takers (2026/27)
Arsenal – **Saka**; Man City – **Haaland**; Chelsea – **Palmer**; Man Utd – **Bruno
Fernandes**; Liverpool – **Isak**; Brentford – **Igor Thiago**; Aston Villa – **Buendía**
(NOT Watkins). Source: [AllAboutFPL](https://allaboutfpl.com/2026/08/premier-league-penalty-set-piece-takers-2026-27-pl-season/),
[RotoWire set-pieces](https://www.rotowire.com/soccer/article/premier-league-set-piece-takers-2026-27-penalties-corners-free-kicks-for-every-team-126070).

---

## 3. New-signing minutes/role risk

Adaptation lag is a distribution shift, not a blanket fade — proven-league/nailed-role
signings can hit immediately; flag only genuine bedding-in.

| Player | New club | From | GW1 tier | Read | Source |
|---|---|---|---|---|---|
| Bruno Guimarães | Arsenal | Newcastle £75m | **HIGH** | Proven-immediate; started Shield CM | [Sky](https://www.skysports.com/football/news/11095/13570096/bruno-guimaraes-arsenal-sign-midfielder-in-lb75m-transfer-as-newcastle-surpass-lb240m-in-player-sales-this-summer) |
| Christos Tzolis | Arsenal | Club Brugge £34m | **MED** | New to PL (bedding-in) but started Shield LW — encouraging | [Yahoo](https://sports.yahoo.com/articles/arsenal-team-face-man-city-135500728.html) |
| Morgan Rogers | Chelsea | Aston Villa | **MED (club LOW-MED)** | Proven PL but role TBD under Alonso (CAM vs wing, Palmer overlap). Verify club at deadline — two leaves disagreed. | [beIN](https://www.beinsports.com/en-us/soccer/premier-league/articles/chelsea-unveil-blockbuster-signing-morgan-rogers-joins-the-club-2026-07-21) |
| Youri Tielemans | Man Utd | Aston Villa £35m | **MED** | Proven PL, midfield role uncertain | [ESPN transfers](https://www.espn.co.uk/football/story/_/id/48955344/premier-league-2026-summer-transfers-all-confirmed-ins-outs-every-club) |
| Jan Paul van Hecke | Tottenham | Brighton £52m | **MED-HIGH** | Proven-PL CB, likely nailed; but a rebuilt Spurs backline = early-cohesion CS risk | [Sky](https://www.skysports.com/football/news/11675/13555493/jan-paul-van-hecke-tottenham-sign-brighton-defender-for-lb52m) |
| Marcos Senesi | Tottenham | Bournemouth (free) | **MED-HIGH** | Proven-PL CB, likely nailed; same new-backline CS caveat | [TeamTalk](https://www.teamtalk.com/tottenham-hotspur/every-completed-tottenham-transfer-summer-2026-signings-sales-loans) |
| Andy Robertson | Tottenham | Liverpool (free) | **MED** | Proven-PL LB; age/rotation + new unit — confirm nailedness at deadline | [Planet Football](https://www.planetfootball.com/tottenham-hotspur/tottenham-dream-defence-2026-27-van-hecke-robertson) |
| Marc Guéhi | Man City | Crystal Palace (Jan 2026) | **MED — rotation** | Real mover; a City sub in the Shield (Dias/Gvardiol started) — not nailed | [Goal](https://www.goal.com/en/lists/man-city-completing-65m-antoine-semenyo-transfer-bournemouth/blt92051843e2785cb4) |

**Do NOT mis-flag as "new":** Gyökeres (Arsenal, 2025), Isak (Liverpool, 2025), João
Pedro (Chelsea, 2025), Mbeumo (Man Utd, 2025), Semenyo (City, Jan 2026) are all
established — their flags are *role/fitness*, not adaptation.

---

## 4. Pre-season friendly MINUTES (signal = minutes/role only; goals ignored)

Per method, minutes in the *final* warm-ups predict GW1 XIs; friendly goal tallies are
noise and never downgrade a proven player.

**Primary signal — 2026 FA Community Shield, Arsenal v Man City, Sun 16 Aug (5 days
pre-GW1).** Starting XI ≈ strong GW1-lineup predictor; the bench = who's being managed.
Lineups confirmed across [Sky](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659),
[Yahoo](https://sports.yahoo.com/articles/arsenal-team-face-man-city-135500728.html),
[World Soccer Talk](https://worldsoccertalk.com/news/arsenal-vs-manchester-city-probable-lineups-for-2026-fa-community-shield-final/).

- **Arsenal XI:** Raya; White, Mosquera, Gabriel, Calafiori; Ødegaard(c), **Bruno
  Guimarães**, Lewis-Skelly; Madueke, **Havertz**, **Tzolis**.
  - Signals: **Havertz preferred to Gyökeres at CF** (role trap, above). **Saka, Rice,
    Eze, Zubimendi, Merino, Gyökeres all benched** — with a deep 2026 WC run behind
    several, this reads as managed-minutes/rotation depth (Saka = load management, likely
    starts GW1). Ben White started RB (fit). Mosquera deputising for Saliba.
- **Man City XI:** Donnarumma; Khusanov, Dias, Gvardiol, O'Reilly; Kovačić, E. Anderson;
  **Semenyo**, Foden, Doku; **Haaland**.
  - Signals: **Haaland nailed**; **Semenyo started RW** (integrated). Grealish, Marmoush,
    Cherki, Rico Lewis, Guéhi benched (depth/managed minutes).
- Per-player friendly-minute detail beyond the Shield: primary source is the
  [FFS pre-season minutes tracker](https://www.fantasyfootballscout.co.uk/fpl-2026-27-pre-season-minutes-goals-assists-tracker)
  (partly paywalled). Where thin, rows are marked MED/LOW and deferred to the T-15 poll.

---

## 5. Cheap NAILED enabler shortlist (fund the premiums)

The highest-leverage GW1 edge is a cheap nailed starter. Prices are as stated by sources
(indicative — reconfirm on the FPL API). Leaf-sourced rows re-checked where load-bearing.

### DEF — established mid-table sides (lower clean-sheet risk) — preferred
| Player | Club | Price | Tier | Note | Source |
|---|---|---|---|---|---|
| **Tyrick Mitchell** | Crystal Palace | £4.5m | **HIGH** | 36 starts last season; cheapest secure route into Palace defence | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) |
| **Matty Cash** | Aston Villa | £4.5m | **HIGH** | 35 apps, attacking-FB ceiling | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) |
| **Michael Kayode** | Brentford | £4.5m | **HIGH** | 37 starts, primary fullback | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) |
| Luke Shaw | Man Utd | £4.5m | **MED-HIGH** | Started all 38 last season, easy openers vs Hull/Ipswich — but United "concerned over his fitness"; injury-prone. **Monitor.** | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) · [StrettyNews](https://strettynews.com/2026/04/11/manchester-united-doubts-luke-shaw-ability-fitness/) |
| Joe Rodon | Leeds | £4.5m | **MED-HIGH** | 33 starts; promoted side (CS risk) but nailed | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) |
| Lewis Dunk | Brighton | £4.5m | **MED** | Brighton revamped defence — rotation possible | [FFS £4.5m def](https://www.fantasyfootballscout.co.uk/2026/07/29/best-4-5m-defenders-for-fpl-2026-27) |

### DEF — £4.0m pool (mostly promoted; CS risk, DEFCON upside)
| Player | Club | Price | Tier | Note | Source |
|---|---|---|---|---|---|
| Milan van Ewijk | Coventry (promoted) | £4.0m | **MED-HIGH** | First-choice RB | [FFS £4.0m def](https://www.fantasyfootballscout.co.uk/2026/07/24/best-4-0m-defenders-for-fpl-2026-27-all-46-assessed) |
| Bobby Thomas | Coventry (promoted) | £4.0m | **MED** | Nailed CB but rotated mid-season last year | [FFS £4.0m def](https://www.fantasyfootballscout.co.uk/2026/07/24/best-4-0m-defenders-for-fpl-2026-27-all-46-assessed) |

**£4.0m gap:** 26 of 46 £4.0m defenders are Coventry/Hull/Ipswich; specific nailed Hull &
Ipswich names sit behind the FFS paywall — **unresolved, verify at deadline.**

### GK
| Player | Club | Price | Tier | Note | Source |
|---|---|---|---|---|---|
| **Bart Verbruggen** | Brighton | £4.5m | **HIGH** | Undisputed #1 under Hürzeler; 130 pts last season, high save %, soft openers. Best cheap-GK value. | [FFS GK](https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27) · [RotoWire profile](https://www.rotowire.com/soccer/player/bart-verbruggen-39728) |
| Djordje Petrović | Bournemouth | £4.5m | **HIGH** | Established #1 (Euro-congestion caveat) | [FFS GK](https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27) |
| Bernd Leno | Fulham | £4.5m | **MED-HIGH** | Primary #1 | [FFS GK](https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27) |

**£4.0m GK — no verified nailed starter for 2026/27.** The commonly-cited "Dúbravka
£4.0m" is at **relegated Burnley** (invalid); a Tottenham claim was garbled. Take the
£4.5m Verbruggen route instead. [FFS GK](https://www.fantasyfootballscout.co.uk/2026/07/28/best-4-0m-4-5m-goalkeepers-for-fpl-2026-27)

### MID (cheap enabler with minutes/DEFCON)
| Player | Club | Price | Tier | Note | Source |
|---|---|---|---|---|---|
| Granit Xhaka | Sunderland | £5.5m | **MED-HIGH** | "Safest starter", ~11 DEFCON/90 floor; promoted side (CS risk) | [FFS £5.5m mid](https://www.fantasyfootballscout.co.uk/2026/08/09/best-5-5m-midfielders-for-fpl-2026-27) |
| Diego Gómez | Brighton | £5.0m | **MED** | Started 22 of 24 late last season; attacking upside — leaf HIGH but I could not strongly re-confirm nailedness (Brighton midfield rotates). | [FFS £5.0m mid](https://www.fantasyfootballscout.co.uk/2026/08/05/best-5-0m-midfielders-for-fpl-2026-27-all-89-assessed) |

**Dropped on verification:** *Pascal Groß (£5.5m)* — the enabler leaf called him nailed
first-choice; my check shows he **returned to Brighton (Jan 2026) as a rotation option**,
not a lock. Do not treat as an enabler. [Brighton FC](https://www.brightonandhovealbion.com/media-article/mft-transfer-news-pascal-gross-borussia-dortmund-january-2026)
*Christian Nørgaard → Everton* remains **UNCONFIRMED (LOW)** — do not rely.

---

## 6. GW1 availability LANDMINES (defer / re-check before deadline)

| Item | Team | Risk | Flag | Source |
|---|---|---|---|---|
| Gyökeres benched in Shield; Havertz started CF | Arsenal | premium FWD may not be nailed GW1 | **Defer — team news** | [Shield XI](https://www.skysports.com/football/arsenal-vs-manchester-city/teams/556659) |
| Fofana SUSPENDED (ban to 6 Sep) | Chelsea | multi-GW ban | Avoid thru GW1+ | [OneFPL GW1 bans](https://onefpl.com/blog/who-will-miss-fpl-gameweek-1-2026-27) |
| Christie SUSPENDED (to 29 Aug) | Bournemouth | GW1 ban | Avoid | [OneFPL](https://onefpl.com/blog/who-will-miss-fpl-gameweek-1-2026-27) |
| Andersen SUSPENDED (to 29 Aug) | Fulham | GW1 ban | Avoid | [OneFPL](https://onefpl.com/blog/who-will-miss-fpl-gameweek-1-2026-27) |
| Saliba OUT (back) · Timber OUT (groin) | Arsenal | 2 premium DEF gone | Avoid | [Sky](https://www.skysports.com/football/news/11670/13566125/william-saliba-injury-arsenal-confirm-france-international-will-miss-extended-period-after-returning-from-world-cup-with-back-problem) |
| Ekitiké OUT (Achilles) · Gomez OUT · Bradley OUT | Liverpool | attack/def depth | Avoid | [OneFPL](https://onefpl.com/blog/who-will-miss-fpl-gameweek-1-2026-27) |
| de Ligt OUT (back) · Ugarte OUT (knee) | Man Utd | DEF/MID depth | Avoid | [OneFPL](https://onefpl.com/blog/who-will-miss-fpl-gameweek-1-2026-27) |
| Šeško shin — "unlikely to start" vs Hull | Man Utd | FWD not nailed | Defer; bench-only | [United in Focus](https://www.unitedinfocus.com/news/benjamin-sesko-shin-injury-update-when-the-man-united-striker-will-return-in-pre-season/) |
| Isak fitness/sharpness (new system) | Liverpool | 90-min doubt | MED — re-check T-15 | [thisisanfield](https://www.thisisanfield.com/2026/08/alexander-isak-fitness-update-liverpool-pre-season/) |
| Newcastle No.9 unsettled (Osula/Woltemade/Wissa) + Bruno G sold | Newcastle | no nailed FWD; midfield gutted | Avoid new Newcastle attackers on minutes | [Yahoo/Athletic](https://sports.yahoo.com/articles/newcastle-plans-2026-27-striker-160000277.html) |
| Injury DOUBTS 75%: Mount (MUN), Livramento (NEW), da Cunha (AVL) | various | start uncertain | Re-check T-15 | [FFS team-news](https://www.fantasyfootballscout.co.uk/team-news) |
| Injury DOUBTS 25% (likely miss): Rodri (MCI), Mitoma/Baleba/Ferguson (BHA), Kulusevski (TOT) | various | likely out/bench | Avoid | [FFS team-news](https://www.fantasyfootballscout.co.uk/team-news) |
| 9 new managers + 2026 WC hangover | league-wide | system change + fatigue = rotation noise | Fade non-nailed cheap picks; re-check | [PL](https://www.premierleague.com/en/news/4679012/manager-line-up-complete-for-202627-season) |

*Note: OneFPL/FFS suspension and doubt tiers above were reported by a leaf agent from
FFS/OneFPL; the three suspensions and the Mount/Livramento 75% tiers were the parent's
pre-flagged items and were confirmed. The 25%-tier doubts (Rodri etc.) are single-source
(FFS) — treat as MED confidence and re-check at the deadline.*

---

## Confidence summary

- **HIGH / verified (multi-source):** the 20-team set incl. Coventry/Hull; the 4 named
  manager changes; Community Shield XIs incl. Gyökeres benched / Havertz & Semenyo
  started; Saliba/Timber/Ekitiké out; Salah left PL; Semenyo & Bruno Guimarães club
  moves; Haaland/Bruno F/João Pedro/Gabriel/Igor Thiago nailed; Verbruggen #1.
- **MED / single-source or time-sensitive — re-check at deadline:** Isak sharpness;
  Palmer/Saka/Watkins/Šeško fitness; the 25%-tier doubts; Diego Gómez nailedness;
  £4.0m Hull/Ipswich defenders; Morgan Rogers' Chelsea role.
- **LOW / unconfirmed:** Nørgaard→Everton; any £4.0m nailed GK; friendly-minute detail
  beyond the Shield.

Live-data reachability was **good** — the corrupt-local-data problem was fully bypassed.
