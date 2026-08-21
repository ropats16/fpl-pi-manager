#!/usr/bin/env python3
"""
season_state.py - the live single source of truth for "my season". Stdlib-only (Pi-friendly).

season-state.json is initialized from the real FPL entry, read by every tool that needs
"my season", and WRITTEN BACK whenever a decision is acted on. The prior effort's failure -
a state file that was never written back - is guarded here as a tested round-trip invariant.

Usage:
  python3 season_state.py init [--entry fixtures/entry.json] [--state season-state.json]
  python3 season_state.py set-squad DECISION.json [--state PATH]     # act on: initial build
  python3 season_state.py pull-squad [--gw N] [--entry-id ID] [--state PATH]  # load my live FPL squad
  python3 season_state.py transfer OUT_ID IN_PLAYER.json [--free] [--state PATH]
  python3 season_state.py chip NAME [--state PATH]                   # play a chip (mark used)
  python3 season_state.py advance-gw [--state PATH]                  # roll FT (+1, cap 5)
  python3 season_state.py show [--state PATH]
  python3 season_state.py selftest                                   # fixture-based round-trip

Every mutating command reads the state, applies the decision, appends a history entry, and
writes the file back in place (or to --state). Money is kept internally in integer tenths
(£0.1) to match the FPL API `now_cost` and avoid float drift.
"""

import json, os, sys, tempfile
from datetime import datetime, timezone

STATE_PATH = "season-state.json"
BUDGET = 100.0          # £m starting budget for the initial 15-man build
FT_CAP = 5              # up to 5 rolled free transfers (2026/27 rules)
FIRST_HALF_LAST_GW = 19  # chip set 1: GW1-19, set 2: GW20-38
POS_QUOTA = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
CLUB_CAP = 3
CHIPS = ("wildcard", "free_hit", "triple_captain", "bench_boost")
# mutable "my season" fields that decisions maintain and that must never be null once the
# state is initialized. entry_id is deliberately excluded: it is identity sourced from
# $FPL_ENTRY_ID at runtime (never committed), not a field the write-back loop maintains.
REQUIRED_NON_NULL = ("squad", "bank", "free_transfers", "current_gw", "objective")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- money helpers (work in integer tenths of £m) -------------------------------------

def tenths(pounds):
    return int(round(float(pounds) * 10))


def pounds(t):
    return round(t / 10.0, 1)


def selling_price(bought_for, current):
    """FPL selling rule: you keep only half of any rise, rounded down to £0.1; price
    drops are borne in full. Returns £m."""
    bf, cur = tenths(bought_for), tenths(current)
    if cur <= bf:
        return pounds(cur)
    return pounds(bf + (cur - bf) // 2)


# --- load / save ----------------------------------------------------------------------

def load_state(path):
    with open(path) as f:
        return json.load(f)


def save_state(state, path):
    """Atomic write-back: temp file in the same dir, then replace."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def log_decision(state, kind, detail):
    state.setdefault("history", []).append(
        {"ts": now_iso(), "gw": state.get("current_gw"), "type": kind, "detail": detail})


# --- init from the real entry ---------------------------------------------------------

def init_state(base, entry_id, entry=None):
    """Populate a template state. `entry_id` is the identity (resolved from $FPL_ENTRY_ID, so
    it never lives in the committed tree); `entry` is an optional real /entry/{id}/ payload for
    the deadline bank. Pre-season the entry has no picks (entered_events == []), so squad starts
    empty-but-not-null and gets filled by a set-squad decision; post-GW1 the bank is read off
    the entry. Note: the real entry_id is never written to history (it is PII)."""
    e = (entry or {}).get("entry", entry) or {}  # accept raw and distilled {"entry": ...} shapes
    state = dict(base)
    state["entry_id"] = entry_id
    state["current_gw"] = e.get("current_event") or 1
    state["squad"] = {"picks": [], "value": 0.0}
    bank = e.get("last_deadline_bank")
    state["bank"] = pounds(bank) if bank is not None else BUDGET
    state["free_transfers"] = 1
    state["pending_point_hits"] = 0
    state["active_chip"] = "none"
    state["objective"] = base.get("objective") or "Maximize overall rank"
    log_decision(state, "init", {"bank": state["bank"]})
    return state


# --- validation -----------------------------------------------------------------------

def validate_squad(picks):
    issues = []
    if len(picks) != 15:
        issues.append(f"squad must be 15 players, got {len(picks)}")
    ids = [p["id"] for p in picks]
    if len(set(ids)) != len(ids):
        issues.append("duplicate player ids in squad")
    counts = {}
    clubs = {}
    for p in picks:
        counts[p["pos"]] = counts.get(p["pos"], 0) + 1
        clubs[p["club"]] = clubs.get(p["club"], 0) + 1
    for pos, need in POS_QUOTA.items():
        if counts.get(pos, 0) != need:
            issues.append(f"need {need} {pos}, got {counts.get(pos, 0)}")
    for club, n in clubs.items():
        if n > CLUB_CAP:
            issues.append(f"club cap exceeded: {club} has {n} (max {CLUB_CAP})")
    return issues


# --- decisions (each mutates state; caller writes back) -------------------------------

def set_squad(state, decision):
    """Act on an initial-build decision: record the 15 picks, recompute bank and squad value.
    Each pick's purchase price is banked as `bought_for` for later selling. Bank defaults to
    the £100.0m budget minus squad cost; a mid-season rebuild (wildcard) must pass an explicit
    `bank` in the decision, since its budget is current value + bank, not £100.0m."""
    picks = []
    for p in decision["picks"]:
        q = dict(p)
        q.setdefault("bought_for", q["price"])
        picks.append(q)
    issues = validate_squad(picks)
    cost = sum(tenths(p["price"]) for p in picks)
    bank = decision.get("bank")
    bank_t = tenths(bank) if bank is not None else tenths(BUDGET) - cost
    if bank_t < 0:
        issues.append(f"squad over budget by £{pounds(-bank_t)}m")
    if issues:
        raise ValueError("invalid squad: " + "; ".join(issues))
    state["squad"] = {"picks": picks, "value": pounds(cost)}
    state["bank"] = pounds(bank_t)
    if "gw" in decision:
        state["current_gw"] = decision["gw"]
    if "captain" in decision:
        state["captain"] = decision["captain"]
    if "vice" in decision:
        state["vice"] = decision["vice"]
    log_decision(state, "set-squad",
                 {"n": len(picks), "value": state["squad"]["value"], "bank": state["bank"]})
    return state


def transfer(state, out_id, in_player, free=False):
    """Act on a transfer: sell OUT (at its FPL selling price), buy IN, adjust bank, spend a
    free transfer (or bank a -4 hit if none left, unless a wildcard/free-hit is active)."""
    squad = state["squad"]
    picks = squad["picks"]
    idx = next((i for i, p in enumerate(picks) if p["id"] == out_id), None)
    if idx is None:
        raise ValueError(f"player {out_id} not in squad")
    out = picks[idx]
    sell = selling_price(out.get("bought_for", out["price"]), out["price"])
    bank_t = tenths(state["bank"]) + tenths(sell) - tenths(in_player["price"])
    if bank_t < 0:
        raise ValueError(f"cannot afford {in_player.get('name')}: short £{pounds(-bank_t)}m")
    new = dict(in_player)
    new.setdefault("bought_for", new["price"])
    new.setdefault("starting", out.get("starting", True))
    new.setdefault("bench_order", out.get("bench_order"))
    trial = picks[:idx] + [new] + picks[idx + 1:]
    issues = validate_squad(trial)
    if issues:
        raise ValueError("transfer breaks squad: " + "; ".join(issues))

    chip_free = free or state.get("active_chip") in ("wildcard", "free_hit")
    hit = 0
    if not chip_free:
        if state.get("free_transfers", 0) >= 1:
            state["free_transfers"] -= 1
        else:
            hit = 4
            state["pending_point_hits"] = state.get("pending_point_hits", 0) + hit

    squad["picks"] = trial
    squad["value"] = pounds(sum(tenths(p["price"]) for p in trial))
    state["bank"] = pounds(bank_t)
    log_decision(state, "transfer", {"out": out["name"], "out_id": out_id, "sell": sell,
                                     "in": new.get("name"), "in_id": new["id"],
                                     "buy": new["price"], "hit": hit, "bank": state["bank"]})
    return state


def chip_period(gw):
    return "first_half" if gw <= FIRST_HALF_LAST_GW else "second_half"


def play_chip(state, name):
    """Act on a chip decision: mark it used in the current half's set. A second-half chip
    can only be played from GW20."""
    if name not in CHIPS:
        raise ValueError(f"unknown chip {name!r}; expected one of {CHIPS}")
    gw = state.get("current_gw", 1)
    period = chip_period(gw)
    chips = state["chips"][period]
    status = chips.get(name)
    if status == "used":
        raise ValueError(f"{name} already used in {period}")
    if isinstance(status, str) and status.startswith("available_from_GW20") and gw < 20:
        raise ValueError(f"{name} (second half) not available until GW20")
    chips[name] = "used"
    state["active_chip"] = name
    log_decision(state, "chip", {"chip": name, "period": period})
    return state


def advance_gw(state):
    """Roll into the next gameweek: +1 free transfer (capped at 5), clear the active chip,
    and unlock the second-half chip set on entry to GW20."""
    gw = state.get("current_gw", 1) + 1
    state["current_gw"] = gw
    state["free_transfers"] = min(FT_CAP, state.get("free_transfers", 0) + 1)
    state["active_chip"] = "none"
    if gw == 20:
        for name, status in state["chips"]["second_half"].items():
            if isinstance(status, str) and status.startswith("available_from_GW20"):
                state["chips"]["second_half"][name] = "available"
    log_decision(state, "advance-gw", {"gw": gw, "free_transfers": state["free_transfers"]})
    return state


def missing_non_null(state):
    """Return the required 'my season' fields that are still null/empty."""
    bad = []
    for k in REQUIRED_NON_NULL:
        v = state.get(k)
        if v is None:
            bad.append(k)
        elif k == "squad" and not isinstance(v, dict):
            bad.append(k)
    return bad


# --- CLI ------------------------------------------------------------------------------

def _opt(args, name, default=None):
    return args[args.index(name) + 1] if name in args else default


def resolve_entry_id(args, entry):
    """Entry id comes from $FPL_ENTRY_ID (per-machine .env, never committed), or --entry-id,
    or the id field of a --entry file. See .env.example."""
    raw = os.environ.get("FPL_ENTRY_ID") or _opt(args, "--entry-id")
    if raw is None and entry is not None:
        raw = (entry.get("entry", entry) or {}).get("id")
    if raw is None:
        sys.exit("no entry id: set FPL_ENTRY_ID (see .env.example) or pass --entry-id / --entry")
    return int(raw)


def cmd_init(args):
    entry_path = _opt(args, "--entry")  # optional gitignored real entry (for deadline bank)
    state_path = _opt(args, "--state", STATE_PATH)
    entry = load_state(entry_path) if entry_path else None
    entry_id = resolve_entry_id(args, entry)
    base = load_state(state_path)
    # Guard the live source of truth: init resets squad + free transfers, so refuse to clobber
    # an already-populated state unless the caller is explicit.
    if (base.get("squad") or {}).get("picks") and "--force" not in args:
        sys.exit(f"{state_path} already has a squad; pass --force to re-initialize")
    state = init_state(base, entry_id, entry)
    save_state(state, state_path)
    bad = missing_non_null(state)
    print(f"init: entry {state['entry_id']} | bank £{state['bank']}m | "
          f"FT {state['free_transfers']} | GW {state['current_gw']}")
    if bad:
        sys.exit(f"ERROR: null mutable fields after init: {bad}")
    print(f"wrote {state_path} (no null mutable fields)")


def cmd_set_squad(args):
    state_path = _opt(args, "--state", STATE_PATH)
    decision = load_state(args[1])
    state = load_state(state_path)
    set_squad(state, decision)
    save_state(state, state_path)
    print(f"set-squad: 15 picks | value £{state['squad']['value']}m | bank £{state['bank']}m")
    print(f"wrote {state_path}")


def cmd_transfer(args):
    state_path = _opt(args, "--state", STATE_PATH)
    out_id = int(args[1])
    in_player = load_state(args[2])
    state = load_state(state_path)
    transfer(state, out_id, in_player, free="--free" in args)
    save_state(state, state_path)
    print(f"transfer: OUT {out_id} IN {in_player.get('name')} | bank £{state['bank']}m | "
          f"FT {state['free_transfers']} | hit pts {state.get('pending_point_hits', 0)}")
    print(f"wrote {state_path}")


def cmd_chip(args):
    state_path = _opt(args, "--state", STATE_PATH)
    state = load_state(state_path)
    play_chip(state, args[1])
    save_state(state, state_path)
    print(f"chip: {args[1]} played ({chip_period(state['current_gw'])})")
    print(f"wrote {state_path}")


def cmd_advance(args):
    state_path = _opt(args, "--state", STATE_PATH)
    state = load_state(state_path)
    advance_gw(state)
    save_state(state, state_path)
    print(f"advance-gw: now GW {state['current_gw']} | FT {state['free_transfers']}")
    print(f"wrote {state_path}")


def cmd_pull_squad(args):
    """Fetch my live 15-man squad from the FPL entry and load it into the state,
    replacing whatever squad is there. entry_id from $FPL_ENTRY_ID or --entry-id;
    gw from --gw or the state's current_gw. Needs network (Pi / direct)."""
    import fpl_api
    state_path = _opt(args, "--state", STATE_PATH)
    entry_id = resolve_entry_id(args, None)
    state = load_state(state_path)
    gw = int(_opt(args, "--gw", state.get("current_gw") or 1))
    picks = fpl_api.get(f"/entry/{entry_id}/event/{gw}/picks/")
    bootstrap = fpl_api.distill_bootstrap(fpl_api.get("/bootstrap-static/"))
    decision = fpl_api.build_squad_decision(picks, bootstrap, gw)
    set_squad(state, decision)
    save_state(state, state_path)
    cap = next((p["name"] for p in state["squad"]["picks"]
                if p["id"] == state["captain"]), state["captain"])
    print(f"pull-squad: loaded {len(decision['picks'])} picks for GW{gw} | "
          f"bank £{state['bank']}m | value £{state['squad']['value']}m | (C) {cap}")


def cmd_show(args):
    state = load_state(_opt(args, "--state", STATE_PATH))
    picks = state.get("squad", {}).get("picks", [])
    print(f"entry {state.get('entry_id')} | GW {state.get('current_gw')} | "
          f"bank £{state.get('bank')}m | FT {state.get('free_transfers')} | "
          f"squad {len(picks)}/15 (£{state.get('squad', {}).get('value')}m)")
    for p in picks:
        star = "(C)" if p["id"] == state.get("captain") else \
               "(V)" if p["id"] == state.get("vice") else ""
        print(f"  {p['pos']:<3} {p['name'][:20]:<20} {p['club']:<4} £{p['price']:>4} {star}")


# --- fixture-based round-trip test ----------------------------------------------------

def selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    entry = load_state(os.path.join(here, "fixtures", "entry.json"))
    decision = load_state(os.path.join(here, "fixtures", "squad-decision.json"))
    template = load_state(os.path.join(here, "season-state.json"))

    tmp = tempfile.mkdtemp(prefix="season-state-")
    path = os.path.join(tmp, "season-state.json")

    # 1. INIT from the real entry -> no null mutable fields, written to disk
    state = init_state(template, entry["id"], entry)
    save_state(state, path)
    assert state["entry_id"] == 9999999, "entry_id must come from the resolved id"
    assert all("entry_id" not in h.get("detail", {}) for h in state["history"]), \
        "the entry id (PII) must never be written to history"
    assert missing_non_null(state) == [], f"null mutable fields after init: {missing_non_null(state)}"
    assert state["bank"] == 100.0 and state["free_transfers"] == 1

    # 2. READ -> ACT (set-squad) -> WRITE-BACK, then READ the file again and confirm it stuck
    state = load_state(path)
    set_squad(state, decision)
    save_state(state, path)
    reread = load_state(path)
    assert len(reread["squad"]["picks"]) == 15, "squad must be written back to the file"
    assert reread["bank"] == 0.0, f"bank should be £0.0 after a £100.0 build, got {reread['bank']}"
    assert reread["squad"]["value"] == 100.0
    assert missing_non_null(reread) == []

    # 3. selling-price rule (keep half the rise, drops in full)
    assert selling_price(4.0, 4.6) == 4.3, "profit of 0.6 -> keep 0.3"
    assert selling_price(5.0, 4.5) == 4.5, "price drop borne in full"
    assert selling_price(6.0, 6.1) == 6.0, "0.1 rise rounds down to 0 kept"

    # 4. TRANSFER round-trip: swap van Ewijk (id 7, £4.0 DEF) for a like £4.0 DEF, on the disk state
    incoming = {"id": 99, "name": "Andersen", "pos": "DEF", "club": "FUL", "price": 4.0}
    state = load_state(path)
    ft_before, bank_before = state["free_transfers"], state["bank"]
    transfer(state, 7, incoming, free=False)
    save_state(state, path)
    after = load_state(path)
    assert not any(p["id"] == 7 for p in after["squad"]["picks"]), "OUT player must be gone"
    assert any(p["id"] == 99 for p in after["squad"]["picks"]), "IN player must be present"
    assert len(after["squad"]["picks"]) == 15 and validate_squad(after["squad"]["picks"]) == []
    assert after["free_transfers"] == ft_before - 1, "a transfer spends one free transfer"
    assert after["bank"] == bank_before, "even-money swap leaves bank unchanged"
    assert after["history"][-1]["type"] == "transfer", "the decision is logged to history"

    # 5. second transfer with 0 FT -> a -4 point hit is banked
    state = load_state(path)
    assert state["free_transfers"] == 0
    incoming2 = {"id": 100, "name": "Cash", "pos": "DEF", "club": "AVL", "price": 4.0}
    transfer(state, 99, incoming2, free=False)
    assert state["pending_point_hits"] == 4, "a transfer with no FT costs 4 points"
    assert state["free_transfers"] == 0

    # 6. over-budget transfer is rejected, state untouched
    state = load_state(path)
    try:
        transfer(state, 4, {"id": 101, "name": "TooDear", "pos": "DEF", "club": "TOT", "price": 99.0})
        assert False, "over-budget transfer must raise"
    except ValueError:
        pass

    # 7. CHIP availability: play wildcard in GW1, then it cannot be replayed
    state = load_state(path)
    play_chip(state, "wildcard")
    assert state["chips"]["first_half"]["wildcard"] == "used"
    try:
        play_chip(state, "wildcard")
        assert False, "a used chip must not be replayable"
    except ValueError:
        pass

    # 8. FREE-TRANSFER rollover: +1 per GW, capped at 5
    state = load_state(path)
    state["free_transfers"] = 0
    advance_gw(state)
    assert state["free_transfers"] == 1 and state["current_gw"] == 2, "roll +1 into next GW"
    state["free_transfers"] = 5
    advance_gw(state)
    assert state["free_transfers"] == 5, "free transfers cap at 5"

    # 9. second-half chip set unlocks on entry to GW20
    state = load_state(path)
    state["current_gw"] = 19
    assert state["chips"]["second_half"]["wildcard"].startswith("available_from_GW20")
    advance_gw(state)
    assert state["current_gw"] == 20
    assert state["chips"]["second_half"]["wildcard"] == "available", "GW20 unlocks set 2"
    try:
        s2 = load_state(path); s2["current_gw"] = 5
        play_chip(s2, "wildcard")  # first_half wildcard still available here -> fine
    except ValueError:
        assert False, "first-half chip should be playable pre-GW20"

    # 10. pull-squad contract: a decision built from live picks (fpl_api) loads via set_squad.
    import fpl_api
    types = [1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4]  # 2 GKP, 5 DEF, 5 MID, 3 FWD
    elements = [{"id": 200 + i, "web_name": f"Real{i}", "team": (i % 5) + 1,  # <=3 per club
                 "element_type": t, "now_cost": 45} for i, t in enumerate(types)]
    bsnap = fpl_api.distill_bootstrap({
        "elements": elements,
        "teams": [{"id": t, "short_name": f"C{t}"} for t in range(1, 6)],
        "events": [],
    })
    picks_payload = {
        "picks": [{"element": 200 + i, "position": i + 1,
                   "is_captain": i == 4, "is_vice_captain": i == 8}
                  for i in range(15)],
        "entry_history": {"bank": 12},
    }
    decision = fpl_api.build_squad_decision(picks_payload, bsnap, gw=3)
    state = load_state(path)
    set_squad(state, decision)
    assert len(state["squad"]["picks"]) == 15, "live picks must load as a 15-man squad"
    assert any(p["id"] == 214 for p in state["squad"]["picks"]), "pick ids are real element ids"
    assert state["captain"] == 204 and state["vice"] == 208, "captain/vice are element ids"
    assert state["bank"] == 1.2, f"bank from entry_history tenths, got {state['bank']}"

    print("SELFTEST PASS: init / read-act-write / transfer / selling-price / chips / FT-rollover / pull-squad")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    try:
        if cmd == "selftest":
            selftest()
        elif cmd == "init":
            cmd_init(args)
        elif cmd == "set-squad":
            cmd_set_squad(args)
        elif cmd == "pull-squad":
            cmd_pull_squad(args)
        elif cmd == "transfer":
            cmd_transfer(args)
        elif cmd == "chip":
            cmd_chip(args)
        elif cmd == "advance-gw":
            cmd_advance(args)
        elif cmd == "show":
            cmd_show(args)
        else:
            print(f"unknown command: {cmd}")
            sys.exit(1)
    except (ValueError, FileNotFoundError, KeyError) as e:
        sys.exit(f"ERROR: {e}")
