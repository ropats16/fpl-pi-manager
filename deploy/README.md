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

# 6. Install + enable the two units
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer.service        /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-pull.service   /etc/systemd/system/
sudo cp /opt/fpl-gaffer/deploy/fpl-gaffer-pull.timer     /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fpl-gaffer.service
sudo systemctl enable --now fpl-gaffer-pull.timer
```

Add `github-token` and `fpl-cookie` credentials the same way (step 4) when the
auto-PR flow (#11 §4) and actuator (#13/#14) are provisioned; the daemon simply
has no such credential until then.

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

## Applying updates

Merge a PR to `main` → the pull timer lands it on `pi/live` within ~15 min.
Markdown (persona/rulebook) applies next wake, no restart; **daemon/pipeline code
changes need a restart** — the daemon self-exits to reload and `Restart=always`
brings it back on the new code. Crash-recovery is therefore free: the next
restart after a fix lands self-heals, no privileged `systemctl restart`.
