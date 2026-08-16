# GW1 2026-27 — Gaffer's Brief

**The reviewed GW1 team selection.** One-shot multi-agent gaffer run (issue
[#25](https://github.com/ropats16/fpl-pi-manager/issues/25)), compiled 2026-08-16/17.
**GW1 deadline: Fri 2026-08-21 17:30 UTC.** Initial 15-man squad, £100.0m budget.

Built from five analysis-angle sub-agents + an assistant-manager pushback loop, all
grounded in the [#24 team-selection research wiki](../research/team-selection/index.md)
and audited against live 2026-27 data. Full reasoning + weights: [decision-log.md](decision-log.md).
Raw signals: [availability](signals/availability.md) · [fixtures-odds](signals/fixtures-odds.md)
· [talent-style](signals/talent-style.md) · [value-ownership](signals/value-ownership.md)
· [optimizer-audit](signals/optimizer-audit.md) · [assistant-manager pushback](signals/assistant-manager-pushback.md).

> **⚠️ This is a pre-deadline draft, not necessarily the final team.** Per the
> [approach note](approach.md), the full-vision gaffer may amend before the deadline if
> new intel lands. **Two hard actions remain before lock** (see §Deadline checklist).

---

## The squad (£100.0m, £0.0 bank)

**Formation 3-4-3. Captain in CAPS.**

### Starting XI
| Pos | Player | Team | £ | Why (one line) |
|---|---|---|---|---|
| GK | **Raya** | ARS | 6.0 | Best clean-sheet spot of GW1 (v Coventry, ~82% fav); 32% template. |
| DEF | **Gabriel** | ARS | 8.0 | Set-piece goal threat + the Coventry CS; the one template DEF. |
| DEF | **Mitchell** | CRY | 4.5 | Nailed (36 starts); v Everton = GW1's lowest goal cluster (CS-lean). |
| DEF | **Shaw** | MUN | 4.5 | v Hull = soft CS. ⚠ fitness MED — see deadline checklist. |
| MID | **Bruno Fernandes** | MUN | 12.0 | 2nd anchor: undisputed pen + set-pieces; soft Hull opener. |
| MID | **Mbeumo** | MUN | 8.0 | Nailed HIGH, backup pens; settled Man Utd attack v Hull. |
| MID | **Szoboszlai** | LIV | 7.0 | 41.6% heavy template — rank-protection (pen NOT counted; see log). |
| MID | **Yates** | NFO | 4.5 | Cheap enabler-starter, home v Leeds. ⚠ verify nailed at deadline. |
| FWD | **HAALAND (C)** | MCI | 15.5 | The anchor + captain: 72.5% owned, best goal env, shortest scorer (1.75). |
| FWD | **João Pedro** | CHE | 7.5 | 57.9% template; Alonso's talisman; unlocks the two-premium build. |
| FWD | **Calvert-Lewin** | LEE | 6.0 | £6.0 pen-taking template forward (25.9%); 3rd-forward value. |

### Bench (autosub priority order)
| # | Player | Team | £ | Role |
|---|---|---|---|---|
| GK | Palmer | IPS | 4.0 | Backup keeper. |
| 1 | **Diop** | IPS | 4.0 | First autosub — nailed £4.0 DEF (18.3%), home v Sunderland (not a battering). |
| 2 | Hughes | CRY | 4.5 | Enabler mid (⚠ verify identity/nailedness — name-collision w/ a Hull "Hughes"). |
| 3 | van Ewijk | COV | 4.0 | Deep cover (COV @ Arsenal — last resort only). |

**Captain: Haaland · Vice-captain: Bruno Fernandes.**

**Spend:** GK 10.0 · DEF 25.0 · MID 36.0 · FWD 29.0 = **£100.0m**, bank £0.0.
**Club cap (max 3):** MUN 3 (Bruno/Mbeumo/Shaw), ARS 2, CRY 2, IPS 2, all others ≤1. ✓

---

## Transfers vs the recorded Aug-5 squad

**N/A — no Aug-5 squad exists.** The FPL entry has no picks recorded
(`entered_events: []`, `current_event: null`) and `season-state.json` has `squad: null` —
this is the **season opener**, so the brief is an **initial 15-man construction**, not a
set of transfers. The acceptance-criteria "transfers vs Aug-5 squad" line is therefore
satisfied as *"initial build; the Aug-5 baseline the ticket assumed was never captured."*
This absence is logged (not fabricated into a phantom prior squad — see
[decision-log](decision-log.md#the-missing-aug-5-squad)).

---

## The three big calls (headlines)

1. **Two premiums, no more: Haaland (C) + Bruno.** The £100m math fits exactly two £12m+
   assets; a third guts the spine. Both are undisputed pen takers into soft openers.
2. **Arsenal for the clean sheet, not the attack.** ARS are the week's biggest mismatch
   (~82% v Coventry) but the attack is a minefield — Saliba & Timber OUT, Gyökeres benched
   in the Community Shield (Havertz started CF), Saka load-managed + pen-disputed. So we
   **bank Raya + Gabriel** and refuse the attacking guess.
3. **The optimizer was overruled.** Its ILP picks rest on a thin last-season projection
   that literally can't see promoted-side or new-signing players; used only as a structural
   sanity check, not trusted. See [optimizer-audit](signals/optimizer-audit.md).

---

## Deadline checklist (T-15→T-5 team-news, Fri 17:30 UTC)

Low-information now; these are the only live-data re-checks that can change the XI:

- [ ] **Shaw fitness** (MUN). If doubtful → **pivot to Kayode (BRE £4.5)**, home, HIGH-nailed
      (NOT Cash — he's in the Brighton-Villa shootout, poor CS).
- [ ] **Hughes** (CRY) — confirm it's the nailed Palace man, not the Hull namesake; if not
      nailed, swap for any confirmed-nailed £4.5 mid.
- [ ] **Yates** (NFO) — confirm starts under Glasner; else reshuffle the 4th XI-mid slot.
- [ ] **Isak / Palmer / Saka / Watkins** — not owned, but confirms whether any becomes a
      late must-consider. **Gyökeres** — if he unexpectedly starts CF, revisit (still not captain).
- [ ] Optional: fresh `./run_pipeline.sh fetch` for live prices/status (fixes stale locals;
      will NOT fix the model gaps — treat as sanity check only).

## First forward-look (GW2+, not now)
- Defence is thin (Gabriel + two £4.5). **First upgrade target: a £6.0 Man City DEF**
  (O'Reilly / Guéhi) for template CS in the round's #1 fixture — unfundable at GW1 without
  dropping template.
- **Szoboszlai** is a GW2-4 sell candidate once Liverpool's attacking roles settle under Iraola.
- **Semenyo** (MCI £8.5) is the named ceiling/covariance-diversification pivot off Mbeumo.

---

*Serves as the baseline for post-GW review ([#21](https://github.com/ropats16/fpl-pi-manager/issues/21)).
Cross-links: [approach](approach.md) · [map](../map.md) · [research wiki](../research/team-selection/index.md).*
