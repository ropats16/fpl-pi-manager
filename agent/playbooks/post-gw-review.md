# Playbook — Post-gameweek review

After the gameweek settles (~Mon/Tue), review how the last set of decisions played out. This is the learning loop — the mechanism that keeps your judgment honest over a season. Emit a lean Telegram review, write outcomes into `reports/gwNN/decision-log.md`, and open a rulebook PR **only if** you learned a rule worth keeping.

## Score the decisions

- Pull the decision log for the gameweek: what you decided, the signals you leaned on, the alternatives you rejected, the AM's pushback, your confidence.
- Set each call against the **actual outcome**. Did the transfer pay? Did the captain haul? Did a rejected alternative outscore the pick? Score every override — yours **and** Rohit's `change X` directives — against what happened.
- Be specific and numeric where you can: points gained/lost vs the baseline plan and vs the alternatives.

## Luck vs process — be honest

This is the discipline that matters most. **A good outcome from a bad process is still a bad decision, and a bad outcome from a good process is still a good decision.** Say which it was. If the captain hauled off a call the evidence didn't support, name it as luck, not vindication. A lucky win never lowers the evidence bar — the rulebook is explicit on this, and the monthly review judges the *pattern*, not the scoreline. Don't grade yourself by the result alone.

## Extract durable lessons

- Only distil a lesson that will **recur** — a repeatable pattern, not a one-off. "Backed a promoted-side striker on a thin sample; regressed hard" is durable. "Haaland blanked once" is not.
- A lesson worth keeping goes to `memory/MEMORY.md` — distilled in your own words with provenance (which GW taught it), never raw fetched text.
- Re-read `memory/learnings.md` — the append-only log where every ad-hoc analysis drops its lessons as it goes (#20). Promotion is **this** review's job: the ones that held up against the outcome get rewritten into `MEMORY.md` in your own words; the rest stay in the log as the record of what you believed at the time. Never edit the log itself.
- If it warrants a change to the override rulebook, open a `gaffer/*` PR. Rohit's `yes` merges the learnings PR — it **never touches FPL**. Silence leaves it open; nothing auto-merges.

## Output

A short, honest Telegram review: what you decided, what happened, how the overrides scored, and any durable lesson. No spin. Own the misses.
