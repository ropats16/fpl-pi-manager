# Weekly Cycle + Approval Protocol — locked (#12)

Grilling session 2026-08-21 ([issue #12](https://github.com/ropats16/fpl-pi-manager/issues/12)). Makes concrete the weekly rhythm (wake/brief timing relative to each GW deadline), the deadline-brief format, and the approve/debate/iterate reply protocol — on the locked runtime (#7 DIY Python daemon, systemd, Pi 4B), the locked gaffer architecture (#9), the locked security posture (#10), and the locked deploy flow (#11). This page is the human-loop build spec for #15/#16; the [map](map.md) bullet is the summary. Closes the #9/#10/#11 deferrals of "weekly cycle / approval-UX / decision-log format → #12".

**In one line:** two approval-bearing touchpoints per GW — a leisurely **draft** in Rohit's IST evening, a **T−2h final** checkpoint — gated by an exact-match `yes` in daemon code; the daemon never writes an unapproved change, and a pre-approved contingency covers "Rohit's asleep at the deadline".

Timing facts this rests on: Rohit is IST (UTC+5:30); FPL deadline = first kickoff − 90 min; so a Fri 17:30 UTC deadline = **23:00 IST** (late night), a typical Sat 11:00 UTC deadline = **16:30 IST** (afternoon). The IST/UK offset is why the draft is pinned to Rohit's clock, not a raw offset.

## 1. Weekly rhythm — the touchpoints relative to each GW deadline

Two approval-bearing touchpoints (draft + final), on top of #9's daily Scout and post-GW/monthly cadence. Exact clock hours → **#15 (`jobs.yaml`)**; this fixes the *anchoring principle* and *ordering*, not the minute.

| When | Wake | Anchor | Rohit-facing | Approval? |
|---|---|---|---|---|
| Daily 10:00 IST | **Scout** | fixed IST (#9) | only on urgent flag | no (appends `reports/gwNN/scout-log.md`) |
| ~T−72h | **Analysts** run stepwise (#9) | pre-deadline offset | — | no (write to `reports/gwNN/`) |
| ~24–48h out, **Rohit's evening IST** | **DRAFT brief** | **IST-pinned** (not raw offset) | yes — full approve/debate/iterate window | **yes** (draft-`yes` snapshot) |
| **T−2h** | **FINAL ping** | true pre-deadline offset | yes — unchanged: notify; changed: re-decide | **conditional** (see §3) |
| T−30..15m | **Daemon acts** (#9) | pre-deadline offset | post-lock receipt | executes the approved plan / contingency |
| after GW settles (~Mon/Tue) | **Post-GW review** | GW completion | yes — lean review + rulebook PR | **yes** (merges PR, never touches FPL) |
| monthly | chips / calibration (#9) | — | — | (#9 scope, not re-decided here) |

- **Draft is IST-pinned, not a raw offset.** A raw T−36h lands at 04:30 IST for a Sat-afternoon deadline; instead the draft posts in Rohit's evening on the day ≈24–48h out, so he reliably sees it awake with time to debate. The **final** stays a true T−2h offset (it's a pre-lock checkpoint, not a leisure read). The rare IST-night deadline falls through to the contingency/no-write backstop (§3).
- **Every GW runs the ritual, content-scaled.** Captaincy is a live FPL write every week, so there is no truly "no-action" GW. A quiet week's draft is just two lines ("roll FT, XI unchanged, (C) Haaland — nothing worth a −4. yes?"); same gates, less text.
- **Urgent / out-of-band path.** News that would void the plan snapshot (§3) — an owned starter/captain ruled out, material news or a price flag on a planned move — fires an **immediate off-schedule URGENT ping** using the same approval protocol (louder alert, marked URGENT), surfacing a carry-void early instead of ambushing Rohit at T−2h. **Quiet-hours 00:00–07:00 IST** hold *non-deadline-critical* pings until morning; a **deadline-critical** ping (deadline itself inside quiet hours) always fires — missing the lock is worse than a late buzz. An unanswered urgent ping still falls to the contingency/no-write backstop.

## 2. Deadline-brief format — lean Telegram, full log in repo

Telegram carries a **lean, phone-readable** brief (≤~250 words, headline-first); the durable reasoning lives in the repo.

- **Repo record (every GW):** the gaffer auto-writes `agent/reports/gwNN/decision-log.md` — signals leaned on, weights, AM pushback, rejected alternatives, confidence, provenance. Tier-4 inbox (#9/#11); the learning-loop baseline for the post-GW review (#21). Depth-on-demand: replying `why?` / `show working` makes the gaffer answer from this log.
- **Draft skeleton (8 parts):**
  1. **Header** — GW#, deadline (IST + UTC), FT banked, £ bank, chip status.
  2. **ASK** — transfer(s) in→out, hit cost, resulting XI delta, **(C)/(VC)**.
  3. **WHY** — 1–3 lines.
  4. **Confidence** — LOW / MED / HIGH.
  5. **Dissent** — the AM's single strongest counter (#9), or "AM: no material objection".
  6. **Watch** — deadline-risk flags to re-verify at the final (feeds the carry-void check).
  7. **Contingency** — named "if X ruled out → do Y" fallbacks the daemon may auto-run if Rohit is unreachable (§3).
  8. **Reply menu** — `yes / why / debate / change X`.

```
GW12 · Sat 16:30 IST (11:00 UTC)
1 FT · £0.3 bank · chips: WC/BB/TC/FH all avail

ASK: Gordon → Saka  (-0, uses FT)
  XI: Saka in for Gordon.  (C) Haaland  (VC) Salah
WHY: Saka 4-home run; Gordon rotation risk (Isak back).
Confidence: MED
Dissent: AM preferred Palmer (pens) — gaffer: Saka ceiling.
Watch: confirm Saka fit at final (knock Tue, trained Thu).
Contingency (auto if unreachable):
  • Saka ruled out → skip transfer, keep Gordon
  • Haaland ruled out → (C) → Salah
  • other starter ruled out → bench-sub per named order
Reply: yes / why / debate / change X
```

- **Final-ping — two forms:**
  - **Unchanged:** `GW12 FINAL — no change since your yes. Locking Sat 16:00 IST. XI/(C) as approved; Watch cleared (Saka trained, starts). Reply STOP to hold.` (opt-out; you may still interject.)
  - **Changed:** `⚠ GW12 CHANGED — Saka not in matchday squad. New ASK: skip transfer, keep Gordon; (C) Haaland. Reply yes to lock / debate. Deadline 16:30 IST.` (fresh `yes` required.)
- **Post-lock receipt.** After it writes (or no-writes), the daemon confirms exactly what got locked: `✅ GW12 locked: Gordon→Saka, (C) Haaland, VC Salah, 0 FT banked.` — closes the loop so Rohit always knows the real FPL state.

## 3. Approval protocol — approve / debate / iterate, gated in daemon code

Per #10, the write gate lives in **daemon code, never model judgment** ("assume the model IS injected").

**① Approval token.** Approval = the whole inbound message (trimmed, case-insensitive) **equals** one of `{yes, y, lock, approve}` — an exact match, **not** a substring. `yes but…` / `yes, and change X` are **not** approval; they route to the gaffer as debate/iterate. The token only flips the gate while daemon state = `AWAITING_APPROVAL` for a specific brief; a carry-void (below) resets that state, so a stale `yes` in scrollback cannot fire.

```
if state == AWAITING_APPROVAL(gwNN) and msg.strip().lower() in {yes,y,lock,approve}:
    approve(gwNN_snapshot)          # flip the gate — daemon, not model
else:
    route_to_gaffer(msg)            # debate / iterate / chat
```

**② The plan snapshot (what a `yes` approves).** On draft-`yes` the daemon freezes a structured snapshot:

```
{ transfers_in, transfers_out, hits, starting_xi[11], captain, vice, chip, contingencies[] }
```

Approval is **atomic over the whole snapshot** — you cannot half-approve a field (a transfer changes the XI, the captain depends on who's in). To alter one field you **iterate** (`change (C) to Salah`); the gaffer emits a revised **full** plan, that becomes the new snapshot, and it needs a fresh `yes`.

**③ Carry-void — what forces a fresh `yes` at the final.** "Changed" is a **struct diff in daemon code**, not the model's opinion of "materiality". At T−2h the daemon diffs the gaffer's final plan against the approved snapshot field-by-field:

- **any** difference in `{transfers, hits, xi, captain, vice, chip, contingencies}` → **carry VOID** → gaffer re-decides, fresh `yes` required;
- **identical** → notify-and-lock (unchanged final form), auto-executes at T−30..15m unless Rohit replies `STOP`;
- **bench-order-only** tweaks and **price-only** moves that don't touch those fields → snapshot still equal → carry holds silently.

**④ Debate.** Unbounded (Rohit's call how long). Each round the gaffer answers with cited evidence and either **concedes** (updates plan → new snapshot → re-`yes`) or **holds** with reasons (plan unchanged, still `AWAITING_APPROVAL`). It never auto-locks out of debate and never "wins" by fiat. On an explicit `change X` directive the gaffer **complies even when it disagrees** — and logs its dissent to `decision-log.md` for post-GW scoring (#9 "supreme-but-scored"; #11 club-owner: gaffer proposes/argues, Rohit disposes, outcomes judge who was right). Debate terminates only via: **`yes`** (lock) · **change→`yes`** · **timeout**.

**⑤ Timeout — no valid approval at the act-moment.** One uniform rule at T−30..15m:

- if a **pre-approved contingency** (snapshot §2, part 7 of the brief) matches the situation → the daemon **executes it deterministically in code** (no model judgment at act-time — Rohit literally approved this exact conditional action, so it stays inside approval-mode);
- otherwise → **no-write**: no transfer (FT banks), no captain change, no chip. FPL auto-carries the last-locked team and FPL's own auto-vice-captain covers a ruled-out captain. Daemon fires a loud alert (`⚠ GW12 locked with NO changes — no approval in time. [last team] stands, (C)=X, 1 FT banked.`).

This reconciles Rohit's "don't let me take a zero while asleep" with #10's no-unapproved-write posture: the only autonomous timeout action is a contingency Rohit already saw and approved; an injected model can at worst have *proposed* contingencies Rohit vetted, never invent a write. Worst uncovered case = field last GW's team and keep the FT.

**⑥ Chips never auto-carry.** A chip (WC / Free Hit / Bench Boost / Triple Captain) flows through the normal draft/final protocol, but any plan containing a chip **never** auto-locks on a carried draft-`yes` — it **always** requires a fresh `yes` at the final ping (opt-**in**), because it is irreversible once the GW starts and season-defining. The gaffer must give **advance heads-up** in the prior GW's review or the monthly note, so a chip is never a surprise same-GW ask. No fresh final `yes` → **chip held, normal team locks** (falls to the no-chip contingency).

**⑦ Post-GW review approval.** After the GW settles (~Mon/Tue), the gaffer emits a lean Telegram review (what it decided, what happened, how overrides — Rohit's and its own — scored, any durable lesson), writes outcomes into `decision-log.md`, and **only if it learned a rule worth keeping** opens a `gaffer/*` rulebook PR (#11). Same approve/debate/iterate verbs, but a `yes` here **breeze-merges the learnings PR** — it **never touches FPL**. Debating pushes back on the lesson; **silence leaves the PR open** (nothing auto-merges).

## Deferred / handed on

- **Exact clock hours** (draft IST slot, quiet-hours bounds, offset minutes) → **#15 `jobs.yaml`**; this page fixes anchoring + ordering only.
- **Templating + `AWAITING_APPROVAL` state machine + snapshot-diff + token parser** implementation, and the ≤25k prompt-cap assertion for briefs → **#16**.
- **FPL write path** the approval gate sits above (actuator) → **#13/#14**; until it's proven the whole loop runs against the fake-by-default write seam (#7 `daemon selftest`).
- Monthly chip/calibration cadence stays **#9**'s; not re-decided here.
