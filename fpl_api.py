#!/usr/bin/env python3
"""
fpl_api.py - fetch, validate, and distill FPL API data. Stdlib-only (Pi-friendly).

Usage:
  python3 fpl_api.py fetch [--entry ID] [--out DIR]   # pull live API (Pi / direct network)
  python3 fpl_api.py distill RAW.json [--out DIR]     # distill staged raw bootstrap JSON
  python3 fpl_api.py diff OLD.json NEW.json           # compare two distilled snapshots
  python3 fpl_api.py selftest                         # offline sanity check
"""

import json, os, sys, time, urllib.request
from datetime import datetime, timezone

BASE = "https://fantasy.premierleague.com/api"
UA = {"User-Agent": "fpl-agent/0.1 (personal, non-commercial)"}

PLAYER_FIELDS = [
    "id", "web_name", "team", "element_type", "now_cost", "status", "news",
    "selected_by_percent", "form", "points_per_game", "total_points", "minutes",
    "goals_scored", "assists", "clean_sheets", "expected_goals",
    "expected_assists", "expected_goal_involvements", "ep_next",
    "chance_of_playing_next_round",
]
TEAM_FIELDS = ["id", "name", "short_name", "strength_attack_home",
               "strength_attack_away", "strength_defence_home", "strength_defence_away"]
EVENT_FIELDS = ["id", "name", "deadline_time", "finished", "is_current", "is_next"]
FIXTURE_FIELDS = ["id", "event", "team_h", "team_a", "team_h_difficulty",
                  "team_a_difficulty", "kickoff_time", "finished",
                  "team_h_score", "team_a_score"]


POS_BY_TYPE = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_squad_decision(picks_payload, bootstrap_snap, gw):
    """Turn a live /entry/{id}/event/{gw}/picks/ payload + a distilled bootstrap
    into the season_state.set_squad decision shape. Pure (no network) so it is
    unit-testable. Pick ids are the real FPL element ids (captain/vice reference
    them); bench_order 0..3 follows FPL positions 12..15; bank comes from the
    event's entry_history. Note: the public picks endpoint carries no per-pick
    purchase price, so set_squad banks the current price as bought_for."""
    players = {p["id"]: p for p in bootstrap_snap["players"]}
    clubs = {t["id"]: t["short_name"] for t in bootstrap_snap["teams"]}
    picks_out, captain, vice = [], None, None
    for pk in picks_payload["picks"]:
        el = players.get(pk["element"])
        if el is None:
            raise ValueError(f"element {pk['element']} not in bootstrap (stale snapshot?)")
        pos = pk.get("position")
        starting = pos is not None and pos <= 11
        picks_out.append({
            "id": el["id"],
            "name": el["web_name"],
            "pos": POS_BY_TYPE[el["element_type"]],
            "club": clubs.get(el["team"], "???"),
            "price": round(el["now_cost"] / 10.0, 1),
            "starting": starting,
            "bench_order": None if starting else pos - 12,
        })
        if pk.get("is_captain"):
            captain = el["id"]
        if pk.get("is_vice_captain"):
            vice = el["id"]
    decision = {"gw": gw, "captain": captain, "vice": vice, "picks": picks_out}
    bank = (picks_payload.get("entry_history") or {}).get("bank")
    if bank is not None:
        decision["bank"] = round(bank / 10.0, 1)
    return decision


def get(path, retries=2, timeout=20):
    url = BASE + path
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def health_bootstrap(raw):
    issues = []
    for key in ("elements", "teams", "events"):
        if key not in raw:
            issues.append(f"missing key {key}")
    n = len(raw.get("elements", []))
    if not 550 <= n <= 900:
        issues.append(f"suspicious player count: {n}")
    ev = len(raw.get("events", []))
    if ev != 38:
        issues.append(f"expected 38 events, got {ev}")
    return issues


def distill_bootstrap(raw):
    return {
        "kind": "bootstrap",
        "fetched_at": now_iso(),
        "health": health_bootstrap(raw),
        "players": [{k: p.get(k) for k in PLAYER_FIELDS} for p in raw.get("elements", [])],
        "teams": [{k: t.get(k) for k in TEAM_FIELDS} for t in raw.get("teams", [])],
        "events": [{k: e.get(k) for k in EVENT_FIELDS} for e in raw.get("events", [])],
    }


def distill_fixtures(raw):
    return {
        "kind": "fixtures",
        "fetched_at": now_iso(),
        "fixtures": [{k: f.get(k) for k in FIXTURE_FIELDS} for f in raw],
    }


def diff_snapshots(old, new):
    oldp = {p["id"]: p for p in old.get("players", [])}
    changes = []
    for p in new.get("players", []):
        o = oldp.get(p["id"])
        if not o:
            continue
        if p.get("now_cost") != o.get("now_cost"):
            changes.append({"id": p["id"], "name": p["web_name"], "type": "price",
                            "from": o.get("now_cost"), "to": p.get("now_cost")})
        if p.get("status") != o.get("status"):
            changes.append({"id": p["id"], "name": p["web_name"], "type": "status",
                            "from": o.get("status"), "to": p.get("status"),
                            "news": p.get("news")})
        try:
            d = float(p.get("selected_by_percent") or 0) - float(o.get("selected_by_percent") or 0)
        except ValueError:
            d = 0.0
        if abs(d) >= 0.5:
            changes.append({"id": p["id"], "name": p["web_name"], "type": "ownership",
                            "delta": round(d, 1)})
    return changes


def save(obj, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = os.path.join(out_dir, f"{prefix}-{stamp}.json")
    with open(path, "w") as f:
        json.dump(obj, f)
    print(f"saved {path} ({os.path.getsize(path)/1024:.0f} KB)")
    return path


def cmd_fetch(out_dir, entry_id=None):
    snap = distill_bootstrap(get("/bootstrap-static/"))
    for issue in snap["health"]:
        print(f"HEALTH: {issue}")
    save(snap, out_dir, "bootstrap")
    save(distill_fixtures(get("/fixtures/")), out_dir, "fixtures")
    if entry_id:
        entry = get(f"/entry/{entry_id}/")
        save({"kind": "entry", "fetched_at": now_iso(), "entry": entry}, out_dir, "entry")


def selftest():
    raw = {
        "elements": [{"id": i, "web_name": f"P{i}", "team": 1, "element_type": 3,
                      "now_cost": 100 + (i % 5), "status": "a",
                      "selected_by_percent": "5.0"} for i in range(1, 601)],
        "teams": [{"id": t, "name": f"T{t}", "short_name": f"T{t}"} for t in range(1, 21)],
        "events": [{"id": e, "name": f"GW{e}", "finished": False} for e in range(1, 39)],
    }
    assert health_bootstrap(raw) == [], "clean payload should have no issues"
    assert health_bootstrap({"elements": []}), "empty payload must be flagged"
    snap = distill_bootstrap(raw)
    assert len(snap["players"]) == 600 and len(snap["events"]) == 38
    snap2 = distill_bootstrap(raw)
    snap2["players"][0]["now_cost"] += 1
    snap2["players"][1]["status"] = "i"
    changes = diff_snapshots(snap, snap2)
    assert len(changes) == 2, f"expected 2 changes, got {len(changes)}"

    # build_squad_decision: live picks + distilled bootstrap -> set_squad decision shape
    bsnap = distill_bootstrap({
        "elements": [
            {"id": 10, "web_name": "Raya", "team": 1, "element_type": 1, "now_cost": 60},
            {"id": 11, "web_name": "Gabriel", "team": 1, "element_type": 2, "now_cost": 80},
            {"id": 12, "web_name": "Haaland", "team": 2, "element_type": 4, "now_cost": 155},
            {"id": 13, "web_name": "Palmer", "team": 3, "element_type": 1, "now_cost": 40},
        ],
        "teams": [{"id": 1, "short_name": "ARS"}, {"id": 2, "short_name": "MCI"},
                  {"id": 3, "short_name": "CHE"}],
        "events": [],
    })
    picks_payload = {
        "picks": [
            {"element": 10, "position": 1, "is_captain": False, "is_vice_captain": False},
            {"element": 11, "position": 2, "is_captain": False, "is_vice_captain": True},
            {"element": 12, "position": 3, "is_captain": True, "is_vice_captain": False},
            {"element": 13, "position": 12, "is_captain": False, "is_vice_captain": False},
        ],
        "entry_history": {"bank": 5},
    }
    dec = build_squad_decision(picks_payload, bsnap, gw=3)
    assert dec["gw"] == 3 and dec["captain"] == 12 and dec["vice"] == 11, dec
    assert dec["bank"] == 0.5, f"bank tenths->£m, got {dec['bank']}"
    by_id = {p["id"]: p for p in dec["picks"]}
    assert by_id[12] == {"id": 12, "name": "Haaland", "pos": "FWD", "club": "MCI",
                         "price": 15.5, "starting": True, "bench_order": None}, by_id[12]
    assert by_id[10]["club"] == "ARS" and by_id[10]["pos"] == "GKP"
    assert by_id[13]["starting"] is False and by_id[13]["bench_order"] == 0, "pos 12 -> bench 0"
    print("SELFTEST PASS: health / distill / diff / squad-pull all OK")


def write_csv(rows, path):
    if not rows:
        print(f"skip {path} (no rows)")
        return
    import csv
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def cmd_csv(snap_path, out_dir):
    with open(snap_path) as f:
        snap = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    if snap.get("kind") == "bootstrap":
        # Enforce the collector's health checks (player-count bounds, 38 events) before
        # the snapshot feeds projections/optimizer: refuse to emit CSVs from a bad fetch.
        issues = snap.get("health") or []
        if issues:
            for i in issues:
                print(f"HEALTH: {i}")
            sys.exit(f"health checks failed for {snap_path} "
                     f"({len(issues)} issue(s)) - refusing to emit CSVs")
        write_csv(snap.get("players", []), os.path.join(out_dir, "players.csv"))
        write_csv(snap.get("teams", []), os.path.join(out_dir, "teams.csv"))
        write_csv(snap.get("events", []), os.path.join(out_dir, "events.csv"))
        print("health: clean")
    elif snap.get("kind") == "fixtures":
        write_csv(snap.get("fixtures", []), os.path.join(out_dir, "fixtures.csv"))
    else:
        print(f"unknown kind: {snap.get('kind')}")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    if cmd == "selftest":
        selftest()
    elif cmd == "fetch":
        out = args[args.index("--out") + 1] if "--out" in args else "./fpl-data"
        entry = int(args[args.index("--entry") + 1]) if "--entry" in args else None
        cmd_fetch(out, entry)
    elif cmd == "distill":
        raw_path = args[1]
        out = args[args.index("--out") + 1] if "--out" in args else "./fpl-data"
        with open(raw_path) as f:
            save(distill_bootstrap(json.load(f)), out, "bootstrap")
    elif cmd == "csv":
        cmd_csv(args[1], args[args.index("--out") + 1] if "--out" in args else "./fpl-data")
    elif cmd == "diff":
        with open(args[1]) as f:
            old = json.load(f)
        with open(args[2]) as f:
            new = json.load(f)
        changes = diff_snapshots(old, new)
        print(json.dumps(changes, indent=2))
        print(f"{len(changes)} change(s)")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)
