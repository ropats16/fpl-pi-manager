# FPL Gaffer — Blueprint Plan

Charted 2026-08-16. Repo: `fpl-pi-manager` (this repo = source of truth; Pi pulls).

## Context

Autonomous FPL manager on Raspberry Pi 4B (2GB, ARM64): Python math pipeline (collector → projections → ILP optimizer) + LLM-driven "gaffer" agent reachable via Telegram, waking 1–3x/day + on message, approval-mode before any team change. A previous agent effort drifted into using Rohit as a relay between chat and the Pi; this plan re-charts the route. Destination: a **build-ready blueprint** — every architectural decision locked (agent runtime, LLM endpoint, Telegram flow, approval flow, actuator, repo layout, stage order) plus a staged roadmap another session can execute without further decisions.

## Decisions locked (charting session, 2026-08-16)

- **Destination** — build-ready blueprint; stage execution is a later effort (except GW1 carve-out below).
- **Runtime bias** — pragmatism first: pick what reliably automates on 2GB; claw frameworks are pattern-sources, not mandatory adoptions.
- **API budget** — ~$5/mo ceiling → lean prompt assembly (distilled CSVs, not raw JSON) is a design constraint.
- **Dev flow** — this git repo is source of truth; develop on Mac, Pi pulls; secrets/data Pi-local + gitignored.
- **Actuator** — in scope, feasibility-gated: research FPL auth/write-API first; fallback = manual apply.
- **GW1 deadline (Fri 2026-08-21 17:30 UTC)** — pre-deadline run in scope as manual task work; blueprint work continues in parallel.

## Inherited constraints (prior effort)

- Approval mode locked: no FPL write without explicit Telegram "yes".
- Hybrid wake model: agent sleeps; wakes on cron (1–3x/day) or Telegram message. No 24/7 token burn.
- LLM brain is remote (Kimi/Qwen-class, OpenAI-compatible endpoint); all context/memory lives on the Pi as files.
- Secrets (bot token, API key, FPL cookie) live only on the Pi.
- Assistant-coach sub-agents (Scout/Statto/Doc) desirable for token scoping — but prior spec chose single-agent; tension to resolve.

## Audit findings (this folder) — full report: [research/mac-folder-audit-2026-08-16.md](research/mac-folder-audit-2026-08-16.md)

The folder was **8 files downloaded flat out of a hyper.io chat UI** (Aug 2 + Aug 16 batches), not a codebase.

- Real + good: `fpl-agent-system.md` (decision-dense master spec), season-rules + reachability docs, both Python files stdlib-only.
- `fpl_optimizer.py` **exists nowhere on this Mac** — on the Pi or lost. Highest-value recovery target.
- `draft_board.py` and `MASTER-PLAN.md` were never real (prior agent's inventory partly fabricated).
- `fpl_api.py` here is stale (no `csv` mode) → pipeline can't run end-to-end on the Mac.
- `fpl_projections.py` ships a failing selftest (v1.1 minutes-floor patch vs `newguy` assert).
- `season-state.json` never initialized (all mutable fields null).
- No secrets anywhere (clean). PII note: entry ID 2928517 + `saf@fplpi` in plaintext — private repo or scrub before any GitHub push.

## Claw/runtime research — full report: [research/claw-research-2026-08.md](research/claw-research-2026-08.md)

- **PicoClaw** (sipeed, Go, 10–20MB): closest spec match — markdown skills, AGENTS/SOUL/USER/MEMORY/HEARTBEAT.md workspace, built-in cron, Telegram long-polling, native Kimi/Qwen/OpenRouter. Pre-1.0. Primary candidate.
- **ZeroClaw** (Rust, 7–8MB, most active): best security model; SQLite-first memory; prebuilt aarch64 only (never compile on Pi). Strong alternative.
- **DIY**: full personal Telegram agent ≈ 500 lines Python (nanoclaw-py template; Nanobot ~4k lines / 191MB as middle ground).
- **Ruled out on 2GB**: OpenClaw (400MB–1.9GB, CVEs), Hermes, NanoClaw (Anthropic-locked + Docker), TinyAGI.
- **Key simplification**: scheduled-wake vs 24/7 is a non-question — resident daemon idles at ~1% RAM, long-polling needs residency anyway. Resident daemon + built-in cron; tokens are the only real cost.
- **Models**: Kimi K2.5 ($0.60/$3.00 per 1M) or `qwen-plus` both fit $5/mo; OpenRouter for single-key A/B. Function calling on both.
- **Security standing rules**: memory-poisoning of persona/memory MD files is a demonstrated attack; SKILL.md = executable code; allowlist own Telegram ID; keys outside agent-readable workspace; no exposed ports.

## Open decisions (backlog — to be ticketed with your own skills)

Ordered; blockers in parentheses.

1. **Pi inventory + recovery** (task, URGENT): SSH `saf@fplpi`, inventory `~/fpl/`, recover optimizer + csv-mode `fpl_api.py`, verify 03:30 cron, pull code/data down.
2. **Consolidate Mac+Pi into repo** (task; needs 1): reconcile versions, interim layout, PII scrub decision.
3. **GW1 pre-deadline run** (task, before Aug 21; needs 1): fetch → CSVs → projections → optimizer k-sweep → review Aug-5 squad; fix CSV handoff + failing selftest en route.
4. **Lock agent runtime**: PicoClaw trial vs ZeroClaw vs minimal Python daemon; trial-then-decide vs commit.
5. **Lock LLM endpoint + routing**: K2.5 vs qwen-plus vs OpenRouter; single model vs escalation routing.
6. **FPL actuator feasibility** (research): 2026 auth flow, cookie lifetime, write endpoints, ToS/account risk. Prior spec rejected automated writes — surface tension.
7. **Actuator decision** (needs 6): direct writes vs manual-apply vs deep-link hybrid.
8. **Gaffer architecture** (needs 4): persona/workspace files, single vs multi-agent (resolve spec tension), memory conventions, lean prompt assembly.
9. **Security hardening** (needs 4): allowlist, secrets placement, poisoning mitigations, skill-loading policy.
10. **Repo layout + Pi deploy** (needs 2, 4): pull cadence, systemd units.
11. **Weekly cycle + approval flow** (needs 8): wake schedule, deadline-brief format, approve/iterate/pushback loop.
12. **Assemble final blueprint** (needs 7, 9, 10, 11): uniform stage map, roadmap incl. Phase 2/3 placement. Closing this = destination reached.
13. **Playable-game landscape** (research, anytime): existing web football games — popularity, shortcomings, format (free-play vs leagues) → Phase 3 scoping input.

## Not yet specified (fog)

- **Phase 2 — gaffer visualizer front-end**: pitch board with team, gaffer avatar center, background agents at desks (per Rohit's reference image). Blocked on single-vs-multi decision (#8) + Rohit walking through the concept; likely a /prototype session then.
- **Phase 3 — web playable football game** (shareable, play vs others): scoping waits on #13; likely its own effort after this plan closes.
- Learning loop (post-GW review grading, learnings log feeding prompts/skills).
- Chip strategy engine (8 chips, set-1 expiry GW19 / 2 Jan 2027).
- Price-watch alerts (livefpl.net = React SPA, needs XHR sniffing).
- Backtest harness for ad-hoc questions (e.g. GK+DEF same-team doubling).
- v2 projections (Understat blend, odds layer, new-signing minutes).

## Out of scope

- Executing blueprint build stages (separate effort) — except GW1 carve-out (#1–3).
- Sentiment analysis (cut by prior spec, uncontested).
