# GW1 2026/27 — Value, Price & Ownership signal

**Analyst:** Value, Price & Ownership Trader · **For:** #25 GW1 one-shot squad
**Observation date:** 2026-08-16 · **GW1 deadline:** Fri 2026-08-21 17:30 UTC

## Sourcing & confidence

- **Primary source (authoritative):** the **official live FPL API** —
  `https://fantasy.premierleague.com/api/bootstrap-static/`, fetched **2026-08-16**.
  Every price, team and ownership % below is pulled directly from it (via `jq`), so
  names/teams/prices are the game's own record, not a summariser's paraphrase.
- **Cross-checks:** surprising team moves were verified against reputable news (e.g.
  Semenyo→Man City confirmed by [Sky Sports](https://www.skysports.com/football/news/11095/13491956/antoine-semenyo-joins-man-city-bournemouth-forward-signs-in-lb64m-transfer-to-take-city-spending-over-lb425m-in-12-months),
  [ESPN](https://www.espn.com/soccer/story/_/id/47537480/man-city-transfer-antoine-semenyo-bournemouth-64-million-premier-league);
  Isak→Liverpool by [Liverpool FC](https://www.liverpoolfc.com/news/liverpool-complete-signing-alexander-isak)).
- **Confidence: HIGH** on prices / ownership / team assignments (live official API,
  reachable). **MEDIUM** on differential "underlying stats" — it is **pre-season, so no
  2026/27 xG/points exist yet**; the API's `total_points`/`minutes` are **last-season
  carryover** (Haaland 239, Bruno 235, `form=0`, `ep_next` a flat 4.0 placeholder).
- **PPM caveat (anti-fabrication):** a 2026/27 points-per-million cannot be computed —
  current-season points are 0. I do **not** invent one. "Value" below is *structural*
  (price-point × nailed role × ownership proxy), with last-season totals used only as
  pedigree, discounted for finishing luck per the wiki.

⚠️ Note vs local repo data: the stale local set (Coventry/Hull "corruption" flag) is
partly a red herring — Coventry & Hull **are** genuinely in the 2026/27 PL. The real
problem was stale prices/labels. Live API resolves it.

---

## 1. The 20 Premier League teams — 2026/27 (confirmed, official API)

Arsenal · Aston Villa · Bournemouth · Brentford · Brighton · Chelsea · **Coventry City** ·
Crystal Palace · Everton · Fulham · **Hull City** · **Ipswich Town** · Leeds · Liverpool ·
Man City · Man Utd · Newcastle · Nott'm Forest · Spurs · Sunderland.

Promoted: **Coventry, Ipswich, Hull**. Relegated out: Wolves, Burnley, West Ham
([PL AGM confirmation](https://www.premierleague.com/en/news/4673099/the-202627-premier-league-season-officially-starts/)).
Notable window moves already reflected in FPL team assignments: Isak→LIV, Semenyo→**MCI**,
Guéhi→**MCI**, João Pedro→**CHE**, Rogers→**CHE**, Gyökeres→ARS, Calvert-Lewin→LEE,
Donnarumma→MCI, Senesi→TOT.

---

## 2. Live price & ownership table — key assets

All figures: official FPL API, 2026-08-16. `status`: a=available, d=doubtful, i=injured.
Source for the whole table: `fantasy.premierleague.com/api/bootstrap-static/` (obs 2026-08-16).

### Forwards
| Player | Team | Price | Own% | status |
|---|---|---|---|---|
| Haaland | MCI | £15.5 | 72.5 | a |
| Isak | LIV | £9.0 | 14.5 | a |
| Watkins | AVL | £8.0 | 12.5 | a |
| Thiago | BRE | £8.0 | 16.8 | a |
| Gyökeres | ARS | £7.5 | 12.1 | a |
| João Pedro | CHE | £7.5 | 57.9 | a |
| Mateta | CRY | £6.5 | 6.3 | a |
| Calvert-Lewin | LEE | £6.0 | 25.9 | a |
| Ekitiké | LIV | £7.5 | 0.2 | **i** |

### Midfielders
| Player | Team | Price | Own% | status |
|---|---|---|---|---|
| B.Fernandes | MUN | £12.0 | 48.1 | a |
| Saka | ARS | £9.5 | 10.3 | a |
| Palmer | CHE | £9.5 | 10.8 | a |
| Semenyo | MCI | £8.5 | 27.6 | a |
| Mbeumo | MUN | £8.0 | 28.4 | a |
| Cunha | MUN | £8.0 | 11.7 | a |
| Gibbs-White | NFO | £8.0 | 11.7 | a |
| Rice | ARS | £7.5 | 20.9 | a |
| Rogers | CHE | £7.5 | 26.7 | a |
| Wirtz | LIV | £7.5 | 15.0 | a |
| Szoboszlai | LIV | £7.0 | 41.6 | a |

### Defenders
| Player | Team | Price | Own% | status |
|---|---|---|---|---|
| Gabriel | ARS | £8.0 | 27.8 | a |
| Virgil | LIV | £6.5 | 17.3 | a |
| O'Reilly | MCI | £6.5 | 21.9 | a |
| Guéhi | MCI | £6.0 | 21.6 | a |
| Senesi | TOT | £6.0 | 9.9 | a |
| Tarkowski | EVE | £6.0 | 9.6 | a |
| Calafiori | ARS | £5.5 | 21.3 | a |
| Pedro Porro | TOT | £5.5 | 23.2 | a |
| Gvardiol | MCI | £5.5 | 13.2 | a |
| Shaw | MUN | £4.5 | 23.5 | a |

### Goalkeepers
| Player | Team | Price | Own% | status |
|---|---|---|---|---|
| Raya | ARS | £6.0 | 32.3 | a |
| Pickford | EVE | £5.5 | 8.7 | a |
| Donnarumma | MCI | £5.5 | 10.7 | a |
| A.Becker | LIV | £5.5 | 3.9 | a |
| Kinsky | TOT | £4.5 | 19.8 | a |
| Verbruggen | BHA | £4.5 | 18.5 | a |
| Dubravka | TOT | £4.0 | 22.2 | a |
| Palmer (GK) | IPS | £4.0 | 5.5 | a |

⚠️ **Spurs GK is a trap:** the API lists **both** Kinsky (£4.5, 19.8%) and Dubravka
(£4.0, 22.2%) at Spurs with high ownership — the field is split on who starts. Do **not**
buy a Spurs keeper until team news confirms GK1. Prefer a settled starter (Pickford £5.5)
or a settled cheap enabler.

---

## 3. £100.0m budget-allocation plan

Wiki shape (top-50 *effective/XI* budget): **MID ~41% · FWD ~30% · DEF ~23% · GK ~6%**,
premiums concentrated in **midfield**. Translated to a concrete 15-man money split:

| Pos | Effective (XI) target | 15-man £ spend | Structure |
|---|---|---|---|
| GKP | ~6% (~£5.5–6.0 starter) | **£9.0–10.0** (pair) | 1 nailed starter £5.5–6.0 + £4.0 backup |
| DEF | ~23% (~£20–23) | **£24–27** | ≤1 premium (Gabriel £8.0) or spread; 3 mid starters £5.5–4.5 + 2×£4.0 bench |
| MID | ~41% (~£38–41) | **£36–41** | 1 premium (Bruno £12) + 2 mid-prems £7.5–8.5 + cheap enablers |
| FWD | ~30% (~£28–30) | **£28–30** | Haaland £15.5 + 1×£7.5 + 1×£6.0 |

**How many premiums fit:** exactly **TWO** genuine £12m+ premiums — **Haaland £15.5 +
Bruno £12.0 = £27.5m** — leaves £72.5m for 13 players (avg £5.58). A *third* "premium"
slot is realistically a **£8.0–9.5 mid** (Semenyo / Mbeumo / Saka / Palmer), not another
£12m asset. Three true £12m+ premiums does **not** leave a functional spine. The winning
shape is **2 premiums + a band of £7.5–8.5 attacking mids + cheap enablers**, exactly the
"premiums in midfield, balanced spine" wiki prescription.

**Representative template-leaning 15** (fits £100.0m, ~£0.5 bank, max-3 respected — an
illustration of feasibility, not the final ILP output):

- **GK:** Pickford 5.5 · *Palmer(IPS) 4.0*
- **DEF:** Gabriel 8.0, Porro 5.5, Shaw 4.5 · *Diop(IPS) 4.0, van Ewijk(COV) 4.0*
- **MID:** B.Fernandes 12.0, Semenyo 8.5, Mbeumo 8.0, Hughes(CRY) 4.5 · *Yates(NFO) 4.5*
- **FWD:** Haaland 15.5, João Pedro 7.5, Calvert-Lewin 6.0

Max-3 tension is **Man City** (Haaland + Semenyo already = 2 → only ONE more City asset
available; cannot pair O'Reilly *and* Guéhi). MUN caps at 3 (Bruno+Mbeumo+Shaw).
Keep ~£0.5m bank and ≥1 FT into GW2 per the GW1 construction note.

---

## 4. Template vs differential (EO = start% + captain%)

### Must-own template core (NOT owning = rank risk)
| Player | Team | Price | Own% | Why it's rank-protection |
|---|---|---|---|---|
| **Haaland** | MCI | £15.5 | **72.5** | Near-universal + captain magnet → effective ownership well past 100%. The one true must-own. |
| **João Pedro** | CHE | £7.5 | **57.9** | Dominant budget-forward template; unlocks the Haaland build. |
| **B.Fernandes** | MUN | £12.0 | **48.1** | Premium-mid template, penalties, nailed. |
| **Szoboszlai** | LIV | £7.0 | **41.6** | Surprise heavy template — a cheap-mid EO you can't ignore. |
| **Raya** | ARS | £6.0 | **32.3** | The GK the field owns. |
| **Gabriel** | ARS | £8.0 | **27.8** | The one DEF the field converges on. |

Secondary template (25–29%, "own or have a reason not to"): **Mbeumo** £8.0 (28.4),
**Semenyo** £8.5 (27.6), **Rogers** £7.5 (26.7), **Calvert-Lewin** £6.0 (25.9),
**Shaw** £4.5 (23.5), **Porro** £5.5 (23.2), **O'Reilly** £6.5 (21.9), **Guéhi** £6.0 (21.6).

### Differentials with real pedigree (earned, not random)
Low EO **only** pays with genuine underlying quality — these have it (pedigree-based,
pending 2026/27 confirmation):
- **Cole Palmer** — CHE, £9.5, **10.8%**. Elite multi-season xGI + penalties; low-owned
  purely on price/team doubts. The premium-mid differential vs Bruno.
- **Saka** — ARS, £9.5, **10.3%**. Nailed, set-pieces/pens, wing-heavy usage share;
  a captain-ceiling differential the field is currently underweight.
- **Isak** — LIV, £9.0, **14.5%**. New Liverpool #9 (Ekitiké injured → minutes clear);
  striker differential with title-team volume. Bedding-in risk = the reason for low EO.
- *Bench upside:* **Wirtz** £7.5 (15.0), **Gibbs-White** £8.0 (11.7) — creative, low-owned.

Avoid *unearned* differentials (low-owned with no underlying case) — that's just variance.

---

## 5. Captaincy — EO asymmetry (GW1)

- **PROTECT (default): Captain Haaland.** At 72.5% ownership and the obvious armband, his
  **captaincy pushes his effective ownership far beyond 100%** — if he hauls and you
  didn't captain (or didn't own) him, that's a large rank *loss*. GW1 is a low-information
  regime → the wiki rule is explicit: **captain the field's premium, don't differential
  the armband.** This is the recommended GW1 call.
- **DIFFERENTIAL-to-climb (only if chasing): Bruno Fernandes (c).** The main lower-EO
  premium armband (nailed, penalties). Captaining Bruno *instead of* Haaland is the
  rank-*gain* play, but it only pays if Bruno out-hauls Haaland — pure downside vs the
  template in a one-shot GW1. Deeper punts (João Pedro, Semenyo) are not advised for GW1.
- **Recommendation:** (C) **Haaland**, (VC) **Bruno Fernandes** (nailed premium fallback).
  Save differential armbands for post-data GWs when EV gaps are observable.
- ⚠️ Fixture caveat: this is EO framing, not fixture-adjusted. Confirm GW1
  opponents/home-away before locking the armband (out of this signal's scope).

---

## 6. Best value per position (structural — nailed-minutes screen)

No 2026/27 PPM exists (pre-season). Ranked on **price-point efficiency × nailed role ×
ownership-as-nailedness-proxy**. All prices/own% = official API, 2026-08-16.

- **GKP:** *Value starter* **Pickford £5.5** (EVE, nailed, save-volume + set-pieces) or
  **Raya £6.0** (template, CS ceiling). *Cheap enabler* — needs team-news; **Verbruggen
  £4.5** (BHA, settled) over the split Spurs pair.
- **DEF:** *Enablers* **Shaw £4.5** (MUN, 23.5% — nailed United full-back, the standout
  £4.5 enabler), **Diop £4.0** (IPS, 18.3%), **van Ewijk £4.0** (COV, 15.1%). *Mid value:*
  **Calafiori £5.5** (ARS, 21.3%), **O'Reilly £6.5** / **Guéhi £6.0** (City, DEFCON + CS).
- **MID:** *Value engine* **Szoboszlai £7.0** (LIV, 41.6% template) and **Mbeumo £8.0**
  (MUN, 28.4%). *Cheap enablers* **Hughes £4.5** (CRY, 11.1%), **Yates £4.5** (NFO, 6.6%),
  **Xhaka £5.5** (SUN). *Differential value:* **Palmer £9.5**.
- **FWD:** *Best budget value* **Calvert-Lewin £6.0** (LEE, 25.9% — the cheap-striker
  template) and **João Pedro £7.5** (CHE, 57.9%). No reliable sub-£5.0 nailed starting
  forward exists — **enable through DEF/MID**, run a £6.0 3rd striker, don't chase £4.5
  forward fodder (Kusi-Asare £4.5 FUL is a punt, not a starter).

### Cheap enablers that unlock a premium-heavy XI (the key GW1 skill)
| Slot | Pick | Team | Price | Own% | Note |
|---|---|---|---|---|---|
| DEF | **Shaw** | MUN | £4.5 | 23.5 | Best £4.5 — nailed full-back, real points |
| DEF | Diop | IPS | £4.0 | 18.3 | £4.0 floor, playing |
| DEF | van Ewijk | COV | £4.0 | 15.1 | £4.0 floor, playing |
| MID | Hughes | CRY | £4.5 | 11.1 | Cheapest playing mid tier |
| MID | Yates | NFO | £4.5 | 6.6 | £4.5 mid, minutes |
| GK | Palmer | IPS | £4.0 | 5.5 | £4.0 backup GK |

Pick "round" price points (£4.0 / £4.5 / £8.0) so any single-move pivot stays open across
GW1–5 (price-point flexibility per the construction note).

### ⚠️ Promoted-side & new-signing enablers the local model HIDES
The local Aug-2 model hard-zeroes promoted-club players and fresh signings (no history →
no xPts), so they are invisible to the optimiser unless surfaced manually. These are
**real, cheap, likely-nailed GW1 starters** (live API, 2026-08-16) and are exactly where
the £4.0 enabler value lives:

| Player | Team (promoted) | Pos | Price | Own% | Note |
|---|---|---|---|---|---|
| **Diop** | IPS | DEF | £4.0 | 18.3 | Highest-owned £4.0 DEF — field already backing him |
| **van Ewijk** | COV | DEF | £4.0 | 15.1 | £4.0 nailed full-back, attacking |
| **Thomas** | COV | DEF | £4.0 | 8.1 | £4.0 centre-back cover |
| **Palmer** | IPS | GK | £4.0 | 5.5 | Cheapest playing-GK backup |
| **Davis / O'Shea / Targett** | IPS/IPS/HUL | DEF | £4.0 | 2.9–5.0 | Deeper £4.0 DEF pool |

New-signing value (window arrivals the local model also under-rates; verify minutes on
final friendly): **Gyökeres** £7.5 ARS (12.1%, was £9.0 → −£1.5, striker in a top attack),
**Wirtz** £7.5 LIV (15.0%, creator), **Cherki** £7.5 MCI (8.4%). Treat with the
new-signing adaptation discount, but do **not** let the model's zero-history blind spot
auto-exclude them — they are priced/owned as genuine assets.

⚠️ Cross-check note (per gaffer): local team→club labels are CORRECT 2026/27 data and
match this live-API pull (Guéhi→MCI, Senesi→TOT, Coventry/Hull/Ipswich promoted). Local
**prices** remain stale (Aug-2) and local **xPts are thin / zero on new & promoted
players** — hence live sourcing above is authoritative and the enabler table is manual.
