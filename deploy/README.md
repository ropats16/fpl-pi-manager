# Deploy — FPL Gaffer walking skeleton (#15)

One-time bootstrap of the resident daemon on the Pi 4B, then it self-heals via
the pull timer. Implements the deferred install steps from
[`plans/repo-deploy.md`](../plans/repo-deploy.md) (#11) under the #10 security
posture. `main` is source of truth; the Pi runs `pi/live` and pulls.

## What the daemon does (this skeleton)

Long-polls Telegram → **numeric allowlist check in daemon core** (unknown sender
= silent drop + log, no reply) → one OpenRouter round-trip (Kimi K2.5) → replies.
Every wake, prompt and reply is a structured jsonl log line; secrets are redacted.
No FPL writes, no tools yet — those land in #16+.

## Verify offline first (any machine, no network, no secrets)

```sh
python3 -m daemon selftest      # drives one full message->reply loop, all edges faked
python3 -m unittest discover -s tests -v
```

## One-time Pi bootstrap

```sh
# 1. Dedicated unprivileged service user + clone (retire old saf@fplpi:~/fpl/)
sudo useradd --system --create-home --shell /usr/sbin/nologin gaffer
sudo git clone https://github.com/ropats16/fpl-pi-manager /opt/fpl-gaffer
sudo chown -R gaffer:gaffer /opt/fpl-gaffer

# 2. Runtime branch: pi/live off main (daemon-authored runtime paths live here)
sudo -u gaffer git -C /opt/fpl-gaffer checkout -b pi/live origin/main

# 3. Deps — stdlib-only daemon; pipeline needs pulp/cbc (see AGENTS.md)
sudo apt install -y python3 git python3-pulp coinor-cbc

# 4. Secrets: encrypt into the root-only credstore (never in the repo, never env)
sudo mkdir -p /etc/credstore.encrypted && sudo chmod 700 /etc/credstore.encrypted
printf '%s' 'PASTE_TELEGRAM_BOT_TOKEN' | sudo systemd-creds encrypt --name=telegram-token - /etc/credstore.encrypted/telegram-token
printf '%s' 'PASTE_OPENROUTER_API_KEY' | sudo systemd-creds encrypt --name=openrouter-key - /etc/credstore.encrypted/openrouter-key

# 5. Non-secret config outside the workspace (numeric allowlist + model)
sudo mkdir -p /etc/fpl-gaffer
sudo cp /opt/fpl-gaffer/deploy/gaffer.env.example /etc/fpl-gaffer/gaffer.env
sudo nano /etc/fpl-gaffer/gaffer.env      # set GAFFER_ALLOWLIST_USER_IDS

# 6. Least-privilege grant: gaffer may restart ONLY its own daemon (auto-reload)
sudo install -m 0440 -o root -g root \
  /opt/fpl-gaffer/deploy/sudoers-fpl-gaffer /etc/sudoers.d/fpl-gaffer
sudo visudo -cf /etc/sudoers.d/fpl-gaffer            # validate before trusting it

# 7. Install + enable the units (pull-reload.sh must stay executable)
chmod +x /opt/fpl-gaffer/deploy/pull-reload.sh
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer.service        /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-pull.service   /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-pull.timer     /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-watch.service  /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-watch.timer    /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-brief.service  /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-brief.timer    /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-review.service /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-review.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fpl-gaffer.service
sudo systemctl enable --now fpl-gaffer-pull.timer
sudo systemctl enable --now fpl-gaffer-watch.timer
sudo systemctl enable --now fpl-gaffer-brief.timer
sudo systemctl enable --now fpl-gaffer-review.timer
```

Add `github-token` and `fpl-cookie` credentials the same way (step 4) when the
auto-PR flow (#11 §4) and actuator (#13/#14) are provisioned; the daemon simply
has no such credential until then. The **5th credential, `odds-api-key`** (#54),
is optional the same way — only the fixtures/odds helper's fetch of
`api.the-odds-api.com` uses it, and without it that one fetch degrades to an
error text the helper reports as a coverage gap:

```sh
printf '%s' 'PASTE_ODDS_API_KEY' | sudo systemd-creds encrypt --name=odds-api-key - /etc/credstore.encrypted/odds-api-key
```

Then add `LoadCredentialEncrypted=odds-api-key:/etc/credstore.encrypted/odds-api-key`
to the units that run helpers once #56 wires the fan-out into the brief wake
(a `LoadCredentialEncrypted` line for a file that does not exist fails the unit,
so the line is not in the shipped units until the key is provisioned).

## Verify supervision (acceptance criteria)

```sh
# Live reply loop on the Pi: message the bot from the allowlisted account.
journalctl -u fpl-gaffer -f            # watch structured wake/reply lines

# Survives a kill (Restart=always brings it straight back):
sudo systemctl kill fpl-gaffer && sleep 8 && systemctl is-active fpl-gaffer   # -> active

# Survives a reboot (boot-start):
sudo reboot     # after boot: systemctl is-active fpl-gaffer  -> active

# Pull path works:
systemctl list-timers fpl-gaffer-pull.timer
sudo systemctl start fpl-gaffer-pull.service && journalctl -u fpl-gaffer-pull -n 20
```

## Price/status watch (#17)

`fpl-gaffer-watch.timer` wakes `python3 -m daemon watch` twice a day (03:10 UTC
post-price-change, 14:10 UTC evening news). Each wake fetches the FPL bootstrap,
health-checks it, diffs against `data/watch-baseline.json`, and Telegram-alerts
**only** when an own-squad or shortlisted player has a price or status change —
a quiet day sends nothing and spends zero tokens (no LLM in this path; the unit
loads only the telegram-token credential). Shortlist lives in
`agent/memory/shortlist.md`; squad ids come from `season-state.json`. The first
wake seeds the baseline silently.

```sh
systemctl list-timers fpl-gaffer-watch.timer
sudo systemctl start fpl-gaffer-watch.service     # force a wake now
journalctl -u fpl-gaffer-watch -n 20              # watch_wake / watch_quiet / watch_alert
```

## Deadline brief + approval (#18)

`fpl-gaffer-brief.timer` wakes `python3 -m daemon brief` **every 15 minutes**
(`*:05,20,35,50` — the 30-minute act window must catch a tick for *any* deadline
minute; an hourly tick misses it for `:00` deadlines). Each
wake is a cheap clock check against the next FPL deadline — outside a window it
logs `brief_quiet` and spends zero tokens. It opens the LLM path only in the
**draft** window (Rohit's IST evening / within 24h) and the **T−2h final**
window, and it **acts** at T−30m. Unlike the watch, the brief thinks, so this
unit loads **both** the `telegram-token` and the `openrouter-key` credentials.

The approval gate lives in daemon code, not model judgment: at T−30m the daemon
calls the actuator **only** on an explicit `yes` (state `approved`/`locked`); an
unapproved deadline is a loud no-write (last team stands, FT banks). Approval
state persists in `data/approval-state.json` (gitignored, shared with the reply
loop so a `yes` sent to the bot flips the same gate the brief wake reads). The
actuator is manual-apply only until the real FPL write path (#13/#14/#19) is
proven — an `act` produces "apply in the FPL app" steps and writes the decision
to `season-state.json` (`decisions.gwNN`), it never mutates an FPL team.

```sh
systemctl list-timers fpl-gaffer-brief.timer
sudo systemctl start fpl-gaffer-brief.service     # force a wake now
journalctl -u fpl-gaffer-brief -n 20              # brief_wake / brief_quiet / brief_draft_sent / brief_acted
```

## Post-GW review (#21)

`fpl-gaffer-review.timer` wakes `python3 -m daemon review` **~4-hourly**
(`02,06,10,14,18,22:25` UTC). Each wake is a cheap events check against the FPL
bootstrap: it looks for a gameweek that has newly **finished** (and had its bonus
`data_checked`), and only then spends LLM tokens — **once per settled GW**. Every
other tick logs `review_quiet` and sends nothing (bonus/`data_checked` can lag
the last whistle by hours, so it keeps checking rather than firing once). When a
GW settles it pulls the actuals, sets them against the **projection snapshot the
brief wake froze** for that GW (`data/projections-gwNN.csv`) and the recorded
decision, and grades the call — projections vs actuals, captain vs best-in-XI,
transfer nets, bench calls — entirely in **code** (the model never scores
itself). The gaffer then writes the luck-vs-process review + a `learnings` block,
which the daemon appends to `reports/gwNN/decision-log.md`. Like the brief it
thinks, so this unit loads **both** the `telegram-token` and the `openrouter-key`
credentials.

Review state persists in `data/review-state.json` (gitignored) — the last GW
reviewed, so a settled GW is graded exactly once and re-sends only if the
Telegram send failed. The entry (team) id used to pull the fielded picks comes
from `FPL_ENTRY_ID` in `gaffer.env` (public, non-secret); left unset the review
falls back to the season-state squad.

```sh
systemctl list-timers fpl-gaffer-review.timer
sudo systemctl start fpl-gaffer-review.service    # force a wake now
journalctl -u fpl-gaffer-review -n 20             # review_wake / review_quiet / review_sent
```

> The `review` units are **new**: the pull path only restarts the running daemon,
> it does not install units. So the one-time `cp` of
> `fpl-gaffer-review.{service,timer}` into `/etc/systemd/system/` plus
> `sudo systemctl enable --now fpl-gaffer-review.timer` must be run by hand on the
> Pi once (as in the bootstrap block above); thereafter it self-heals via the
> timer like the others.

## Helper tool loop (#54)

`python3 -m daemon helper <role> [--gw N]` runs one helper role (`availability`,
`fixtures`, `quality`, `market`, `scout`, `am`) as a bounded tool loop on its mapped
model and writes `agent/reports/gwNN/<role>.md` for the next FPL deadline's GW
(write-once — delete the file to re-run). No timer yet (#56/#57 wire it into the
draft wake and the daily Scout); to run one by hand on the Pi with the daemon's
config and credentials:

```sh
sudo systemd-run --uid=gaffer --gid=gaffer --pipe --wait --collect \
  -p WorkingDirectory=/opt/fpl-gaffer -p EnvironmentFile=/etc/fpl-gaffer/gaffer.env \
  -p LoadCredentialEncrypted=telegram-token:/etc/credstore.encrypted/telegram-token \
  -p LoadCredentialEncrypted=openrouter-key:/etc/credstore.encrypted/openrouter-key \
  /usr/bin/python3 -m daemon helper availability
# -> jsonl events (llm_call with tokens + cost, fetch / fetch_refused / search,
#    cap_hit, report_written) then one `helper: role=… status=… report=… cost=$…` line
```

Ceilings and the model map are `gaffer.env` overrides (`GAFFER_HELPER_MAX_*`,
`GAFFER_HELPER_MODEL`, `GAFFER_AM_MODEL`, `GAFFER_FETCH_ALLOWLIST`,
`GAFFER_PRICE_TABLE`) — see `gaffer.env.example`; defaults are the #51 decisions.

## Applying updates (self-test-gated auto-reload)

Merge a PR to `main` → within ~15 min the pull timer lands it on `pi/live` and
`pull-reload.sh` decides what to do — **no manual SSH for routine changes**:

- **Markdown / data / squad** (no `*.py` changed) → applies on the next wake, no
  restart (the assembler reads `agent/*.md`, `season-state.json`,
  `data/projections.csv` fresh each message, #16). The pull exits quietly.
- **Code** (`*.py` changed) → the script runs `python3 -m daemon selftest` on the
  freshly-pulled code first:
  - **selftest passes** → `sudo systemctl restart fpl-gaffer` (via the narrow
    sudoers grant) and Telegram gets `✅ Deployed — <PR/commit link>`.
  - **selftest fails** → **no restart**; the daemon keeps running the last-good
    version and Telegram gets `⛔ Deploy blocked — <link>` (log at
    `/tmp/gaffer-deploy-selftest.log`). A bad merge can't take the gaffer down.

So the pull path is the deploy path: a green PR reaches the *running* daemon
hands-off, and only a self-test-clean build ever restarts it. `Restart=always`
still covers crash-recovery independently. To force a deploy now rather than wait
for the timer: `sudo systemctl start fpl-gaffer-pull.service`.
