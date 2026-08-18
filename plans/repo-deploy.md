# Repo Layout + Pi Deploy + Supervision — locked (#11)

Grilling session 2026-08-19 ([issue #11](https://github.com/ropats16/fpl-pi-manager/issues/11)). Makes concrete the "repo is source of truth, Pi pulls" flow: the final committed tree, the two-way git flow, the pull mechanism, and systemd supervision — on the locked runtime (#7 DIY Python daemon, systemd, Pi 4B) under the locked security posture (#10). This page is the deploy/supervision build spec for #15/#16; the [map](map.md) bullet is the summary.

**Governance in one line:** Rohit is the club owner — owns the tier-1 core engine (only he changes it), approves the gaffer's per-GW performance review, and breeze-merges the gaffer's proposed rule/code PRs; the gaffer runs day-to-day, keeps auditable minutes, and can never touch its own guardrails or act on the team without a Telegram "yes".

## 1. Final tree — organized by who writes each path

The [#10 write-tiers](security-hardening.md) map 1:1 onto directories, so the ACL becomes clean path-prefix rules:

```
fpl-pi-manager/
├── daemon/       # TIER 1 core — loop · tools/ · jobs.yaml · write-ACL · Telegram
│   │             #   allowlist · approval gates · credential loading. Rohit-only via git.
│   └── tools/    #   hand-written tool registry (no exec/shell/eval tool, ever)
├── pipeline/     # TIER 1.5 instruments — fpl_api / fpl_projections / fpl_optimizer /
│                 #   season_state  (moved out of root — the one refactor this locks)
├── agent/        # gaffer workspace
│   ├── GAFFER.md · roles/ · playbooks/   # TIER 2 rulebook
│   ├── memory/        # TIER 3 diary — MEMORY.md + LLM-wiki   ┐ pi/live-authored,
│   └── reports/gwNN/  # TIER 4 inbox — write-once, untrusted   ┘ backed up off-box
├── state/season-state.json               # runtime state (write-back invariant)  ┘
├── deploy/       # systemd unit files + install/pull scripts
├── fixtures/     # committed offline-seam fixtures (unchanged)
├── data/         # gitignored working data (unchanged)
├── docs/  plans/ # existing
└── run_pipeline.sh  .env.example
```

- **`pipeline/` move** (four `.py` out of root) is the one code change this decision forces — it makes the tier-1.5 ACL a path-prefix rule and de-clutters root. Touches `run_pipeline.sh` + the `season_state.py` invocations in the README; **#4's green pipeline is re-verified after the move.**
- **Committed vs gitignored:** `state/`, `agent/memory/`, `agent/reports/` are **committed** — they are exactly what #10's off-box backup, "replay-since-last-commit", audit trail, and one-command revert rely on. `data/` stays gitignored. `main` ships these three once as **seed**, then never touches them again.
- **Filesystem vs ACL (clarification):** tier-1 protection is the **app-level write-ACL in daemon code** (#10 §4), *not* filesystem read-only. The clone is filesystem-writable by the `gaffer` user so the pull can update code; the *model's* tools still cannot write tier-1. The pull process (same user, not the model) is what updates code files.

## 2. Two branches — a path-disjoint split so merges never conflict

Git flows **both ways**: Rohit authors tier-1/1.5/2 code+rulebook; the daemon writes runtime state/memory/reports every wake. The split keeps them apart:

| Branch | Author | Owns (exclusive write) |
|---|---|---|
| `main` | Rohit (PRs) + gaffer (breezed PRs) | `daemon/` · `pipeline/` · `agent/GAFFER.md` · `agent/roles/` · `agent/playbooks/` · `docs/` · `plans/` · `fixtures/` |
| `pi/live` | daemon only | `state/` · `agent/memory/` · `agent/reports/` |

Because the two path-sets are **disjoint**, `git merge origin/main` into `pi/live` always auto-resolves — the daemon never edits an authored file, `main` never edits a runtime file. `main` stays the clean, human-curated source of truth; `pi/live` = live brain + minutes + off-box backup.

- **~500 diary commits, distilled:** the daemon auto-commits every wake (audit + revert + poisoning-detection + replay). Fine-grained commits only earn their keep *while a GW is live*; once the **post-GW self-review** clears the week as benign, the daemon **squash-compacts that GW's wake commits into one summary commit** (force-push to `pi/live` is safe — Pi-only branch). Net: ~one commit per reviewed GW + the current live window — dozens, not hundreds.
- **Findings reach `main` two ways, never by bulk merge:** (a) code/rulebook via the PR flow (§4); (b) durable memory learnings only when the gaffer encodes them as a tier-2 rulebook PR. Raw diary/reports stay on `pi/live` as audit — the firehose is never dumped on `main`.

## 3. Pull (main → Pi) — outbound-only, independent timer

- **Trigger = poll, outbound-only.** #10 locked zero inbound surface, so no push-webhook. The Pi pulls: `git fetch origin && git merge origin/main` into `pi/live`.
- **Mechanism = independent 15-min timer + on-boot** (a `deploy/`-owned oneshot, `User=gaffer`), *not* a daemon job. Strictly better than pulling inside the daemon: a breezed PR is live within ~15 min, git stays out of the tier-1 core, and it doubles as the crash-recovery path (below).
- **Applying a change:** rulebook/persona/playbook markdown is picked up **next wake, no restart** (context assembled from markdown at runtime, #7). Daemon/pipeline **code** changes need a process restart — a healthy daemon self-exits to reload; `Restart=always` brings it back on the new code.

## 4. Gaffer → main — auto-PR, no-merge token

When the gaffer has a vetted rule/param/code improvement:

1. It writes the change on a fresh **`gaffer/<slug>` branch off `origin/main`** — *not* on `pi/live` (keeps the runtime branch free of authored-path edits).
2. The daemon **auto-opens a PR via `gh`** and Telegram-pings Rohit the link.
3. Rohit **breeze-reviews + merges**; the pull timer (§3) lands it on `pi/live`.

- **4th secret = a GitHub token**, riding #10's secret machinery (`LoadCredentialEncrypted`, process-only, never in model context). **Scope = PR-create + push to `gaffer/*` on this repo only, no merge rights.** Even a fully poisoned gaffer can at most open a PR Rohit rejects — it can never merge to `main`. Same token does the `pi/live` backup push (HTTPS) — one credential, no separate deploy key.
- **Governance the flow serves:** the per-GW **decision-log review** (each decision + points it earned) is posted to Telegram for Rohit's approval; its evidence is the per-wake minutes (§2). Tier-1 core + the transfer-approval gate ("no FPL write without a Telegram yes") remain **Rohit-only, immutable** — the gaffer proposes knowledge/rules, never rewrites its own guardrails or acts on the team unattended.

## 5. Supervision — two unprivileged units

`User=gaffer` (dedicated unprivileged service user, **not `saf`**), clone at `/opt/fpl-gaffer`.

**`fpl-gaffer.service`** — the resident daemon:
- `Restart=always`, **`StartLimitIntervalSec=0`** (a crash-loop keeps cycling until the 15-min pull lands a fix — else systemd gives up and the fix never applies), `WorkingDirectory=/opt/fpl-gaffer`.
- #10 §6 hardening (locked there, assembled here): `NoNewPrivileges=yes`, `ProtectSystem=strict` + `ReadWritePaths=/opt/fpl-gaffer`, `ProtectHome=yes`, `PrivateTmp=yes`, `RestrictAddressFamilies=AF_INET AF_INET6`, `CapabilityBoundingSet=` (empty), `MemoryMax=`.
- `LoadCredentialEncrypted=` for the four secrets (OpenRouter key, Telegram token, GitHub token, FPL cookie when provisioned) → service-private tmpfs `$CREDENTIALS_DIRECTORY`, never env.
- Self-schedules wakes from `jobs.yaml`; long-polls Telegram (wake-on-message).

**`fpl-gaffer-pull.timer` + `fpl-gaffer-pull.service`** — a tiny unprivileged `gaffer` oneshot, `OnBootSec=` + `OnUnitActiveSec=15min`: `git fetch && git merge origin/main` into `pi/live`. That is the whole job.

**Crash-recovery = free.** The daemon reads its code fresh on every start, and `Restart=always` is already cycling a crashed process. The moment the pull lands Rohit's fix on disk, the **next automatic restart heals** — no privileged `systemctl restart`, no root. The pull service only has to get the fix onto the disk.

## Deferred / handed off

- Install/bootstrap steps (fresh clone at `/opt/fpl-gaffer`, retire old `saf@fplpi:~/fpl/`, `systemd-creds encrypt` the four secrets, `systemctl enable` the units, create `pi/live` off `main`, apt deps) → build ticket #15.
- `jobs.yaml` schema + the self-exit-on-code-change detection → #15/#16. Schedule *times* are unchanged from #9 (Scout 10:00 IST, analysts T−72h, lock T−30..15m, post-GW T+24h, monthly) — just encoded here.
- Decision-log / performance-review message format, approval-protocol UX → #12.
- Compaction squash implementation (post-GW hook) → #16 (rides the post-GW self-review wake).
- FPL-cookie provisioning → #13/#14.
