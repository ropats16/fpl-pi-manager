"""Scheduled price/status watch (#17) — deterministic, no model in the loop.

The systemd timer wakes this 2x/day: fetch bootstrap, health-check it, diff
against the last baseline snapshot, and Telegram-alert ONLY when a player Rohit
owns (season-state squad) or is tracking (agent/memory/shortlist.md) moves on
price or availability. Everything else — other players, ownership drift, a
clean day — is silence.

Silence is the default for two reasons. Cost: the diff is plain Python, so a
quiet day spends zero tokens and never opens the LLM path (the unit ships only
the telegram-token credential, least privilege per #10 §3). Signal: an alert
that fires for players he does not care about trains him to ignore alerts.

The baseline advances only on a wake that fully succeeded. A failed fetch, a
health-check failure, or a failed send all leave it in place, so the next wake
re-diffs the same window — a missed alert is recoverable, a lost one is not.
"""

import json
import os

import fpl_api

# FPL availability letters, expanded for a phone screen.
STATUS_NAMES = {"a": "available", "d": "doubtful", "i": "injured",
                "s": "suspended", "u": "unavailable", "n": "not in squad"}


def parse_shortlist(text):
    """Player web_names from the markdown shortlist, lowercased for matching.
    One name per line; `-`/`*` bullets optional, blank and full-line `#`
    comments ignored. Deliberately dumb — this file is gaffer-writable (tier 3),
    so it may only ever widen a notification set, never do anything else."""
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.lstrip("-*").strip()
        if name:
            names.add(name.lower())
    return names


def _read(path):
    with open(path, "r") as f:
        return f.read()


def load_watch_targets(state_path, shortlist_path, logger=None):
    """(squad element ids, shortlisted lowercased names). A missing or malformed
    file yields an empty set for that source rather than raising — a broken
    shortlist must degrade the watch to squad-only, never kill the wake — but
    the degradation is logged: a blind squad watch that looks like a quiet day
    would silently void the "alert on my players" guarantee (#17)."""
    ids = set()
    try:
        state = json.loads(_read(state_path))
        for pick in state.get("squad", {}).get("picks", []) or []:
            pid = pick.get("id")
            if isinstance(pid, int):
                ids.add(pid)
    except Exception as e:               # noqa: BLE001 — see docstring
        ids = set()
        if logger:
            logger.event("watch_targets_degraded", source="state",
                         error=type(e).__name__, detail=str(e))
    try:
        names = parse_shortlist(_read(shortlist_path))
    except Exception as e:               # noqa: BLE001 — see docstring
        names = set()
        if logger:
            logger.event("watch_targets_degraded", source="shortlist",
                         error=type(e).__name__, detail=str(e))
    return ids, names


def relevant_changes(changes, ids, names):
    """Price/status moves on watched players only. Ownership drift is never
    alertable — it is analysis input, not a thing to wake a phone for."""
    return [c for c in changes
            if c.get("type") in ("price", "status")
            and (c.get("id") in ids or str(c.get("name", "")).lower() in names)]


def _money(tenths):
    return f"£{(tenths or 0) / 10.0:.1f}"


def _status(letter):
    return STATUS_NAMES.get(letter, str(letter))


def format_alert(changes):
    """Lean phone-readable text: a count header, then one line per change."""
    lines = [f"🔔 GW watch — {len(changes)} change(s)"]
    for c in changes:
        if c["type"] == "price":
            lines.append(f"💰 {c['name']} {_money(c['from'])} → {_money(c['to'])}")
        else:
            line = f"🩹 {c['name']}: {_status(c['from'])} → {_status(c['to'])}"
            news = (c.get("news") or "").strip()
            lines.append(f"{line} — {news}" if news else line)
    return "\n".join(lines)


def _write_baseline(path, snap):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(snap, f)


def run_watch(fetch, state_path, shortlist_path, baseline_path, telegram,
              allowlist, logger):
    """One wake. Returns a process exit code (0 ok, 1 the wake did not complete).

    `fetch` is injected so the whole path runs offline in tests — same seam
    posture as daemon.http.Transport (#7: own the HTTP edges)."""
    logger.event("watch_wake")
    try:
        snap = fetch()
    except Exception as e:               # noqa: BLE001 — a bad wake must not crash the timer
        logger.event("watch_error", error=type(e).__name__, detail=str(e))
        return 1

    issues = snap.get("health") or []
    if issues:
        # Suspect payload: alerting off it could fake an injury. Keep the
        # baseline so the next wake diffs against known-good data.
        logger.event("watch_health_fail", issues=issues)
        return 1

    if not os.path.exists(baseline_path):
        _write_baseline(baseline_path, snap)
        logger.event("watch_baseline_seeded", players=len(snap.get("players", [])))
        return 0

    with open(baseline_path, "r") as f:
        baseline = json.load(f)
    changes = fpl_api.diff_snapshots(baseline, snap)
    ids, names = load_watch_targets(state_path, shortlist_path, logger=logger)
    relevant = relevant_changes(changes, ids, names)

    # Target counts on every diff wake: "quiet because nothing moved" and
    # "quiet because the watch is blind" must be distinguishable in the journal.
    targets = {"squad_ids": len(ids), "shortlist": len(names)}
    if not relevant:
        logger.event("watch_quiet", total_changes=len(changes), relevant=0,
                     **targets)
        _write_baseline(baseline_path, snap)
        return 0

    text = format_alert(relevant)
    logger.event("watch_alert", relevant=len(relevant),
                 total_changes=len(changes), changes=relevant, **targets)
    for chat_id in sorted(allowlist):
        try:
            telegram.send_message(chat_id=chat_id, text=text)
        except Exception as e:           # noqa: BLE001 — see below
            # Baseline stays put so the next wake re-alerts. Better a duplicate
            # than a price move Rohit never hears about.
            logger.event("watch_send_error", chat_id=chat_id,
                         error=type(e).__name__, detail=str(e))
            return 1
    _write_baseline(baseline_path, snap)
    return 0
