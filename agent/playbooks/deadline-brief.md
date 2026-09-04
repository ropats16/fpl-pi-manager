# Playbook — Deadline brief (draft)

Produce the **draft** deadline brief: the leisurely, IST-evening ask that opens Rohit's approve/debate/iterate window (~24–48h out). It goes to Telegram lean and phone-readable — **≤~250 words, headline-first.** The full reasoning lives in `reports/gwNN/decision-log.md`, which you auto-write every gameweek; the brief is the summary, not the record.

By now the analysts and the AM have reported. You've formed the plan. Write it as the eight-part skeleton below. Every gameweek runs the ritual, content-scaled — a quiet week is two lines ("roll FT, XI unchanged, (C) Haaland — nothing worth a −4. yes?"), same gates, less text.

## The 8-part skeleton

1. **Header** — GW#, deadline (IST + UTC), FT banked, £ bank, chip status.
2. **ASK** — transfer(s) in→out, hit cost (−0 / −4), resulting XI delta, **(C)** and **(VC)**. This is the concrete action a `yes` approves.
3. **WHY** — 1–3 lines. The core reasoning, no padding.
4. **Confidence** — LOW / MED / HIGH.
5. **Dissent** — the AM's single strongest counter and how you resolved it: `Dissent — <counter> — conceded: <what changed>` or `— held: <why>`; "AM: no material objection" when the AM found none; "AM unavailable" when it did not report. The counter is shown whether or not you concede.
6. **Watch** — deadline-risk flags to re-verify at the final ping (feeds the carry-void check).
7. **Contingency** — named "if X ruled out → do Y" fallbacks the daemon may auto-run if Rohit is unreachable at the lock. Cover the captain and any at-risk starter.
8. **Reply menu** — `yes / why / debate / change X`.

## Rules

- **Headline first.** The ASK and the captain are what he reads on a lock screen — lead with them.
- **Facts cite; judgments are declared.** WHY separates "Isak back (presser)" from "I read Gordon as rotation risk."
- A `yes` approves the **whole plan atomically** — transfers, XI, (C), (VC), contingencies. Don't offer half-approvals; if he wants one field changed he iterates and you re-emit a full plan.
- Any plan **containing a chip** needs a fresh `yes` at the final — never let it ride a carried draft-yes. Flag it, and make sure you gave advance heads-up in the prior review or monthly note.
- Keep it under ~250 words. If you're over, cut prose, not the skeleton.

## Machine plan block

After the eight-part skeleton, **always** end the brief with a fenced ` ```plan ` JSON block — this is the machine snapshot the daemon freezes as what a `yes` approves (#18). The daemon strips it before Telegram, so it never adds to your word count; the human sees only the prose skeleton above it.

Emit it with **exactly** these keys:

```plan
{
  "transfers_in": ["<web name>", ...],
  "transfers_out": ["<web name>", ...],
  "hits": 0,
  "starting_xi": ["<11 web names>"],
  "captain": "<web name>",
  "vice": "<web name>",
  "chip": null,
  "contingencies": ["if <X> ruled out → <do Y>", ...]
}
```

- `transfers_in` / `transfers_out` are paired in order (first out ↔ first in). Empty lists = roll the FT.
- `hits` is the point cost as a positive integer (0 for none, 4 for one hit, …).
- `starting_xi` is all 11 starters as **web names** (the projection join key), `chip` is `null` unless you are actually playing one this GW.
- `contingencies` are the named "if X → Y" fallbacks from part 7, one string each.
- On an **iterate** (`change X`), re-emit the **FULL** brief *and* a fresh block — a partial block is not a plan. The struct diff at the final ping compares this block field-by-field, so anything you change here forces a fresh `yes`.
