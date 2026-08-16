#!/usr/bin/env python3
"""
fpl_optimizer.py -- best 15-man squad + GW1 XI from projections.csv (ILP via PuLP).

Requires: pulp + CBC solver.
  Pi:  sudo apt install -y python3-pulp coinor-cbc
  (fallback: pip3 install --break-system-packages pulp)

Modes:
  scratch                 best squad under budget, ignoring current squad
  from-squad              k-sweep: best squad with at most k changes vs current squad
  xi                      best GW1 XI + bench order + captain from CURRENT squad
  selftest                offline sanity check

Options: --budget 100.0  --gw1-weight 2.0  --min-xmins 900  --max-changes 8
"""

import csv, sys, unicodedata
from pathlib import Path

DATA = Path("data")
SQUAD_SHAPE = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
MAX_PER_CLUB = 3
SQUAD_SIZE = 15

# YOUR current squad (web_names as in players.csv; matching is accent/case-insensitive)
KEEP_NAMES = ["Haaland", "B.Fernandes"]   # solver may never sell these

CURRENT_SQUAD = [
    "Roefs", "Verbruggen", "Senesi", "Guéhi", "Diop", "Mitchell", "F.Kadıoğlu",
    "B.Fernandes", "Semenyo", "Hughes", "Tavernier", "Szoboszlai",
    "Haaland", "Kusi Asare", "João Pedro",
]


def f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s.lower() if c.isalnum())


def load_players(path=DATA / "projections.csv"):
    rows = list(csv.DictReader(open(path)))
    players, gws = {}, set()
    for r in rows:
        pid = r["id"]
        gws.add(int(r["gw"]))
        if pid not in players:
            players[pid] = {"id": pid, "web_name": r["web_name"], "pos": r["pos"],
                            "team": r["team"], "cost": f(r["now_cost"]),
                            "xmins": f(r["xmins"]), "gw1": 0.0,
                            "horizon": f(r["horizon_xpts"])}
    gw1 = min(gws)
    for r in rows:
        if int(r["gw"]) == gw1:
            players[r["id"]]["gw1"] = f(r["xpts"])
    return players, gw1


def load_team_names():
    p = DATA / "teams.csv"
    if not p.exists():
        return {}
    return {r["id"]: r["short_name"] for r in csv.DictReader(open(p))}


def match_squad(players, names):
    """Map names -> player ids. Exact-normalized first, then unique substring, then best-xmins."""
    by_norm = {}
    for pid, p in players.items():
        by_norm.setdefault(norm(p["web_name"]), []).append(pid)
    ids, warnings = [], []
    for name in names:
        n = norm(name)
        cands = by_norm.get(n, [])
        if not cands:
            cands = [pid for pid, p in players.items()
                     if n and (n in norm(p["web_name"]) or norm(p["web_name"]) in n)]
        if not cands:
            warnings.append(f"NO MATCH: {name}")
            continue
        if len(cands) > 1:
            cands.sort(key=lambda pid: -players[pid]["xmins"])
            warnings.append(f"AMBIGUOUS: {name} -> {players[cands[0]]['web_name']} "
                            f"(also: {[players[c]['web_name'] for c in cands[1:3]]})")
        ids.append(cands[0])
    return ids, warnings


def solve(players, budget, gw1_weight, min_xmins, current_ids=None, max_outsiders=None):
    import pulp
    ids = list(players)
    x = pulp.LpVariable.dicts("x", ids, cat="Binary")
    prob = pulp.LpProblem("fpl", pulp.LpMaximize)
    prob += pulp.lpSum(x[i] * (players[i]["horizon"] + (gw1_weight - 1.0) * players[i]["gw1"])
                       for i in ids)
    prob += pulp.lpSum(x[i] for i in ids) == SQUAD_SIZE
    prob += pulp.lpSum(x[i] * players[i]["cost"] for i in ids) <= budget + 1e-9
    for pos, n in SQUAD_SHAPE.items():
        prob += pulp.lpSum(x[i] for i in ids if players[i]["pos"] == pos) == n
    for t in {players[i]["team"] for i in ids}:
        prob += pulp.lpSum(x[i] for i in ids if players[i]["team"] == t) <= MAX_PER_CLUB
    if min_xmins > 0:
        prob += pulp.lpSum(x[i] * players[i]["xmins"] for i in ids) >= min_xmins
    if current_ids is not None and max_outsiders is not None:
        prob += pulp.lpSum(x[i] for i in ids if i not in set(current_ids)) <= max_outsiders
    keep = globals().get("KEEP_IDS")
    if keep:
        for i in keep:
            if i in players:
                prob += x[i] == 1
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[status] != "Optimal":
        return None, None
    chosen = [i for i in ids if x[i].value() and x[i].value() > 0.5]
    return chosen, pulp.value(prob.objective)


def pick_xi(players, squad_ids):
    """Best GW1 XI over all legal formations. Returns (xi, bench_order, formation)."""
    by_pos = {pos: sorted((i for i in squad_ids if players[i]["pos"] == pos),
                          key=lambda i: -players[i]["gw1"]) for pos in SQUAD_SHAPE}
    best = None
    for d in range(3, 6):
        for m in range(2, 6):
            fw = 10 - d - m
            if not (1 <= fw <= 3):
                continue
            if d > len(by_pos["DEF"]) or m > len(by_pos["MID"]) or fw > len(by_pos["FWD"]):
                continue
            xi = ([by_pos["GKP"][0]] + by_pos["DEF"][:d] + by_pos["MID"][:m]
                  + by_pos["FWD"][:fw])
            total = sum(players[i]["gw1"] for i in xi)
            if best is None or total > best[0]:
                best = (total, xi, (d, m, fw))
    _, xi, formation = best
    rest = [i for i in squad_ids if i not in xi and players[i]["pos"] != "GKP"]
    rest.sort(key=lambda i: -players[i]["gw1"])
    gkp_bench = [i for i in squad_ids if players[i]["pos"] == "GKP" and i not in xi]
    return xi, rest + gkp_bench, formation


def report(players, chosen, gw1, team_names, title):
    cost = sum(players[i]["cost"] for i in chosen)
    hor = sum(players[i]["horizon"] for i in chosen)
    zeros = sum(1 for i in chosen if players[i]["horizon"] < 0.5)
    print(f"\n=== {title} ===")
    print(f"cost £{cost:.1f}m | 6-GW xpts {hor:.1f} | zero-projection players: {zeros}")
    for pos in ("GKP", "DEF", "MID", "FWD"):
        line = sorted((i for i in chosen if players[i]["pos"] == pos),
                      key=lambda i: -players[i]["horizon"])
        for i in line:
            p = players[i]
            tname = team_names.get(p["team"], p["team"])
            print(f"  {pos} {p['web_name'][:18]:<18} {tname:<4} £{p['cost']:>4.1f} "
                  f"gw1 {p['gw1']:>5.2f} hor {p['horizon']:>6.2f} xmins {p['xmins']:>5.1f}")
    xi, bench, formation = pick_xi(players, chosen)
    cap = max(xi, key=lambda i: players[i]["gw1"])
    vc = max((i for i in xi if i != cap), key=lambda i: players[i]["gw1"])
    print(f"  XI (GW{gw1}, {formation[0]}-{formation[1]}-{formation[2]}): "
          + ", ".join((players[i]["web_name"] + (" (C)" if i == cap else " (VC)" if i == vc else ""))
                      for i in xi))
    print(f"  bench order: " + ", ".join(players[i]["web_name"] for i in bench))
    print(f"  XI gw1 xpts: {sum(players[i]['gw1'] for i in xi):.2f} + captain bonus")


def get_args(args):
    def opt(name, default, cast=float):
        return cast(args[args.index(name) + 1]) if name in args else default
    return opt("--budget", 100.0), opt("--gw1-weight", 2.0), opt("--min-xmins", 900.0), \
           opt("--max-changes", 8, int)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    mode = args[0]
    if mode == "selftest":
        selftest()
        return
    players, gw1 = load_players()
    team_names = load_team_names()
    budget, gw1w, min_xmins, max_changes = get_args(args[1:])
    current_ids, warns = match_squad(players, CURRENT_SQUAD)
    for w in warns:
        print("WARN:", w)
    keep_ids, keep_warns = match_squad(players, KEEP_NAMES)
    for w in keep_warns:
        print("WARN (keep):", w)
    globals()["KEEP_IDS"] = keep_ids
    if mode == "scratch":
        chosen, _ = solve(players, budget, gw1w, min_xmins)
        if not chosen:
            sys.exit("no optimal solution (try --min-xmins 0)")
        report(players, chosen, gw1, team_names, f"SCRATCH optimal (budget £{budget:.1f}m)")
    elif mode == "from-squad":
        if len(current_ids) != SQUAD_SIZE:
            sys.exit(f"matched {len(current_ids)}/15 of current squad - fix CURRENT_SQUAD names")
        base, _ = solve(players, budget, gw1w, min_xmins, current_ids, max_outsiders=0)
        cur_hor = sum(players[i]["horizon"] for i in (base or []))
        print(f"current squad as-is: 6-GW xpts {cur_hor:.1f}")
        best, _ = solve(players, budget, gw1w, min_xmins)
        best_hor = sum(players[i]["horizon"] for i in (best or []))
        print(f"scratch optimal:      6-GW xpts {best_hor:.1f}  (gap {best_hor - cur_hor:+.1f})")
        print(f"\nk-sweep (max changes vs your squad):")
        prev = None
        for k in range(0, max_changes + 1):
            chosen, _ = solve(players, budget, gw1w, min_xmins, current_ids, max_outsiders=k)
            if not chosen:
                print(f"  k={k}: infeasible")
                continue
            hor = sum(players[i]["horizon"] for i in chosen)
            ins = [players[i]["web_name"] for i in chosen if i not in current_ids]
            outs = [players[i]["web_name"] for i in current_ids if i not in chosen]
            gain = "" if prev is None else f" (+{hor - prev:.1f})"
            print(f"  k={k}: xpts {hor:.1f}{gain}  OUT: {', '.join(outs) or '-'} | IN: {', '.join(ins) or '-'}")
            prev = hor
        report(players, best, gw1, team_names, "SCRATCH optimal for reference")
    elif mode == "xi":
        if len(current_ids) != SQUAD_SIZE:
            sys.exit(f"matched {len(current_ids)}/15 of current squad - fix CURRENT_SQUAD names")
        report(players, current_ids, gw1, team_names, "YOUR current squad")
    else:
        print(f"unknown mode: {mode}")
        sys.exit(1)


def selftest():
    players = {}
    def mk(pid, name, pos, team, cost, hor, gw1, xmins=80):
        players[pid] = {"id": pid, "web_name": name, "pos": pos, "team": team,
                        "cost": cost, "horizon": hor, "gw1": gw1, "xmins": xmins}
    for i in range(4):
        mk(f"g{i}", f"GK{i}", "GKP", str(10 + i), 4.5 + 0.5 * (i == 0), 20 - 2 * i, 3.5 - 0.3 * i)
    for i in range(8):
        mk(f"d{i}", f"DF{i}", "DEF", str(i % 6 + 1), 4.0 + 0.5 * i, 12 + 2 * i, 2.0 + 0.2 * i)
    for i in range(8):
        mk(f"m{i}", f"MD{i}", "MID", str(i % 6 + 1), 4.5 + 0.5 * i, 14 + 2 * i, 2.2 + 0.2 * i)
    for i in range(6):
        mk(f"f{i}", f"FW{i}", "FWD", str(i % 6 + 1), 5.0 + 0.5 * i, 10 + 2 * i, 1.8 + 0.2 * i)
    # club-cap test: 4 superstars all on team "9"
    mk("x1", "Star1", "DEF", "9", 6.0, 40, 5.0)
    mk("x2", "Star2", "MID", "9", 7.0, 40, 5.0)
    mk("x3", "Star3", "FWD", "9", 8.0, 40, 5.0)
    mk("x4", "Star4", "MID", "9", 7.0, 40, 5.0)

    chosen, obj = solve(players, 100.0, 2.0, 0.0)
    assert chosen and len(chosen) == 15, "need 15"
    shape = {}
    for i in chosen:
        shape[players[i]["pos"]] = shape.get(players[i]["pos"], 0) + 1
    assert shape == SQUAD_SHAPE, f"bad shape {shape}"
    assert sum(players[i]["cost"] for i in chosen) <= 100.0 + 1e-9
    n9 = sum(1 for i in chosen if players[i]["team"] == "9")
    assert n9 == 3, f"club cap violated: {n9}"

    cur = ["g2", "g3"] + [f"d{i}" for i in range(5)] + [f"m{i}" for i in range(5)] + [f"f{i}" for i in range(3)]
    chosen0, _ = solve(players, 100.0, 2.0, 0.0, cur, max_outsiders=0)
    assert set(chosen0) == set(cur), "k=0 must return current squad"
    totals = []
    for k in range(0, 4):
        ch, _ = solve(players, 100.0, 2.0, 0.0, cur, max_outsiders=k)
        totals.append(sum(players[i]["horizon"] for i in ch))
    assert all(b >= a - 1e-9 for a, b in zip(totals, totals[1:])), "k-sweep must be monotone"

    xi, bench, form = pick_xi(players, chosen)
    assert len(xi) == 11 and len(bench) == 4
    assert sum(1 for i in xi if players[i]["pos"] == "GKP") == 1
    assert sum(1 for i in xi if players[i]["pos"] == "DEF") >= 3
    assert sum(1 for i in xi if players[i]["pos"] == "FWD") >= 1
    cap = max(xi, key=lambda i: players[i]["gw1"])
    assert players[cap]["gw1"] == max(players[i]["gw1"] for i in chosen), "captain from XI max gw1"
    print("SELFTEST PASS: shape/budget/club-cap/k-sweep-monotone/XI-formation/captain")


if __name__ == "__main__":
    main()
