#!/usr/bin/env bash
#
# pull-reload.sh — the pull half of continuous deploy, with a self-test gate.
#
# Run by fpl-gaffer-pull.service (as gaffer, every 15 min + on boot). It:
#   1. pulls main -> pi/live (the merge auto-resolves; path-sets are disjoint, #11)
#   2. if the pull changed tracked *.py, gates a daemon restart behind the offline
#      `daemon selftest` on the NEW code — so a broken merge can't take down the
#      live gaffer; it keeps running the last-good version instead
#   3. pushes a Telegram deploy / blocked notice (with the PR/commit link)
#
# Markdown / data / squad changes need no restart — the assembler reads them fresh
# each wake (#16) — so a pull that touched no *.py exits quietly after the merge.
#
# Restarting a system unit as the gaffer user needs the least-privilege sudoers
# grant in deploy/sudoers-fpl-gaffer.  (#deploy-auto-reload)

set -uo pipefail

REPO="${GAFFER_REPO_DIR:-/opt/fpl-gaffer}"
SERVICE="fpl-gaffer.service"

cd "$REPO" || { echo "pull-reload: cannot cd $REPO" >&2; exit 1; }

old="$(git rev-parse HEAD)"
git fetch origin || { echo "pull-reload: fetch failed" >&2; exit 1; }
git merge -m "pull: main -> pi/live" origin/main || {
    echo "pull-reload: merge failed (manual resolve needed)" >&2; exit 1; }
new="$(git rev-parse HEAD)"

[ "$old" = "$new" ] && exit 0            # nothing pulled

# Link to what just landed. The pi/live HEAD is the local MERGE commit
# ("pull: main -> pi/live"), which carries no PR number — so read the merged-in
# side, origin/main, whose squash-merge subject holds "(#NN)". Fall back to that
# commit's sha (not the local merge commit). Repo slug from the origin remote.
slug="$(git remote get-url origin 2>/dev/null \
        | sed -E 's#^git@github\.com:##; s#^https://github\.com/##; s#\.git$##')"
base="https://github.com/${slug:-ropats16/fpl-pi-manager}"
main_tip="$(git rev-parse origin/main)"
# Newest PR number across everything merged this pull ($old..origin/main); git log
# is newest-first so head -1 is the latest. Fall back to the origin/main tip sha,
# which (unlike the local pi/live merge) is pushed to GitHub and so resolves.
pr="$(git log --format='%s' "$old..origin/main" | grep -oE '#[0-9]+' | head -1 | tr -d '#')"
if [ -n "$pr" ]; then link="$base/pull/$pr"; else link="$base/commit/$main_tip"; fi

# Only *.py changes need a process restart; anything else applies live.
if [ -z "$(git diff --name-only "$old" "$new" -- '*.py')" ]; then
    echo "pull-reload: no *.py change; applies live, no restart" >&2
    exit 0
fi

# Gate the restart on the offline selftest run against the freshly-pulled code.
# Each outcome is echoed to stderr (journald) too, so there's an audit trail even
# if Telegram is unreachable.
if ! python3 -m daemon selftest >/tmp/gaffer-deploy-selftest.log 2>&1; then
    echo "pull-reload: BLOCKED — selftest failed for $link; not restarting" >&2
    python3 -m daemon notify "⛔ Deploy blocked — $link failed the offline selftest; still running the previous version. Log: /tmp/gaffer-deploy-selftest.log" || true
    exit 0
fi

# selftest clean -> restart. Note the restart status on its own, so a flaky
# notice can never masquerade as a failed restart (or vice versa).
if sudo -n /usr/bin/systemctl restart "$SERVICE"; then
    echo "pull-reload: DEPLOYED $link — selftest passed, gaffer restarted" >&2
    python3 -m daemon notify "✅ Deployed — $link (selftest passed, gaffer restarted)" || true
else
    echo "pull-reload: restart FAILED after clean selftest for $link" >&2
    python3 -m daemon notify "⚠️ Deployed $link but the restart command failed — check the Pi." || true
fi
