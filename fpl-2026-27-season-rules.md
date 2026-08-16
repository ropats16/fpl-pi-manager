# FPL 2026/27 Season Facts
**Project:** fpl-agent-system · **Verified:** 2026-08-01 (premierleague.com via web_fetch + Sky Sports)

- **Season starts Friday 21 August 2026** — a week later than usual due to the 2026 World Cup. Opener: Arsenal v Coventry (newly promoted) at the Emirates. Final day: Sun 30 May 2027.
- 33 weekend + 5 midweek rounds. Summer transfer window: 15 Jun – 31 Aug 2026 (window closes AFTER GW1 — early-GW transfer risk for new signings).
- 8 chips: two sets of Wildcard / Free Hit / Triple Captain / Bench Boost — set 1 usable GW1–19, set 2 GW20–38. **First set expires at the GW19 deadline (2 Jan 2026, ~18:30 UK)** — chip timing is a real planning constraint.
- Up to **5 rolled free transfers**.
- **DefCon points** continue (defenders/CDMs earn for defensive contributions; verify exact thresholds at build time).
- Post-World-Cup season → elevated rotation/minutes risk early GWs for players who went deep in the tournament.
- FPL API event-1 deadline field currently shows 2026-08-15T17:30:00Z — **stale/pre-season placeholder, treat API dates as provisional until GW1 lock.**

## To verify when game data firms up (all endpoint-checkable)
- DefCon thresholds/values (bootstrap-static `element_types`)
- Exact chip mechanics text (`events` / game settings)
- Official GW1 deadline (events[0].deadline_time — re-pull at build time)
