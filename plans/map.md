# Wayfinder Map: FPL Gaffer

Label: wayfinder:map · Charted 2026-08-16 · Spec: [issue #1](https://github.com/ropats16/fpl-pi-manager/issues/1) · Tickets: [GitHub issues #2–#23](https://github.com/ropats16/fpl-pi-manager/issues), sub-issues of #1 with native blocked-by edges and `wayfinder:<type>` labels. Frontier = open, unblocked, unassigned.

## Destination

A **build-ready blueprint** for the autonomous FPL gaffer on the Pi 4B (2GB): every architectural decision locked (agent runtime, LLM endpoint, Telegram flow, approval flow, actuator approach, repo layout, stage order) and a spec + staged roadmap another session can execute without further decisions.

## Notes

- System shape: Python math pipeline (collector → projections → ILP optimizer) + LLM "gaffer" via Telegram; cron wakes 1–3x/day + wake-on-message; approval mode — no FPL write without explicit Telegram "yes".
- LLM brain remote (OpenAI-compatible endpoint); all context/memory on the Pi as files; secrets (bot token, API key, FPL cookie) Pi-only.
- Standing decisions from charting: **pragmatism-first** runtime choice; **~$5/mo** API ceiling (lean prompt assembly is a design constraint); **this repo = source of truth, Pi pulls**; actuator **in scope, feasibility-gated**; **GW1 pre-deadline run in scope as task work** (deadline Fri 2026-08-21 17:30 UTC).
- Security standing rules (from claw research): memory-poisoning of persona/memory MD files is demonstrated; SKILL.md = executable code; allowlist own Telegram user ID; keys outside agent-readable workspace; no exposed ports (long-polling only).
- Facts: Pi host `fplpi`, user `saf`; FPL entry id in gitignored `.env` (`FPL_ENTRY_ID`, see `../.env.example`); prior-effort spec at [fpl-agent-system.md](../fpl-agent-system.md).
- Skills per ticket type: /grilling for grilling tickets, /research for research, /prototype when the visualizer graduates.

## Decisions so far

- Charting session (2026-08-16) — destination = build-ready blueprint; pragmatism-first runtime bias; ~$5/mo budget; git-repo-Pi-pulls dev flow; actuator in-scope feasibility-gated; GW1 run in-scope as tasks.
- [Claw/runtime landscape research](research/claw-research-2026-08.md) — PicoClaw primary candidate (Go, 10–20MB, markdown-native workspace, native Kimi/Qwen, Telegram long-polling, cron); ZeroClaw strong alt (security/velocity); ~500-line Python DIY viable; OpenClaw/Hermes/NanoClaw/TinyAGI ruled out on 2GB; resident daemon idles at ~1% RAM so scheduled-wake-vs-24/7 is a non-question; Kimi K2.5 ($0.60/$3.00 per 1M) or qwen-plus fit the budget, both with function calling.
- [Mac folder audit](research/mac-folder-audit-2026-08-16.md) — folder was a stale flattened chat-download, not a codebase; `fpl_optimizer.py` exists nowhere on the Mac (Pi or lost); prior agent's inventory partly fabricated (`draft_board.py`, `MASTER-PLAN.md` never existed); local pipeline can't run end-to-end (stale `fpl_api.py` lacks `csv` mode; projections selftest failing); `season-state.json` never initialized; no secrets present; PII (entry ID, `saf@fplpi`) in plaintext — scrub or keep repo private.
- [Pi inventory + recovery](research/pi-inventory-2026-08-16.md) ([#2](https://github.com/ropats16/fpl-pi-manager/issues/2)) — **nothing lost**: `fpl_optimizer.py`, csv-mode `fpl_api.py`, and `draft_board.py` all recovered from `~/fpl/` into the repo (audit's "missing/fabricated" claims were wrong). Pi = Pi 4B, Debian 13 trixie (not Lite), aarch64, Python 3.13.5, 1.8 GiB RAM, 21 G free. **No cron exists anywhere** and `logs/` is empty — claimed nightly 03:30 never ran. Data 11 days stale (2026-08-05, GW1–6); fresh fetch needed before GW1 run. Host resolves via `fplpi.local`, key auth installed.
- Spec + tickets published (2026-08-16) — the spec is [issue #1](https://github.com/ropats16/fpl-pi-manager/issues/1); 22 tickets (#2–#23) cut from spec + map with native sub-issue parenting, blocked-by dependencies, and type labels. Open tickets are found by query on the tracker, not listed here. Deadline-critical chain: #2→#3→#4→#5 before Fri Aug 21 17:30 UTC.
- Tree consolidated ([#3](https://github.com/ropats16/fpl-pi-manager/issues/3), 2026-08-16) — repo is the single authoritative tree: all four `.py` re-verified byte-identical (sha256) to `saf@fplpi.local:~/fpl/`, zero divergence. Killed the flattened chat-download cruft: `rm _index.md` (dead memory-index), fixed broken links in `fpl-agent-system.md` + `SKILL.md`. **PII decision (revised same day):** repo stays private for now, but the entry ID was moved out for eventual public safety. Correction: the entry ID is **not** in any `.py` — it's a runtime `--entry` CLI arg — so it only ever sat in docs. Now homed in gitignored `.env` (`FPL_ENTRY_ID`) with committed `.env.example` placeholder; scrubbed the two doc literals (id + team name — both link back to the real name via the public entry API). Residual, not yet scrubbed: Pi host/user (`saf@fplpi`, LAN-only mDNS, low risk) and git history (retains prior literals; not worth rewriting for low-risk public data). Skill-file shape (single vs multi-agent, one-skill-per-task) deferred to the [#9](https://github.com/ropats16/fpl-pi-manager/issues/9) architecture grilling, not settled here.

## Not yet specified

Fog (can't phrase sharply yet — everything sharp is now a ticket on the tracker):

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
