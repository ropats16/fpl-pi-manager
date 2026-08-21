#!/usr/bin/env python3
"""
fpl_projections.py -- expected points per player per gameweek (v1).

Reads:   data/players.csv, data/fixtures.csv  (produced by fpl_api.py)
Writes:  data/projections.csv                 (long format: player x gameweek)

v1.1 recipe (all tunables at top):
  base_rate  = blend of last-season pts/90 and FPL ep_next (weights by minutes)
  xmins      = last-season minutes share (proxy for nailedness)
  fixture    = FDR multiplier (position-specific) + home edge
  status     = availability haircut (a/d/i/s/u)
  horizon    = mild decay over next N gameweeks (trust history less further out)

Minutes-floor (v1.1): a player with fewer than MIN_MINUTES_FOR_HISTORY senior
minutes has no history to trust, so minutes_share() floors them to 0 and they
project 0 -- even with a positive ep_next. New signings / youth are gated out
here on purpose; a later news/minutes layer re-adds them.

Cold start (v1.2): at a season boundary almost nobody has crossed the minutes
floor yet, so that gate would zero the WHOLE league. is_cold_start() detects the
league-wide case and available players fall back to FPL's own ep_next (already
minutes-aware) instead of projecting 0. Mid-season new-signing gating is
unaffected, since then most of the pool is over the floor.

Not in v1: Understat blend, betting odds, press-conference news, learned minutes.

Usage:
  python3 fpl_projections.py                 # reads data/, writes data/projections.csv
  python3 fpl_projections.py selftest        # offline sanity check (no files needed)
"""

import csv, json, math, sys
from pathlib import Path
from collections import defaultdict

DATA = Path("data")
HORIZON = 6           # gameweeks ahead
TOPN = 15             # printed leaders per position

# ---- tunables ----
FULL_MINUTES = 90.0
NAILED_FLOOR = 0.10   # min minutes-share for any squad player
MIN_MINUTES_FOR_HISTORY = 450   # below this, minutes_share() floors to 0 -> projects 0 (v1.1)
EP_WEIGHT_LOW_MIN = 0.7         # trust ep_next this much for low-minute players
EP_WEIGHT_HIGH_MIN = 0.25       # ...and this much for established starters
# Season-boundary cold start (v1.2): when almost no one has senior minutes yet (a
# fresh season), the minutes-share floor would gate the WHOLE league to 0. Detect
# that league-wide and fall back to FPL's own ep_next for available players.
COLD_START_ESTABLISHED_FRAC = 0.10   # <10% of the pool over the minutes floor => cold start
COLD_START_NOMINAL_MINUTES = 72.0    # assumed minutes for an available starter pre-history
HOME_EDGE = 1.06
DECAY = 0.96          # per-GW multiplier on history-driven rate

# FDR 1..5 -> multiplier, per defensive (GKP/DEF) / attacking (MID/FWD)
FDR_MULT_DEF = {1: 1.30, 2: 1.15, 3: 1.00, 4: 0.85, 5: 0.70}
FDR_MULT_ATT = {1: 1.25, 2: 1.12, 3: 1.00, 4: 0.88, 5: 0.75}

STATUS_MULT = {"a": 1.0, "d": 0.50, "i": 0.10, "s": 0.0, "u": 0.0}

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def load_csv(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


def base_rate(p):
    """Expected pts per 90 from last-season record + FPL's ep_next blend."""
    minutes = f(p["minutes"])
    pts = f(p["total_points"])
    ep_next = f(p.get("ep_next"))
    hist_p90 = (pts / minutes * FULL_MINUTES) if minutes > 0 else 0.0
    w_ep = EP_WEIGHT_LOW_MIN if minutes < MIN_MINUTES_FOR_HISTORY else EP_WEIGHT_HIGH_MIN
    if ep_next <= 0:
        w_ep = 0.0  # nothing to blend with
    return (1 - w_ep) * hist_p90 + w_ep * ep_next * (FULL_MINUTES / 90.0)


def minutes_share(p):
    minutes = f(p["minutes"])
    if minutes < MIN_MINUTES_FOR_HISTORY:
        return 0.0   # no senior history -> do not project (youth/new signings; news layer re-adds)
    share = minutes / (38.0 * FULL_MINUTES)
    return max(NAILED_FLOOR, min(1.0, share))


def is_cold_start(players):
    """True at a season boundary: fewer than COLD_START_ESTABLISHED_FRAC of the pool
    have crossed the minutes-history floor, so minutes can't gate nailedness yet."""
    if not players:
        return False
    established = sum(1 for p in players if f(p.get("minutes")) >= MIN_MINUTES_FOR_HISTORY)
    return established < COLD_START_ESTABLISHED_FRAC * len(players)


def status_mult(p, gw1=False):
    st = (p.get("status") or "a").strip()
    m = STATUS_MULT.get(st, 1.0)
    if gw1:
        cop = p.get("chance_of_playing_next_round")
        if cop not in (None, "", "None"):
            m = min(m, f(cop, 100.0) / 100.0)
    return m


def fixture_mult(pos_id, fdr, home):
    table = FDR_MULT_DEF if pos_id in (1, 2) else FDR_MULT_ATT
    return table.get(int(fdr), 1.0) * (HOME_EDGE if home else 1.0)


def project(players, fixtures):
    """Return list of dicts: one row per player per upcoming gameweek."""
    # fixtures by event -> {team_id: [(fdr, home)]}  (two entries for DGW)
    by_event = defaultdict(lambda: defaultdict(list))
    for fx in fixtures:
        if fx.get("finished") == "True":
            continue
        ev = fx.get("event")
        if not ev:
            continue
        ev = int(ev)
        by_event[ev][int(fx["team_h"])].append((int(fx["team_h_difficulty"]), True))
        by_event[ev][int(fx["team_a"])].append((int(fx["team_a_difficulty"]), False))

    events = sorted(by_event)[:HORIZON]
    cold = is_cold_start(players)
    rows = []
    for p in players:
        pos_id = int(p["element_type"])
        team = int(p["team"])
        rate = base_rate(p)
        mins = minutes_share(p)
        # Cold-start fallback: no minutes to trust league-wide, so for an available
        # player with an ep_next signal use FPL's own expected points as the per-game
        # base (it is already minutes-aware) instead of rate*mins == 0. Injured/no-signal
        # players fall through to rate*mins and stay ~0, as they should.
        ep_next = f(p.get("ep_next"))
        cold_fallback = (cold and mins == 0.0 and ep_next > 0
                         and (p.get("status") or "a").strip() in ("a", "d"))
        per_game_base = ep_next if cold_fallback else rate * mins
        xmins_disp = COLD_START_NOMINAL_MINUTES if cold_fallback else mins * FULL_MINUTES
        for i, ev in enumerate(events):
            games = by_event[ev].get(team, [])
            if not games:
                xp = 0.0  # blank gameweek
            else:
                xp = 0.0
                for fdr, home in games:
                    xp += (per_game_base * fixture_mult(pos_id, fdr, home)
                           * status_mult(p, gw1=(i == 0)) * (DECAY ** i))
            rows.append({
                "id": p["id"], "web_name": p["web_name"], "pos": POS[pos_id],
                "team": team, "gw": ev, "now_cost": f(p["now_cost"]) / 10.0,
                "xmins": round(xmins_disp, 1),
                "xpts": round(xp, 2),
                "horizon_xpts": None,  # filled below
            })
    # aggregate horizon totals
    tot = defaultdict(float)
    for r in rows:
        tot[r["id"]] += r["xpts"]
    for r in rows:
        r["horizon_xpts"] = round(tot[r["id"]], 2)
    return rows, events


def write_projections(rows, out):
    if not rows:
        print("no rows to write")
        return
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


def report(rows, events):
    print(f"\nhorizon: GWs {events}")
    for pos in ("GKP", "DEF", "MID", "FWD"):
        # best total over horizon per player in this position
        best = {}
        per_gw = defaultdict(dict)
        for r in rows:
            if r["pos"] != pos:
                continue
            pid = r["id"]
            if pid not in best or r["horizon_xpts"] > best[pid]["horizon_xpts"]:
                best[pid] = r
            per_gw[pid][r["gw"]] = r["xpts"]
        top = sorted(best.values(), key=lambda r: -r["horizon_xpts"])[:TOPN]
        print(f"\n{pos} top {TOPN} by {len(events)}-GW xpts:")
        hdr = "name".ljust(18) + "cost".rjust(6) + "".join(f"gw{g}".rjust(7) for g in events) + "total".rjust(8)
        print(hdr)
        for r in top:
            line = r["web_name"][:17].ljust(18) + f"{r['now_cost']:>6.1f}"
            for g in events:
                line += f"{per_gw[r['id']].get(g, 0.0):>7.2f}"
            line += f"{r['horizon_xpts']:>8.2f}"
            print(line)


def selftest():
    players = [
        # nailed premium attacker
        {"id": "1", "web_name": "NailedMan", "element_type": "4", "team": "1",
         "minutes": "3420", "total_points": "250", "ep_next": "6.0",
         "status": "a", "chance_of_playing_next_round": "", "now_cost": "150"},
        # rotation risk
        {"id": "2", "web_name": "Rotato", "element_type": "3", "team": "1",
         "minutes": "900", "total_points": "60", "ep_next": "3.0",
         "status": "a", "chance_of_playing_next_round": "", "now_cost": "60"},
        # injured
        {"id": "3", "web_name": "Crocked", "element_type": "2", "team": "2",
         "minutes": "3000", "total_points": "150", "ep_next": "0.0",
         "status": "i", "chance_of_playing_next_round": "0", "now_cost": "55"},
        # new signing, no history
        {"id": "4", "web_name": "NewGuy", "element_type": "3", "team": "2",
         "minutes": "0", "total_points": "0", "ep_next": "4.5",
         "status": "a", "chance_of_playing_next_round": "", "now_cost": "65"},
    ]
    fixtures = [
        {"event": "1", "team_h": "1", "team_a": "2", "team_h_difficulty": "2",
         "team_a_difficulty": "4", "finished": "False"},
        {"event": "2", "team_h": "2", "team_a": "1", "team_h_difficulty": "3",
         "team_a_difficulty": "3", "finished": "False"},
    ]
    rows, events = project(players, fixtures)
    by_name = {}
    for r in rows:
        by_name.setdefault(r["web_name"], []).append(r)

    nailed = by_name["NailedMan"]
    rotato = by_name["Rotato"]
    crocked = by_name["Crocked"]
    newguy = by_name["NewGuy"]

    assert nailed[0]["xpts"] > rotato[0]["xpts"], "nailed should outscore rotation"
    assert crocked[0]["xpts"] < 0.5, "injured should project ~0 in GW1"
    # v1.1 minutes-floor: a player below MIN_MINUTES_FOR_HISTORY has no senior history to
    # trust, so minutes_share() floors them to 0 and they project 0 regardless of ep_next.
    # New signings are deliberately gated out here; the (future) news/minutes layer re-adds
    # them. This is the intended behavior -- do not assert they "lean on ep_next".
    assert newguy[0]["xmins"] == 0.0, "new signing below minutes floor -> zero xmins"
    assert newguy[0]["xpts"] == 0.0, "new signing below minutes floor -> zero projection"
    # team 1 home FDR 2 in GW1 vs away FDR 3 in GW2 -> GW1 multiplier higher for attacker
    assert nailed[0]["xpts"] > nailed[1]["xpts"], "easier fixture should project higher"
    # blanks: no fixture -> 0
    rows2, _ = project(players, [fx for fx in fixtures if fx["event"] == "1"])
    assert all(r["xpts"] == 0.0 or r["gw"] == 1 for r in rows2)

    # --- season-boundary cold start (v1.2) -------------------------------------------
    # At season start almost nobody has accumulated MIN_MINUTES_FOR_HISTORY minutes,
    # so minutes_share() can't gate nailedness and the WHOLE league projects 0 (the
    # real GW1 bug). When the pool is league-wide cold, available players must fall
    # back to FPL's own ep_next instead of zeroing out. Mid-season new-signing gating
    # (asserted above, on an established pool) stays intact via league-wide detection.
    cold = [
        {"id": "10", "web_name": "FreshStarter", "element_type": "3", "team": "1",
         "minutes": "0", "total_points": "0", "ep_next": "5.0",
         "status": "a", "chance_of_playing_next_round": "", "now_cost": "80"},
        {"id": "11", "web_name": "FreshCrock", "element_type": "4", "team": "1",
         "minutes": "0", "total_points": "0", "ep_next": "4.0",
         "status": "i", "chance_of_playing_next_round": "0", "now_cost": "90"},
        {"id": "12", "web_name": "FreshNoSignal", "element_type": "2", "team": "2",
         "minutes": "0", "total_points": "0", "ep_next": "0.0",
         "status": "a", "chance_of_playing_next_round": "", "now_cost": "40"},
    ]
    crows, _ = project(cold, fixtures)
    cby = {}
    for r in crows:
        cby.setdefault(r["web_name"], []).append(r)
    assert cby["FreshStarter"][0]["xpts"] > 0.0, "cold start: available starter must lean on ep_next, not 0"
    assert cby["FreshStarter"][0]["xmins"] > 0.0, "cold start: available starter needs a nominal xmins"
    assert cby["FreshCrock"][0]["xpts"] == 0.0, "cold start: injured stays ~0 despite ep_next"
    assert cby["FreshNoSignal"][0]["xpts"] == 0.0, "cold start: no ep_next signal -> 0"

    print("SELFTEST PASS: nailed>rotation, injured~0, minutes-floor gates new signing to 0, "
          "FDR ordering, blanks=0, cold-start ep_next fallback")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "selftest":
        selftest()
        sys.exit(0)
    players = load_csv(DATA / "players.csv")
    fixtures = load_csv(DATA / "fixtures.csv")
    rows, events = project(players, fixtures)
    write_projections(rows, DATA / "projections.csv")
    report(rows, events)
