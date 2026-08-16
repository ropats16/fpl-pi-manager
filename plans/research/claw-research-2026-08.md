# Claw-style agent frameworks for Pi 4B 2GB — research (Aug 2026)

Subagent web-research findings. Source-quality warning: the claw ecosystem is flooded with SEO content farms; numbers below are flagged where they trace only to vendor claims. Verify against repos before committing.

## TL;DR

OpenClaw (Node, idles ~400MB, spikes to GB-scale) is the wrong tool for 2GB. Credible candidates: **PicoClaw** (Go, 10–20MB) and **ZeroClaw** (Rust, 7–8MB idle). PicoClaw matches the spec almost line-for-line (markdown skills, SOUL/AGENTS/MEMORY.md, Telegram long-polling, built-in cron, native Kimi+Qwen+OpenRouter). ZeroClaw is better-engineered, more active, more security-conscious, less file-based.

## Frameworks

### OpenClaw (ex-Clawdbot → Moltbot)
Steinberger; TS/Node ≥22; ~430k LOC; 247k stars; v2026.7.1-2 (4 Aug, hardening release). Gateway idles ~394–420MB/bot; issue #13758 documents 1.9GB RSS + 69.9% CPU after 13h (leaking 600s LLM timeouts, incomplete exec-session cleanup, unbounded Node heap). Docs: 2GB+ "recommended", practitioners say 4GB minimum; on 2GB the V8 heap ceiling causes OOM crashes. **Verdict: do not.**

### ZeroClaw
Rust, single static binary, zeroclaw-labs, 32.6k stars. Most active of the lightweight set: v0.8.4 (2 Aug), v0.8.3 (16 Jul, SOP engine + WASM plugin host), v0.8.2 (26 Jun, A2A). ~7–8MB RSS idle (marketing says <5MB; benchmarks desktop-normalized, not real Pi). Prebuilt aarch64/armv7/arm binaries. **Never build from source on Pi** — fat-LTO linker >7GB RSS. Security: supervised-by-default (medium-risk needs approval, high-risk blocked), workspace boundaries, cryptographic tool receipts, sub-agents can't escalate parent risk profile; 0.8.x closed SSRFs, constant-time token comparison. Memory SQLite+embeddings first; markdown/Postgres/Qdrant backends optional. SKILL.md/SKILL.toml with security audit at load. Cron as agent-scoped sub-agents (≥5min recommended). 30+ channels incl. Telegram.

### PicoClaw
**Sipeed**, Go single binary, launched 9 Feb 2026; ~30k stars; v0.3.1 (3 Jul) — docs changelog stale at v0.2.8, README at v0.2.9 (sloppy hygiene). Self-declared pre-1.0/not-production-ready; community maintainers recruited. README claims <10MB, admits recent builds 10–20MB. RISC-V/ARM/ARM64/MIPS/x86_64; field-tested on Pi Zero 2 W (512MB). Workspace: `AGENTS.md` (rules), `SOUL.md` (identity), `USER.md`, `MEMORY.md` (learned), `HEARTBEAT.md`, `memory/YYYY-MM-DD.md`, `sessions/`, `cron/` — system prompt assembled from markdown. Skills: `skills/<name>/SKILL.md` + YAML frontmatter, ClawHub install. Cron: `picoclaw cron add --cron "0 9 * * *"`; **gotcha: reminders fail silently without `"deliver": true` in cron/jobs.json**. Telegram via long polling (right call behind home NAT). Native Kimi (since v0.2.1), Qwen, OpenRouter + arbitrary OpenAI-compatible base URLs. SubTurn sub-agents (v0.2.4), MCP. `.security.yml`, cron gating, sensitive-data filtering. Real repo: `sipeed/picoclaw` (beware namesquats `Clawland-AI/picclaw`, `qidu/picoclaw`).

### Hermes Agent (Nous Research)
140k+ stars in 3 months; ~224B daily tokens via OpenRouter (May). Python 3.11 + Node 22 + ripgrep + ffmpeg. 2–4GB recommended; ≥2GB required with browser tools; **refuses models serving <64k context**. Marginal on 2GB — skip.

### NanoClaw
Gavriel Cohen / NanoCo; ~500-line TS core; per-agent Docker/MicroVM isolation; strongest security pitch. Disqualified: **Anthropic Claude Agent SDK-locked** (no OpenAI-compatible) + ~400MB + Docker daemon.

### TinyClaw → TinyAGI
Bash+TS multi-agent team orchestration; delegates execution to Claude Code/Codex CLI. Wrong shape for 2GB single personal agent.

### Nanobot (HKUDS)
~4,000 lines Python, ~9k stars, v0.1.4. Memory, web search, background sub-agents, Telegram/WhatsApp/Discord/Feishu; OpenRouter/OpenAI/Anthropic/DeepSeek/Gemini/Groq/vLLM/Ollama. **~191MB on a Pi** — fine in 2GB. The auditable middle ground; multiple writeups: best Pi option if comfortable with Python.

### nanoclaw-py (ApeCodeAI) — best roll-your-own template
~500 lines / 9 files: Claude Agent SDK + python-telegram-bot + APScheduler + SQLite. Single-user via OWNER_ID, file/bash/web tools, cron+interval+one-shot scheduling, CLAUDE.md long-term memory, daily archives. Swap Claude SDK for `openai` pointed at Moonshot/DashScope and it's exactly the described architecture.

## Comparison (2GB Pi 4B fit)

| | PicoClaw | ZeroClaw | Nanobot | Hermes | NanoClaw | OpenClaw | DIY |
|---|---|---|---|---|---|---|---|
| Runtime | Go binary | Rust binary | Python ~4k LOC | Py+Node | TS+Docker | Node ≥22 | Py ~500 LOC |
| Idle RAM | 10–20MB | 7–8MB | ~191MB | 300MB+ | 400MB+Docker | 394MB→1.9GB | 40–60MB |
| Fits 2GB? | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ✅ |
| OpenAI-compat | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Kimi/Qwen native | ✅/✅ | ✅/✅ | via OpenRouter | ✅ | ❌ | ✅ | ✅ |
| Telegram | ✅ long-poll | ✅ | ✅ | ✅ | ✅ | ✅ | trivial |
| MD skills | ✅ | ✅ (+audit) | partial | ✅ | limited | ✅ | DIY |
| MD persona/memory | ✅ full | partial (SQLite-first) | files | 3-layer | — | ✅ | DIY |
| Cron wake | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | APScheduler |
| Security | ok, pre-1.0 | **best** | small surface | mid | strongest-isolation | **weakest** | yours |

## Security context — OpenClaw incidents (why the ecosystem forked)

Jan 2026 Giskard exploit; 30k+ exposed instances / 135k+ IPs. CVE-2026-24763 (command injection), CVE-2026-26322 (SSRF), CVE-2026-26329 (path traversal), CVE-2026-30741 (prompt-injection RCE). Structural problem: indirect prompt injection — any text in front of the agent steers it; exposed instances leaked system prompts, tool configs, memory files, credentials. **Memory poisoning of SOUL.md/MEMORY.md demonstrated — applies to PicoClaw/ZeroClaw too** (same markdown-memory pattern). Moltbook breach (Feb): 1.5M API tokens. Aug state: CVEs patched but sandboxing still off by default, Gateway outside sandbox.

**Rules regardless of pick**: treat skills as executable code (Snyk: SKILL.md → shell access in 3 lines of markdown); never expose control port; allowlist own Telegram user ID; keys outside agent-readable workspace.

## Scheduled wake vs 24/7 — don't bother

Resident PicoClaw/ZeroClaw daemon costs 8–20MB (<1% of 2GB). Telegram long-polling needs a resident process anyway (webhooks need a public HTTPS endpoint — unwanted attack surface behind home NAT). Real cost is tokens (ZeroClaw warns cron <5min drives usage; 1–3/day is nothing). So: resident daemon + built-in cron, systemd `Restart=always` for supervision. Pi hygiene: disable bluetooth/avahi/cups, swap on USB SSD not SD, optional weekly off-hours reboot.

## Kimi & Qwen APIs (Aug 2026)

**Moonshot/Kimi** — K3 launched 16 Jul 2026; `https://api.moonshot.ai/v1`, OpenAI-compatible; 1M ctx. Per-1M pricing: K3 $3/$15 ($0.30 cached); K2.7-Code $0.95/$4; K2.6 $0.95/$4; **K2.5 $0.60/$3 ($0.10 cached) — sweet spot**. Function calling incl. `tool_choice:"required"`, streaming, structured output, vision; auto caching ~80–90% off cached input. Caveat: K3 reasoning-history/fixed-params/caching semantics need integration testing.

**Qwen/DashScope** — `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`, sk- key; qwen-plus/max/turbo. Qwen3.8-Max GA 3 Aug: $2/$6/$0.25-cached. Function calling, structured outputs, batches, prefix completion, server-side tools (code interpreter, web search). qwen-plus/turbo = sensible defaults, max via routing only.

Both on OpenRouter for single-key A/B.

## Framework vs roll-your-own

False binary at this size. Armin Ronacher's "Pi" post: minimal agent = shortest system prompt + 4 tools (Read/Write/Edit/Bash), no MCP; let the agent write its own extensions. Consensus: "agent that remembers and uses tools" ≈ a weekend in Python. But PicoClaw/ZeroClaw are ~10MB binaries adoptable in an hour and abandonable in an hour.

## Recommendation

**Primary: PicoClaw** (prebuilt ARM64) + **Kimi K2.5 or qwen-plus**. Accept: pre-1.0, sloppy release hygiene, partly community-maintained — acceptable when the failure mode is "no morning briefing".
**Strong alt: ZeroClaw** if weighting security/velocity over markdown-native workspace.
**Fallback: Nanobot or nanoclaw-py template** (swap Claude SDK → openai @ moonshot/dashscope).
**Avoid: OpenClaw, NanoClaw, Hermes, TinyAGI** on this hardware.
**Suggested path**: adopt PicoClaw, run 2 weeks against real workload, then decide if the 500-line DIY is worth writing.

## Sources

Key primary: github.com/sipeed/picoclaw · github.com/zeroclaw-labs/zeroclaw · github.com/HKUDS/nanobot · github.com/ApeCodeAI/nanoclaw-py · github.com/openclaw/openclaw (issue #13758) · docs.openclaw.ai/install/raspberry-pi · docs.zeroclawlabs.ai (raspberry-pi-setup, skills) · docs.picoclaw.io/docs/changelog · lucumr.pocoo.org/2026/1/31/pi/ (Ronacher) · snyk.io/articles/skill-md-shell-access/ · giskard.ai OpenClaw vulnerability writeup · CNBC 2026-02-02 Clawdbot→OpenClaw · therouter.ai Kimi K3 guide · benchlm.ai/moonshot/api-pricing · techjacksolutions.com Qwen API guide · ofox.ai Qwen3.8-Max pricing · itsfoss.com/openclaw-alternatives · thenewstack.io NanoClaw pieces · hermes-agent.org.
(Full URL list in original agent report; secondary comparison sites — clawbeat.co, lushbinary.com, openclawpulse.com etc. — are SEO-grade, treat as leads only.)
