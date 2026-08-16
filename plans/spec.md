# Spec: FPL Gaffer — autonomous FPL manager on the Pi

Status: ready-for-agent
Source: synthesized from [map.md](map.md), the prior-effort spec (fpl-agent-system.md), and the research reports in `plans/research/`. 2026-08-16.

## Problem Statement

Rohit plays FPL (entry 2928517, "Magnificos") and wants his team managed well without doing the grunt work himself: watching prices and injuries nightly, re-projecting points, re-optimizing transfers and captaincy before all 38 deadlines, and remembering lessons across the season. A previous attempt left him as a human relay between a chat assistant and his Raspberry Pi — the opposite of automation. The intelligence, context, and tools must live on his hardware (Pi 4B, 2GB), reachable from wherever he is, at negligible running cost.

## Solution

A resident "gaffer" agent on the Pi that Rohit talks to over Telegram. Deterministic Python does the math (collector → projections → optimizer, file-based, stdlib-first); a remote LLM (OpenAI-compatible endpoint, ~$5/mo ceiling) does the judgment, woken by cron 1–3x/day or by an incoming message — never burning tokens idle. Each gameweek the gaffer assembles a deadline brief — recommended XI, captain, transfers, reasoning — and sends it for approval. Rohit replies approve / debate / iterate; the gaffer pushes back or adapts, and only acts on the team after an explicit "yes". Everything the gaffer knows — persona, season state, memory, learnings — lives as files on the Pi, in this git repo's working tree (repo is source of truth; Pi pulls).

## User Stories

1. As an FPL manager, I want a pre-deadline brief on Telegram (XI, bench order, captain/vice, transfers, reasoning), so that I can decide my gameweek in one glance.
2. As an FPL manager, I want to approve the brief with a single reply, so that acting on it costs me seconds.
3. As an FPL manager, I want to push back on a recommendation and get an honest, statistically-grounded counter-argument or concession, so that the final call is genuinely better than either of us alone.
4. As an FPL manager, I want the gaffer to iterate on a rejected plan and return an updated one, so that debate converges instead of stalling.
5. As an FPL manager, I want nothing changed on my FPL team without my explicit approval, so that I keep final authority over my season.
6. As an FPL manager, I want approved changes applied for me (feasibility permitting), so that I never have to log into the FPL site as a middleman.
7. As an FPL manager, I want a manual-apply fallback with exact instructions when direct actuation is unavailable, so that a broken integration never costs me a deadline.
8. As an FPL manager, I want the agent to wake when I message it, so that I get answers on demand, not on a schedule.
9. As an FPL manager, I want scheduled wakes (1–3x/day) for routine checks, so that news and prices are monitored without me prompting.
10. As an FPL manager, I want to send a link ("this player's injured — seen this?") and have the gaffer research and fold it into its thinking, so that one-off intel isn't lost.
11. As an FPL manager, I want to request ad-hoc analyses (e.g. backtest doubling up on a GK+DEF from the same club), so that strategy questions get evidence-based answers.
12. As an FPL manager, I want learnings from analyses recorded (specific and general), so that the gaffer compounds knowledge across the season.
13. As an FPL manager, I want recorded learnings to actually feed future prompts and recommendations, so that the system gets smarter, not just bigger.
14. As an FPL manager, I want alerts when my players' prices are about to move or their status changes, so that I can act before value is lost.
15. As an FPL manager, I want a post-gameweek review comparing projections to actuals, so that I can see whether the model earns its recommendations.
16. As an FPL manager, I want chip strategy (8 chips, first set expiring GW19 / 2 Jan 2027) factored into weekly advice, so that chips aren't wasted or forgotten.
17. As an FPL manager, I want free-transfer rollover (up to 5) tracked in the season state, so that transfer advice reflects what I actually have.
18. As an FPL manager, I want the gaffer to know my current squad, bank, and pending plans from a single season-state source of truth, so that advice is never based on stale assumptions.
19. As an FPL manager, I want deadline-aware timing (brief lands comfortably before each deadline), so that I'm never rushed or too early to matter.
20. As an FPL manager, I want the API spend held to ~$5/mo, so that automation never costs more than the hobby.
21. As an FPL manager, I want only my Telegram user ID able to command the agent, so that nobody else can steer my team or my Pi.
22. As an FPL manager, I want secrets (bot token, LLM key, FPL cookie) stored only on the Pi outside the agent-readable workspace, so that a prompt-injected or poisoned agent can't exfiltrate them.
23. As an FPL manager, I want the agent's memory files protected against poisoning (reviewed writes, no untrusted content persisted verbatim), so that one malicious page can't backdoor my gaffer.
24. As a developer, I want the repo to be the single source of truth with the Pi pulling updates, so that stale-copy drift (the failure of the prior effort) can't recur.
25. As a developer, I want every pipeline stage runnable and testable as a CLI on fixture files, so that I can verify behavior without network, tokens, or the Pi.
26. As a developer, I want each tool's selftest green, so that a red gate means a real regression, not accepted noise.
27. As a developer, I want the daemon testable with all externals (FPL, LLM, Telegram) faked at the HTTP edge, so that the full conversation-to-action loop is verifiable offline.
28. As a developer, I want the daemon supervised (auto-restart, boot-start), so that a crash or power cut doesn't silently end the season.
29. As a developer, I want structured logs of wakes, prompts, decisions, and actions, so that I can debug why the gaffer said what it said.
30. As an FPL manager, I want the gaffer to survive FPL API quirks (stale pre-season deadlines, schema drift) via health checks, so that garbage data never reaches a recommendation.

## Implementation Decisions

- **Split of labor**: deterministic Python computes; the LLM judges. The LLM never does arithmetic the optimizer can do; the pipeline never makes judgment calls the LLM should own.
- **Pipeline modules** (existing, stdlib-only, file-based): collector (fetch/distill/csv/diff/selftest against the FPL API, with health checks: player count bounds, exactly 38 events), projections (xPts over a 6-GW horizon: pts/90 ⊕ ep_next blend × minutes share × position-split FDR × status × decay; <450-min floor), optimizer (PuLP+CBC ILP: scratch squad, from-squad k-change sweep, XI/captain under formation/budget/3-per-club constraints — to be recovered from the Pi or rebuilt from its documented interface). Stages communicate only via files (snapshot JSON → distilled CSVs → projections CSV → optimizer output).
- **Gaffer daemon**: resident process on the Pi (resident costs ~1% RAM; Telegram long-polling requires residency — webhooks rejected: no inbound ports). Wakes on Telegram update or cron; assembles prompts from workspace files (persona, season state, distilled data, learnings) and calls an OpenAI-compatible endpoint with function calling. Runtime (PicoClaw vs ZeroClaw vs ~500-line DIY daemon) is **pending** — the spec's daemon contract (HTTP-edge behavior) must hold under any of the three.
- **Approval flow**: proposal → Rohit's reply → approve (act) / debate (argue back with evidence) / iterate (revise and re-propose). No FPL mutation outside an approved proposal. Actuator mode (direct API writes vs manual-apply vs deep-link) is **pending feasibility research**; the interface is a single act-on-team boundary with a dry-run mode so the mode can change without touching the flow.
- **Season state**: one machine-readable state document (squad, bank, FTs, chips, pending plans, history) is the sole source of truth for "my season"; every wake reads it, every acted decision writes it back. (Prior effort's core wiring failure — the state file was never written back — must be a tested invariant.)
- **Memory/learnings**: file-based on the Pi, in-repo conventions; learnings log append-only with specific + general entries; prompt assembly includes a bounded selection, not the whole log (token ceiling).
- **Token discipline**: prompts assembled from distilled CSVs/state summaries, never raw 8MB API payloads; scheduled wakes batch their thinking; cheap default model (Kimi K2.5 or qwen-plus class) with escalation only if a routing decision later adds it.
- **Security**: Telegram user-ID allowlist; secrets outside the agent-readable workspace; skills/memory writes treated as privileged (SKILL.md is executable code; memory poisoning is a demonstrated attack); no exposed ports.
- **Deploy**: git pull on the Pi + supervised service (systemd, restart-always); data/logs/secrets local and gitignored.

## Testing Decisions

- Good tests exercise external behavior at the two agreed seams; no mocking of internals, no testing of implementation details.
- **Seam 1 — file-contract CLI (existing)**: each pipeline stage tested by running its CLI on fixture files and asserting on output files. The built-in selftests are this seam; the projections selftest is currently red (v1.1 minutes-floor vs `newguy` assert) and must be fixed to green, not deleted or skipped. Diff/health-check behavior tested with crafted snapshot pairs.
- **Seam 2 — HTTP edge (new, the only new seam)**: daemon tests fake FPL API, LLM endpoint, and Telegram at the network boundary (stub server or record/replay). Canonical tests: inject a Telegram update → assert assembled prompt contents and bounded size; scripted LLM reply → assert proposal message; approval reply → assert actuator call (or dry-run record) and season-state write-back; non-allowlisted sender → assert refusal; cron wake → assert batch behavior and no action without approval.
- Prior art: the existing `selftest` subcommands (synthetic 600-player payload pattern) — extend that idiom rather than introducing a test framework the Pi can't cheaply run.

## Out of Scope

- Phase 2 visualizer front-end and Phase 3 web playable game (fog on the map; separate efforts).
- Sentiment analysis (cut by prior spec, uncontested).
- v2 projections model (Understat blend, odds layer, new-signing minutes logic) — v1.1 model ships first.
- Shadow-team tournaments / red-team modes from the prior spec's later phases.
- Multi-user support — single manager, single entry, single Telegram ID.

## Further Notes

- **Pending decisions that gate implementation order** (tracked on the map, to be ticketed): agent runtime; LLM endpoint + routing; actuator mode (feasibility research first — note the prior spec explicitly rejected automated writes as ToS risk, Rohit has since chosen feasibility-gated in-scope); single- vs multi-agent gaffer (prior spec: single; Rohit leans assistant-coach sub-agents); repo layout + deploy cadence; weekly cycle timing.
- **Recovery precondition**: the optimizer and the csv-mode collector exist (if anywhere) only on the Pi (`saf@fplpi:~/fpl/`); inventory + recovery is the urgent first task, ahead of the GW1 deadline (Fri 2026-08-21 17:30 UTC).
- The FPL API's pre-season event deadlines are known to be stale placeholders; deadline logic must source truth from refreshed data, not cached bootstrap.
- PII (entry ID, Pi host/user) is in plaintext in-repo — keep the repo private or scrub before any public push.
