# Playbook — Deadline final (T−2h)

The **final** pre-deadline checkpoint (~T−2h). Not a leisure read — a lock check. By now the draft `yes` (if any) is a frozen snapshot; your job is to re-verify the Watch flags from the draft and re-decide, then re-emit the plan so the daemon can diff it against what Rohit approved.

The daemon does the diff in code, not you (#18 / weekly-cycle.md §3③): it compares your fresh plan block field-by-field against the approved snapshot. So you do not judge "materiality" — you just report the truthful current plan. Any real change (a ruled-out starter, a forced captain swap, a new hit) shows up as a struct diff and the daemon demands a fresh `yes`; an identical plan carries the draft `yes` and auto-locks.

## What to check

1. **Watch flags** — walk each deadline-risk flag the draft raised. Resolved (trained, in the matchday squad, price held) or triggered (ruled out, benched, priced out)?
2. **Re-decide** — if a flag triggered, apply the named contingency or form a fresh plan. If all clear, the plan is unchanged.
3. **Chips** — a chip **never** auto-carries a draft `yes` (§3⑥). If the plan plays one, it needs a fresh `yes` here; say so explicitly.

## Output

Same eight-part skeleton as the draft (headline-first, ≤~250 words), but frame it as the T−2h final check — lead with whether anything changed since the `yes`:

- **Unchanged:** state it plainly ("Watch cleared, plan as approved") so Rohit knows a `yes` isn't needed again.
- **Changed:** lead with the change and the new ASK; a fresh `yes` is required.

Then end with the **same ` ```plan ` machine block** as the draft (see `deadline-brief.md` → "Machine plan block") — exact keys, full XI, `chip` only when playing one. The daemon diffs this block; emit the real current plan, not the old one.
