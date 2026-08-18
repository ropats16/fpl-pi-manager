# Security Hardening — locked posture (#10)

Grilling session 2026-08-18 ([issue #10](https://github.com/ropats16/fpl-pi-manager/issues/10)). Maps every standing security rule to a concrete mechanism on the locked runtime (#7 DIY Python daemon, systemd, Pi 4B). This page is the build spec for the security surface of #15/#16/#17; the [map](map.md) bullet is the summary.

**Threat model in one line:** the model WILL be injected (K2-family ~95% poisonable) — so every guarantee lives in plumbing the model can't edit, never in prompts. With this posture, a fully injected gaffer can at worst produce bad advice and dirty files in allowed paths — never code execution, secret theft, or silent team changes.

## 1. Tool surface — fixed registry, no autonomous exec

- The gaffer gets ONLY hand-written Python tools (FPL fetch, path-ACL'd read/write, optimizer run, Telegram send, gated actuator). **No shell/exec/eval tool. Ever.** Maths pipeline runs as daemon code, not model-invoked shell.
- **Escape hatch = `propose_command`:** gaffer sends the exact command to Rohit on Telegram; runs only on explicit "yes"; executed via `systemd-run` sandbox — no network, workspace-only mount, timeout, memory cap. Rule for Rohit: never approve a command you don't understand — the justification is exactly what an injection would fake.
- **Per-wake LLM call/token cap** in the daemon loop (injection can't spin a token-burn loop; also guards the $5/mo ceiling).
- Knob-tuning (weights/thresholds) lives in gaffer-writable parameter files (markdown/JSON) behind the tier-2 gate — no exec needed for routine tuning. "Config" the *daemon* reads (allowlist, ACL, jobs) is tier 1, never model-writable.

## 2. Telegram — numeric-ID allowlist in daemon core

- Daemon compares `message.from.id` to Rohit's **numeric** user ID (never `@username` — changeable/re-registrable) **before any text reaches the model**.
- Check lives in the immutable core (daemon code); the ID sits in Pi-side config outside every gaffer-writable path (a poisoned gaffer must not widen its own allowlist).
- Unknown sender → **silent drop + log line** (no reply — replying confirms a live bot).
- Accept only plain messages from the 1:1 chat; ignore group/channel/edited/inline update types.

## 3. Secrets — encrypted, process-only, never in context

Extends #8's LoadCredential lock with the exact hardening:

- `systemd-creds encrypt` → `/etc/credstore.encrypted/`, root:root 0600, loaded via `LoadCredentialEncrypted=`. No TPM on Pi: host key in `/var/lib/systemd/` (root 0400) — defends the pulled/cloned/backed-up SD card, not root compromise. Accepted.
- Daemon runs as a **dedicated unprivileged service user** (not `saf`); secrets surface only in `$CREDENTIALS_DIRECTORY` (service-private tmpfs, gone on stop), never env — kills the `/proc/<pid>/environ` leak.
- Secrets read at startup into client objects only; **log-redaction guard on all three values is a test-asserted invariant** (#16 AC).
- Rotation = manual via root-only `set-secret.sh` (SSH in, paste, re-encrypt, restart). Keys revocable from dashboards in seconds.
- **FPL cookie unprovisioned until the actuator is proven** (#13/#14): highest-value secret (real account session); until then the daemon simply has no third credential. Refresh = same script.

## 4. Write policy — five tiers, ACL in daemon code

Enforced by the write tool checking (role, path) — never by prompt. Nothing model-writable is executable or daemon-read config (security machinery): poisoning can bias judgment but can't alter mechanism.

| Tier | Paths | Who writes | Gate |
|---|---|---|---|
| 1 Core | daemon loop, tool registry, write-ACL, allowlist, approval gates, credential loading | Rohit only, via git (Mac → Pi pulls) | dev flow; gaffer may write a *proposal* |
| 1.5 Instruments | maths pipeline `.py` (optimizer, projections, fpl_api…) | gaffer, gated | candidate diff → offline selftest in the §1 sandbox → diff + test result to Telegram → Rohit "yes" → applied + git-committed |
| 2 Rulebook | `GAFFER.md`, `roles/*.md`, `playbooks/` | gaffer, gated | propose → Rohit Telegram "yes" **before** write (#9 reaffirmed) |
| 3 Diary | `memory/` + wiki | gaffer only | free, but distilled-words-only + provenance citation; auto git-commit per wake (role+wake in message); post-hoc diff review; one-command revert |
| 4 Inbox | `reports/gwNN/` | each analyst → own file only | write-once; **untrusted forever** — read as evidence, never instructions |

**Tier-3 exception (locked in #9, unchanged here):** the gaffer's *override rulebook* self-amends **without** Rohit — its gate is #9's own machinery (3 scored precedents + AM adversarial review + next-GW activation), git-committed like all tier-3 writes; the ACL gives that one path a rulebook-specific rule. The immutable core it cannot touch stays tier 1.

Poisoning mitigations riding on the tiers:
- **No verbatim persistence of untrusted content:** fetched web text lands only in tier 4 with source stamps; memory holds the gaffer's distillations. Analysts can't write to memory at all, so a poisoned fetch can't self-install.
- Prompt assembly wraps reports in delimiters marked "data, not instructions" (cuts injection rates; costs nothing; not relied upon alone).
- Every model-originated write = one git commit → audit trail + revert (GitHub as last-resort restore).
- Post-GW review + AM challenge double as poisoning *detection* (weird memory = flagged).
- Rohit pastes third-party text on Telegram → treated as tier-4 data, not instruction.

**Skills:** no runtime skill install, no ClawHub, no third-party SKILL.md ever. `playbooks/` are repo-committed and reach the Pi only via git pull — "skills = executable code" reduces to tier 2 + repo review.

**Model choice is decoupled:** injection resistance becomes an A/B criterion on the OpenRouter per-call seam (#8), not a re-decision here — the plumbing assumes the model is fooled.

## 5. Web fetch — allowlist with a self-extending gate

- **Domain allowlist in daemon config**, seeded from the [#24 data-sources page](research/team-selection/sources/data-sources.md) (official FPL API, odds, Understat, vetted news).
- Non-listed domain → blocked + logged; gaffer may **propose an addition via Telegram** (domain + one-line why → Rohit "yes" → permanent). Scout breadth grows organically, then stabilizes.
- **GET-only** (POST *is* exfil — the system's only internet writes are Telegram-to-Rohit and the gated actuator), response-size caps, timeouts.
- Fetched text keeps tier-4 treatment. Residual accepted: exfil-via-query-params to allowlisted sites — context holds no secrets (§3), loot is FPL chatter.

## 6. Host + process hygiene

- **Zero inbound surface:** Telegram long-poll, outbound-only; no webhook, no control port, nothing listening. `ufw` default-deny inbound; SSH from LAN only, key-auth only (password auth off).
- **systemd unit sandboxing:** `NoNewPrivileges=yes`, `ProtectSystem=strict` + `ReadWritePaths=` workspace only, `ProtectHome=yes`, `PrivateTmp=yes`, `RestrictAddressFamilies=AF_INET AF_INET6`, `CapabilityBoundingSet=` (empty), `MemoryMax=` (runaway daemon can't OOM the 2GB Pi). Defense-in-depth under the tool registry.
- **Avahi stays** (deviation from claw-research hygiene list — killing it breaks `fplpi.local`); bluetooth/cups disabled; HDMI/LEDs off for the watt.
- `unattended-upgrades` on; optional weekly off-hours reboot.

## 7. Availability — 24/7 reaffirmed + power-cut fail-safe

Power windows rejected (idle ≈ 2.2–2.6 kWh/mo ≈ ₹15–25; a forgotten power-on silently missing a GW lock is the worst failure mode in the system). Mechanisms:

- **Boot = resume:** Pi auto-boots on power restore; systemd starts daemon; `Restart=always` for crashes. Nothing manual.
- **Atomic state writes:** `season-state.json` etc. via tmp → fsync → rename; power cut mid-write leaves the old good file. Workspace git-committed → replay-since-last-commit worst case.
- **Catch-up on boot:** heartbeat + last-completed-wake record; on startup run missed-but-still-relevant wakes (stale Scout run), skip obsolete ones.
- **Deadline guard:** on boot, if a GW lock window is open and not done → run immediately + Telegram Rohit. The one wake that must never be lost.
- **SD-card protection** (the real Pi power-cut killer): journaled fs, minimal write volume, git push as off-box backup.
- **"safe to unplug?" Telegram command:** daemon answers from the jobs config ("clear until tomorrow 09:45 IST" / "NO — GW lock in 4h"). Week-one post-GW review adds observed wake durations to make windows empirical.

## Deferred / handed off

- Exact deploy layout, service-user name, Pi-pull cadence → #11.
- Prompt-assembler delimiter format, ACL implementation, redaction tests, call-cap values → #16 (build), #15 (skeleton).
- Approval-protocol UX (message formats for propose_command / tier-2 diffs / actuator) → #12.
- FPL-cookie provisioning → #13/#14.
