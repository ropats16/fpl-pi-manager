# Wayfinder Map: FPL Gaffer

Label: wayfinder:map · Charted 2026-08-16 · Tickets: none yet (Rohit creates them with his own skills)

## Destination

A **build-ready blueprint** for the autonomous FPL gaffer on the Pi 4B (2GB): every architectural decision locked (agent runtime, LLM endpoint, Telegram flow, approval flow, actuator approach, repo layout, stage order) and a spec + staged roadmap another session can execute without further decisions.

## Notes

- System shape: Python math pipeline (collector → projections → ILP optimizer) + LLM "gaffer" via Telegram; cron wakes 1–3x/day + wake-on-message; approval mode — no FPL write without explicit Telegram "yes".
- LLM brain remote (OpenAI-compatible endpoint); all context/memory on the Pi as files; secrets (bot token, API key, FPL cookie) Pi-only.
- Standing decisions from charting: **pragmatism-first** runtime choice; **~$5/mo** API ceiling (lean prompt assembly is a design constraint); **this repo = source of truth, Pi pulls**; actuator **in scope, feasibility-gated**; **GW1 pre-deadline run in scope as task work** (deadline Fri 2026-08-21 17:30 UTC).
- Security standing rules (from claw research): memory-poisoning of persona/memory MD files is demonstrated; SKILL.md = executable code; allowlist own Telegram user ID; keys outside agent-readable workspace; no exposed ports (long-polling only).
- Facts: Pi host `fplpi`, user `saf`; FPL entry 2928517 "Magnificos"; prior-effort spec at [fpl-agent-system.md](../fpl-agent-system.md).
- Skills per ticket type: /grilling for grilling tickets, /research for research, /prototype when the visualizer graduates.

## Decisions so far

- Charting session (2026-08-16) — destination = build-ready blueprint; pragmatism-first runtime bias; ~$5/mo budget; git-repo-Pi-pulls dev flow; actuator in-scope feasibility-gated; GW1 run in-scope as tasks.
- [Claw/runtime landscape research](research/claw-research-2026-08.md) — PicoClaw primary candidate (Go, 10–20MB, markdown-native workspace, native Kimi/Qwen, Telegram long-polling, cron); ZeroClaw strong alt (security/velocity); ~500-line Python DIY viable; OpenClaw/Hermes/NanoClaw/TinyAGI ruled out on 2GB; resident daemon idles at ~1% RAM so scheduled-wake-vs-24/7 is a non-question; Kimi K2.5 ($0.60/$3.00 per 1M) or qwen-plus fit the budget, both with function calling.
- [Mac folder audit](research/mac-folder-audit-2026-08-16.md) — folder was a stale flattened chat-download, not a codebase; `fpl_optimizer.py` exists nowhere on the Mac (Pi or lost); prior agent's inventory partly fabricated (`draft_board.py`, `MASTER-PLAN.md` never existed); local pipeline can't run end-to-end (stale `fpl_api.py` lacks `csv` mode; projections selftest failing); `season-state.json` never initialized; no secrets present; PII (entry ID, `saf@fplpi`) in plaintext — scrub or keep repo private.

## Not yet specified

Sharp questions ready to be ticketed (Rohit's ticketing skills will cut these):

- Pi inventory + recovery (task, urgent — unblocks GW1 run): SSH `saf@fplpi`, inventory `~/fpl/`, recover optimizer + csv-mode `fpl_api.py`, verify 03:30 cron, pull down.
- Consolidate Mac+Pi code into repo (task; after inventory): reconcile versions, PII scrub decision.
- GW1 pre-deadline run (task, before Aug 21): fetch → CSVs → projections → optimizer k-sweep → review Aug-5 squad; fix CSV handoff + failing selftest en route.
- Lock agent runtime (grilling): PicoClaw trial vs ZeroClaw vs minimal Python daemon; trial-then-decide vs commit.
- Lock LLM endpoint + routing (grilling): K2.5 vs qwen-plus vs OpenRouter; single model vs escalation routing.
- FPL actuator feasibility (research): 2026 auth flow, cookie lifetime, write endpoints, ToS/account risk — prior spec rejected automated writes; surface that tension.
- Actuator decision (grilling; after feasibility): direct writes vs manual-apply vs deep-link hybrid.
- Gaffer architecture (grilling; after runtime): persona/workspace files, single vs multi-agent (prior spec chose single, Rohit leans multi — resolve), memory conventions, lean prompt assembly.
- Security hardening (grilling; after runtime): allowlist, secrets placement, poisoning mitigations, skill-loading policy.
- Repo layout + Pi deploy (grilling): pull cadence, systemd units.
- Weekly cycle + approval flow (grilling; after architecture): wake schedule, brief format, approve/iterate/pushback loop.
- Assemble final blueprint (grilling; last): uniform stage map + roadmap incl. Phase 2/3 placement. Closing this = destination reached.
- Playable-game landscape (research, anytime): existing web football games — popularity, shortcomings, format → Phase 3 scoping.

Still fog (can't phrase sharply yet):

- **Phase 2 — gaffer visualizer front-end**: pitch board with team, gaffer avatar center, background agents at desks (Rohit's reference image). Waits on single-vs-multi decision + Rohit walking through the concept; likely a /prototype ticket then.
- **Phase 3 — web playable football game** (shareable, play vs others): waits on landscape research; likely its own wayfinder effort after this map closes.
- Learning loop (post-GW review grading, learnings log feeding prompts/skills).
- Chip strategy engine (8 chips, set-1 expiry GW19 / 2 Jan 2027).
- Price-watch alerts (livefpl.net = React SPA, needs XHR sniffing).
- Backtest harness for ad-hoc questions (e.g. GK+DEF same-team doubling).
- v2 projections model (Understat blend, odds layer, new-signing minutes).

## Out of scope

- Executing the blueprint's build stages — separate effort after this map closes (except the GW1 carve-out tasks above).
- Sentiment analysis — cut by prior spec, uncontested.
