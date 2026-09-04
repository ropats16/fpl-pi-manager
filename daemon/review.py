"""The post-gameweek review wake (#21) — the learning loop's scoring half.

After a gameweek settles, this timer-driven wake fetches the actuals, sets them
against the projections the decision was made on (snapshotted by the brief wake
at draft/act time into `data/projections-gwNN.csv`) and the decision the daemon
recorded (`season-state.json` decisions.gwNN), and grades the calls: model vs
outcome per player and in aggregate, captain vs vice / best-in-XI, each transfer
in-minus-out net of the hit, bench vs the starters it could have replaced.

Every number is computed HERE, in code, from the FPL API — the model never
grades itself. The gaffer gets the scorecard as distilled markdown inside the
user turn (never raw JSON — repo invariant #9/#10), writes the honest
luck-vs-process review the playbook asks for, and ends with a ```learnings
block; the daemon strips and vets that block through the #20 gate before
anything reaches Telegram or the diary.

Same never-lose-a-wake posture as the watch/brief: a fetch/LLM error logs and
returns non-zero with the review state UNadvanced (the next tick retries); a
Telegram send failure leaves the GW un-marked so it re-sends. A GW is marked
reviewed only after its review was delivered. Silence (no new finished GW) is
the default and costs zero tokens.
"""

import csv
import json
import os
import re
from datetime import datetime, timezone

from daemon.learnings import record_learnings
from daemon.plan import _atomic_write_json, append_decision_log, parse_plan
from daemon.prompt import normalize_name
from daemon.propose import REVIEW_PROPOSE_HINT, parse_proposal

# How many biggest projection misses (each way) the scorecard names. The rest
# is summarised as an aggregate so the prompt stays bounded.
TOP_MISSES = 5


def latest_finished_gw(events):
    """The highest event id whose `finished` is true and whose `data_checked`
    (when the key is present) is also true — FPL flips `finished` at the last
    whistle and `data_checked` once bonus points are final. None if no event has
    finished. Fed the distilled bootstrap events."""
    best = None
    for e in events or []:
        if not e.get("finished"):
            continue
        if "data_checked" in e and not e.get("data_checked"):
            continue
        gid = e.get("id")
        if isinstance(gid, int) and (best is None or gid > best):
            best = gid
    return best


def snapshot_path(store_dir, gw):
    """`<store_dir>/projections-gwNN.csv` — where the brief wake stores the
    projection rows the GW's decision was made on."""
    return os.path.join(store_dir, f"projections-gw{gw:02d}.csv")


def snapshot_projections(projections_path, gw, out_path):
    """Copy the rows for `gw` from the pipeline's long-format projections.csv
    (id, web_name, pos, team, gw, now_cost, xmins, xpts, horizon_xpts) to
    `out_path`, header included. Returns the number of rows written. A missing
    source or zero matching rows writes nothing and returns 0; the write is
    temp+rename so a power cut never leaves a half file."""
    if not projections_path or not os.path.exists(projections_path):
        return 0
    rows, fields = [], None
    with open(projections_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames
        for row in reader:
            try:
                if int(row.get("gw")) == gw:
                    rows.append(row)
            except (TypeError, ValueError):
                continue             # malformed pipeline row -> skip
    if not rows or not fields:
        return 0
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, out_path)
    return len(rows)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_gw_projections(path):
    """Rows of one snapshot file -> {"by_id": {int id: row}, "by_name": {(normalized
    name, pos): row}} where row = {"id", "web_name", "pos", "xpts", "xmins"}.
    Missing/unreadable file -> both maps empty (the review degrades to
    'proj n/a', never crashes)."""
    out = {"by_id": {}, "by_name": {}}
    if not path or not os.path.exists(path):
        return out
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                try:
                    pid = int(raw.get("id"))
                except (TypeError, ValueError):
                    pid = None
                row = {"id": pid, "web_name": raw.get("web_name") or "",
                       "pos": raw.get("pos") or "", "xpts": _f(raw.get("xpts")),
                       "xmins": _f(raw.get("xmins"))}
                if pid is not None:
                    out["by_id"].setdefault(pid, row)
                key = (normalize_name(row["web_name"]), row["pos"])
                if key[0]:
                    out["by_name"].setdefault(key, row)
    except Exception:                # noqa: BLE001 — a broken snapshot costs a section, never a wake
        return {"by_id": {}, "by_name": {}}
    return out


def _fmt_rank(v):
    """Overall rank as the compact string Rohit reads: 3123456 -> '3.1M',
    412000 -> '412k', 812 -> '812', None -> 'n/a'."""
    if not isinstance(v, (int, float)):
        return "n/a"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}k"
    return f"{int(v)}"


# The Unicode minus (U+2212) reads better than a hyphen next to numbers and is
# what the headline/miss lines quote, so it is used everywhere a signed delta or
# gain is rendered.
_MINUS = "−"


def _signed(v, dp=1):
    """A signed one-decimal string with the Unicode minus: -3.8 -> '−3.8'."""
    if v is None:
        return "n/a"
    if v < 0:
        return f"{_MINUS}{abs(v):.{dp}f}"
    return f"+{v:.{dp}f}"


def _signed_int(v):
    """A signed integer string with the Unicode minus: -18 -> '−18', 0 -> '0'."""
    if v is None:
        return "n/a"
    if v < 0:
        return f"{_MINUS}{abs(int(v))}"
    if v > 0:
        return f"+{int(v)}"
    return "0"


def _pts(v):
    """A raw-points scalar for prose: None -> 'n/a', else the integer."""
    return "n/a" if v is None else v


def _proj(sc):
    """The projected XI total for prose — 'n/a' when not one starter matched a
    projection row (no snapshot), never a misleading '0.0'."""
    return f"{sc['projected_xi']:.1f}" if sc["matched"][0] else "n/a"


def build_scorecard(gw, live, picks, players, projections, decision,
                    picks_source="entry"):
    """Pure. Grade the gameweek.

    live        : {int element id: {"minutes", "total_points", "goals_scored",
                   "assists", "clean_sheets", "bonus"}} — fpl_api.distill_live().
    picks       : the fielded 15 as [{"id"/"element", "position" (1..15),
                   "is_captain", "is_vice_captain"}] plus optional
                   "entry_history" {"points", "points_on_bench", "rank",
                   "overall_rank", "event_transfers", "event_transfers_cost",
                   "bank"}, "automatic_subs" [{"element_in", "element_out"}]
                   and "active_chip" ("bboost"/"3xc"/…) — i.e. the raw
                   /entry/{id}/event/{gw}/picks/ payload. Multipliers are NOT
                   trusted from the payload: the effective XI and armband are
                   re-derived here from the autosubs list and minutes played
                   (vice takes over when the captain did not play), so the
                   grade is on what FPL actually counted. May be None when no
                   entry id is configured; then the caller passes the
                   season-state squad shaped the same way (position from
                   starting/bench_order) and picks_source="state".
    players     : {int element id: {"web_name", "pos", "team"}} from the
                   distilled bootstrap (fpl_api.player_index()).
    projections : load_gw_projections() result (may be empty maps).
    decision    : season-state decisions.gwNN dict {"plan", "status",
                   "recorded_at"} or None.

    Returns a dict with (all optional fields None/[] when the data is missing,
    and every gap named in "gaps"):
      gw, points, points_on_bench, overall_rank, gw_rank, transfers_made,
      transfers_cost, picks_source, active_chip,
      projected_xi (sum xpts over the PLANNED XI, planned captain ×2 — ×3 on
        triple captain — over matched players only), matched (n matched / n
        planned starters), actual_xi (sum of points × effective multiplier
        over the EFFECTIVE XI after autosubs — equals `points` when entry
        data is present),
      rows: [{"name","pos","starter","multiplier","proj","actual","minutes",
              "delta"}] for all 15 (starter/multiplier = effective), sorted
              by |delta| desc (None deltas last),
      misses: {"under": top TOP_MISSES rows with actual < proj,
               "over":  top TOP_MISSES rows with actual > proj},
      autosubs: [{"in","in_points","out","out_points"}] FPL applied,
      captain: {"name","points","planned_name","armband_passed","vice_name",
                "vice_points","best_name","best_points","gain_vs_best"}
                (name/points = the EFFECTIVE captain, raw GW pts; best =
                highest raw pts among effective starters; gain_vs_best =
                (cap − best) × (multiplier − 1), i.e. what moving the armband
                to the best starter would have changed the total by),
      plan_captain: the decision plan's captain when it differs from the
                armband set in the app (an override happened) else None,
      transfers: [{"out","in","out_points","in_points","net"}] from the
                decision plan pairs (net = in − out); transfers_applied is
                False for a no_write plan (graded as the counterfactual);
                transfers_net = sum(net) − hits only when every pair resolved,
      transfers_applied, transfers_net, hits,
      bench_calls: [{"bench","bench_points","starter","starter_points"}] for
                each (post-autosub) bench player who outscored an effective
                starter of the same position,
      decision_status: "locked" | "no_write" | None,
      gaps: [str] e.g. "no projections snapshot for GW2", "no daemon decision
            recorded for GW2 (ad-hoc gameweek)", "picks from season state (no
            entry id) — autosubs not applied", "transfer name 'X' ambiguous —
            not graded".

    Ids in `picks` may be synthetic (season-state before pull-squad); resolve
    each pick to a real element via `players` by id when present, else by
    (normalize_name(name), pos)."""
    live = live or {}
    players = players or {}
    projections = projections or {"by_id": {}, "by_name": {}}
    by_id = projections.get("by_id") or {}
    by_name = projections.get("by_name") or {}
    plan = decision.get("plan") if decision else None
    status = decision.get("status") if decision else None
    picks = picks or {}
    active_chip = picks.get("active_chip")

    # Name join tables over the bootstrap: position-scoped (pick resolution and
    # projection-by-name), exact web_name, and surname -> ids (transfer names).
    name_pos, name_exact, name_norm = {}, {}, {}
    for pid, info in players.items():
        web = (info or {}).get("web_name") or ""
        nn = normalize_name(web)
        if web:
            name_exact.setdefault(web.strip().casefold(), pid)
        if nn:
            name_pos.setdefault((nn, (info or {}).get("pos")), pid)
            name_norm.setdefault(nn, set()).add(pid)

    def _resolve_name(name):
        """A plan's web name -> (element id, None) or (None, reason). Exact
        web_name wins; a surname join is trusted only when it is unique — two
        Silvas must not have one's points laundered onto the other."""
        if not name:
            return None, "empty"
        pid = name_exact.get(str(name).strip().casefold())
        if pid is not None:
            return pid, None
        ids = name_norm.get(normalize_name(name), ())
        if len(ids) == 1:
            return next(iter(ids)), None
        return None, ("ambiguous" if ids else "unknown")

    built, gaps = [], []
    for pick in (picks or {}).get("picks", []) or []:
        pid = pick.get("id")
        if pid is None:
            pid = pick.get("element")
        pos_hint = pick.get("pos")
        rid = None
        if pid in players:
            rid = pid
        else:                                # synthetic id: join by (name, pos)
            key = (normalize_name(pick.get("name")), pos_hint)
            if key[0] and key in name_pos:
                rid = name_pos[key]
        if rid is not None:
            name = players[rid].get("web_name")
            pos = players[rid].get("pos")
        else:
            name = pick.get("name") or (f"#{pid}" if pid is not None else "?")
            pos = pos_hint or "?"
            gaps.append(f"could not resolve squad pick '{name}'")

        position = pick.get("position")
        # Planned XI = positions 1..11 as entered (all 15 under a bench boost);
        # the effective XI and multipliers are derived below from what FPL
        # itself applied after the whistle (autosubs, armband to the vice).
        planned = ((isinstance(position, int) and 1 <= position <= 11)
                   or active_chip == "bboost")

        proj = None
        if rid is not None and rid in by_id:
            proj = by_id[rid].get("xpts")
        else:
            hit = by_name.get((normalize_name(name), pos))
            if hit:
                proj = hit.get("xpts")

        actual = minutes = None
        if rid is not None and rid in live:
            actual = live[rid].get("total_points")
            minutes = live[rid].get("minutes")

        delta = (actual - proj) if (actual is not None and proj is not None) else None
        built.append({
            "name": name, "pos": pos, "planned": planned, "starter": planned,
            "multiplier": 0, "proj": proj, "actual": actual, "minutes": minutes,
            "delta": delta, "position": position,
            "is_captain": bool(pick.get("is_captain")),
            "is_vice": bool(pick.get("is_vice_captain")), "id": rid})

    # --- what FPL applied after the whistle ---------------------------------
    # Autosubs: element_out leaves the XI, element_in joins it (bench order and
    # formation legality are FPL's to decide; the payload is the record).
    by_rid = {b["id"]: b for b in built if b["id"] is not None}
    autosubs = []
    for s in picks.get("automatic_subs") or []:
        o, i = by_rid.get(s.get("element_out")), by_rid.get(s.get("element_in"))
        if o is not None and i is not None:
            o["starter"], i["starter"] = False, True
            autosubs.append({"in": i["name"], "in_points": i["actual"],
                             "out": o["name"], "out_points": o["actual"]})

    def _played(b):
        return b is not None and b["starter"] and (b["minutes"] or 0) > 0

    # The armband: the planned captain unless he did not play and the vice did.
    planned_cap = next((b for b in built if b["is_captain"]), None)
    vice = next((b for b in built if b["is_vice"]), None)
    cap = planned_cap
    if planned_cap is not None and not _played(planned_cap) and _played(vice):
        cap = vice
    cap_mult = 3 if active_chip == "3xc" else 2
    for b in built:
        b["multiplier"] = (cap_mult if b is cap else 1) if b["starter"] else 0

    def _row(b):
        return {k: b[k] for k in ("name", "pos", "starter", "multiplier",
                                  "proj", "actual", "minutes", "delta")}

    # Two frames, deliberately: the model projected the PLANNED XI with the
    # planned captain doubled; the outcome is the EFFECTIVE XI FPL fielded.
    planned_xi = [b for b in built if b["planned"]]
    starters = [b for b in built if b["starter"]]
    actual_xi = sum(b["actual"] * b["multiplier"] for b in starters
                    if b["actual"] is not None)
    projected_xi = sum(b["proj"] * (cap_mult if b is planned_cap else 1)
                       for b in planned_xi if b["proj"] is not None)
    matched = (sum(1 for b in planned_xi if b["proj"] is not None), len(planned_xi))

    eh = picks.get("entry_history") or {}
    points = eh["points"] if "points" in eh else actual_xi

    # rows: every pick sorted by |delta| desc, None deltas last.
    rows = [_row(b) for b in sorted(
        built, key=lambda b: (b["delta"] is None, -abs(b["delta"] or 0)))]

    scored = [b for b in built if b["delta"] is not None]
    under = sorted((b for b in scored if b["actual"] < b["proj"]),
                   key=lambda b: b["delta"])[:TOP_MISSES]
    over = sorted((b for b in scored if b["actual"] > b["proj"]),
                  key=lambda b: -b["delta"])[:TOP_MISSES]
    misses = {"under": [_row(b) for b in under], "over": [_row(b) for b in over]}

    # Captain grade on the EFFECTIVE captain, raw (un-multiplied) points.
    # best-in-XI keeps the captain on a tie so a captain who tied the top scorer
    # shows a 0 gain, not a phantom loss. Moving the armband to the best starter
    # would have changed the total by (best - cap) per extra multiple — ×1 for a
    # normal captain, ×2 under triple captain — never by 2×(cap - best).
    best_b, best_val = None, None
    for b in starters:
        if b["actual"] is not None and (best_val is None or b["actual"] > best_val):
            best_b, best_val = b, b["actual"]
    if cap and cap["actual"] is not None and cap["actual"] == best_val:
        best_b = cap
    cap_pts = cap["actual"] if cap else None
    gain = ((cap_pts - best_val) * (cap_mult - 1)
            if (cap_pts is not None and best_val is not None) else None)
    captain = {
        "name": cap["name"] if cap else None, "points": cap_pts,
        "planned_name": planned_cap["name"] if planned_cap else None,
        "armband_passed": cap is not planned_cap,
        "vice_name": vice["name"] if vice else None,
        "vice_points": vice["actual"] if vice else None,
        "best_name": best_b["name"] if best_b else None,
        "best_points": best_val, "gain_vs_best": gain}

    # An override in the app: the armband set differs from the plan's captain.
    plan_captain = None
    if plan and plan.get("captain") and planned_cap and planned_cap["name"]:
        if (normalize_name(plan["captain"])
                != normalize_name(planned_cap["name"])):
            plan_captain = plan["captain"]

    # Transfers: plan pairs (short side padded), each side priced from live by
    # name. A no_write plan was never applied, so its pairs are graded as the
    # counterfactual it would have been, and labelled as such.
    transfers, transfers_net = [], None
    hits = (plan.get("hits") if plan else 0) or 0
    transfers_applied = status == "locked"
    if plan:
        ti = plan.get("transfers_in") or []
        to = plan.get("transfers_out") or []
        for i in range(max(len(ti), len(to))):
            pair = {"out": to[i] if i < len(to) else None,
                    "in": ti[i] if i < len(ti) else None}
            pts = {}
            for side in ("out", "in"):
                pid, why = _resolve_name(pair[side])
                pts[side] = ((live.get(pid) or {}).get("total_points")
                             if pid is not None else None)
                if pid is None and pair[side]:
                    gaps.append(f"transfer name '{pair[side]}' {why} — not graded")
            net = ((pts["in"] - pts["out"])
                   if (pts["in"] is not None and pts["out"] is not None) else None)
            transfers.append({"out": pair["out"], "in": pair["in"],
                              "out_points": pts["out"], "in_points": pts["in"],
                              "net": net})
        if transfers and all(t["net"] is not None for t in transfers):
            transfers_net = sum(t["net"] for t in transfers) - hits
    elif eh.get("event_transfers"):
        gaps.append(f"{eh['event_transfers']} transfer(s) made in the app but no "
                    "plan recorded — not graded")

    # Bench calls: a bench player (after autosubs) who outscored a same-position
    # starter names the LOWEST-scoring starter he could have replaced.
    bench_calls = []
    for b in built:
        if b["starter"] or b["actual"] is None:
            continue
        beaten = [s for s in starters if s["pos"] == b["pos"]
                  and s["actual"] is not None and s["actual"] < b["actual"]]
        if beaten:
            worst = min(beaten, key=lambda s: s["actual"])
            bench_calls.append({"bench": b["name"], "bench_points": b["actual"],
                                "starter": worst["name"],
                                "starter_points": worst["actual"]})

    if not by_id and not by_name:
        gaps.append(f"no projections snapshot for GW{gw}")
    if decision is None:
        gaps.append(f"no daemon decision recorded for GW{gw} (ad-hoc gameweek)")
    if picks_source == "state":
        gaps.append("picks from season state (no entry id) — autosubs not applied")

    return {
        "gw": gw, "points": points, "points_on_bench": eh.get("points_on_bench"),
        "overall_rank": eh.get("overall_rank"), "gw_rank": eh.get("rank"),
        "transfers_made": eh.get("event_transfers"),
        "transfers_cost": eh.get("event_transfers_cost"),
        "picks_source": picks_source, "active_chip": active_chip,
        "projected_xi": projected_xi, "matched": matched, "actual_xi": actual_xi,
        "rows": rows, "misses": misses, "autosubs": autosubs,
        "captain": captain, "plan_captain": plan_captain, "transfers": transfers,
        "transfers_applied": transfers_applied, "transfers_net": transfers_net,
        "hits": hits, "bench_calls": bench_calls, "decision_status": status,
        "gaps": gaps}


def _proj_str(v):
    return "n/a" if v is None else f"{v:.1f}"


def render_scorecard(sc, full=False):
    """The scorecard as distilled markdown — headline numbers, the top misses,
    captain/transfer/bench grades, decision status, and the gaps spelled out.
    Never json.dumps (invariant #9/#10). Bounded for the prompt: at most
    2*TOP_MISSES player lines plus the grades. `full=True` (the repo record)
    adds the per-player table for all 15."""
    m, n = sc["matched"]
    pts = sc["points"]
    head = (f"GW{sc['gw']} scorecard — {_pts(pts)} pts "
            f"(proj {_proj(sc)}, {m}/{n} matched)")
    if sc.get("points_on_bench") is not None:
        head += f" · bench {sc['points_on_bench']}"
    if sc.get("overall_rank") is not None:
        head += f" · rank {_fmt_rank(sc['overall_rank'])}"
    if sc.get("active_chip"):
        head += f" · chip {sc['active_chip']}"
    lines = [head]

    def _miss(r):
        return (f"- {r['name']} ({r['pos']}) proj {r['proj']:.1f} → "
                f"actual {r['actual']} ({_signed(r['delta'])})")

    misses = sc["misses"]
    if misses["under"] or misses["over"]:
        lines += ["", "## Biggest misses"]
        lines += [_miss(r) for r in misses["under"]]
        lines += [_miss(r) for r in misses["over"]]

    if full and sc["rows"]:
        lines += ["", "## All picks (proj → actual)"]
        for r in sc["rows"]:
            role = f"XI ×{r['multiplier']}" if r["starter"] else "bench"
            lines.append(f"- {r['name']} ({r['pos']}, {role}) "
                         f"{_proj_str(r['proj'])} → {_pts(r['actual'])}"
                         + (f" ({_signed(r['delta'])})" if r["delta"] is not None
                            else "")
                         + (f", {r['minutes']} min" if r["minutes"] is not None
                            else ""))

    if sc.get("autosubs"):
        lines += ["", "## Autosubs (applied by FPL)"]
        for a in sc["autosubs"]:
            lines.append(f"- {a['in']} ({_pts(a['in_points'])}) in for "
                         f"{a['out']} ({_pts(a['out_points'])})")

    cap = sc["captain"]
    cap_lines = []
    if cap and cap.get("name"):
        cap_lines.append(f"- (C) {cap['name']}: {_pts(cap['points'])} pts")
        if cap.get("armband_passed"):
            cap_lines.append(f"- armband passed: {cap['planned_name']} did not "
                             f"play, vice {cap['name']} counted as captain")
        elif cap.get("vice_name"):
            cap_lines.append(
                f"- (VC) {cap['vice_name']}: {_pts(cap['vice_points'])} pts")
        if cap.get("best_name"):
            cap_lines.append(
                f"- best in XI: {cap['best_name']} {_pts(cap['best_points'])} "
                f"({_signed_int(cap['gain_vs_best'])} vs best)")
    if sc.get("plan_captain"):
        cap_lines.append(
            f"- plan captain was {sc['plan_captain']} (overridden in the app)")
    if cap_lines:
        lines += ["", "## Captain"] + cap_lines

    if sc["transfers"]:
        applied = sc.get("transfers_applied")
        lines += ["", "## Transfers" + ("" if applied else
                                        " — planned, NOT applied (no approval)")]
        for t in sc["transfers"]:
            lines.append(
                f"- {t['out'] or '—'} ({_pts(t['out_points'])}) → "
                f"{t['in'] or '—'} ({_pts(t['in_points'])}) = "
                f"net {_signed_int(t['net'])}")
        if sc["transfers_net"] is not None:
            lines.append(f"- net after −{sc['hits']} hit: "
                         f"{_signed_int(sc['transfers_net'])}"
                         + ("" if applied else " (counterfactual)"))

    if sc["bench_calls"]:
        lines += ["", "## Bench"]
        for b in sc["bench_calls"]:
            lines.append(
                f"- {b['bench']} ({b['bench_points']}) outscored "
                f"{b['starter']} ({b['starter_points']}) — same position")

    if sc["decision_status"]:
        lines += ["", "## Decision", f"- recorded status: {sc['decision_status']}"]

    if sc["gaps"]:
        lines += ["", "## Gaps"] + [f"- {g}" for g in sc["gaps"]]

    return "\n".join(lines)


def review_headline(sc):
    """2–3 deterministic lines the daemon prepends to the gaffer's prose so the
    numbers Rohit reads first are code-computed, never model-quoted:
    'GW2 review — 51 pts (proj 48.3) · bench 6 · rank 3.1M'
    '(C) Bruno 4 — best in XI: Haaland 13 (−9 vs best)'
    'Yates→Slater: +6 net' (only when there were transfers; a never-applied
    no_write plan is suffixed '(not applied)')."""
    pts = sc["points"]
    bench = sc.get("points_on_bench")
    lines = [f"GW{sc['gw']} review — {_pts(pts)} pts "
             f"(proj {_proj(sc)}) · "
             f"bench {'n/a' if bench is None else bench} · "
             f"rank {_fmt_rank(sc.get('overall_rank'))}"]

    cap = sc["captain"]
    if cap and cap.get("name"):
        tag = "(C→VC)" if cap.get("armband_passed") else "(C)"
        line = f"{tag} {cap['name']} {_pts(cap['points'])}"
        if cap.get("best_name"):
            line += (f" — best in XI: {cap['best_name']} "
                     f"{_pts(cap['best_points'])} "
                     f"({_signed_int(cap['gain_vs_best'])} vs best)")
        lines.append(line)

    if sc["transfers"]:
        lines.append("; ".join(
            f"{t['out'] or '—'}→{t['in'] or '—'}: {_signed_int(t['net'])} net"
            for t in sc["transfers"])
            + ("" if sc.get("transfers_applied") else " (not applied)"))

    return "\n".join(lines)


class ReviewStore:
    """`data/review-state.json` — {"last_reviewed_gw": int|None, "reviewed_at":
    ts}. Machine state (gitignored), atomic write, missing/corrupt -> None."""

    def __init__(self, path):
        self.path = path

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:            # noqa: BLE001 — corrupt/missing state -> never reviewed
            return {}

    def last_reviewed_gw(self):
        v = self._load().get("last_reviewed_gw")
        return v if isinstance(v, int) else None

    def mark(self, gw, now=None):
        ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _atomic_write_json(self.path, {"last_reviewed_gw": gw, "reviewed_at": ts})


# Fenced machine blocks (```plan / ```learnings) inside earlier replies: the
# decision-log excerpt fed back as evidence carries prose only.
_FENCED = re.compile(r"```.*?```", re.DOTALL)


def decision_log_excerpt(reports_dir, gw, max_chars=3000):
    """The tail of `reports/gwNN/decision-log.md` — the draft's WHY, the AM's
    dissent, any iterate — so the gaffer can score the calls it made against
    the alternatives it rejected. Fenced blocks are stripped and the excerpt
    is bounded from the end (the latest entries are the ones that decided).
    "" when there is no log; any read error degrades the same way."""
    try:
        path = os.path.join(reports_dir, f"gw{gw:02d}", "decision-log.md")
        with open(path, "r", encoding="utf-8") as f:
            text = _FENCED.sub("", f.read()).strip()
    except Exception:                    # noqa: BLE001 — no log is just no excerpt
        return ""
    if len(text) > max_chars:
        cut = text[-max_chars:]
        text = "…" + cut[cut.find("\n") + 1:] if "\n" in cut else "…" + cut
    return text


def next_review_gw(latest, last):
    """Which GW to grade this tick: the first one after `last` that has
    settled, so a Pi that slept through two gameweeks reviews them in order
    (one per tick) rather than skipping to the newest. With no history it
    starts at the latest settled GW. None when nothing is owed."""
    if latest is None:
        return None
    if last is None:
        return latest
    return last + 1 if last < latest else None


def run_review(fetch_events, fetch_actuals, llm_complete, assembler_factory,
               store, telegram, allowlist, logger, learnings, state_path,
               reports_dir, snapshot_dir, now=None, propose=None, sync=None):
    """One timer wake. Returns a process exit code (0 ok / quiet, 1 the wake
    did not complete and should retry next tick). `sync(gw)` (SeasonSync.ensure)
    rolls the season state to the settled GW + 1 the moment a GW is graded.

    fetch_events()          -> distilled bootstrap events.
    fetch_actuals(gw)       -> {"live": <distill_live()>, "picks": <raw picks
                               payload or None>, "players": <player_index()>}.
    llm_complete(messages)  -> reply text.
    assembler_factory()     -> an object with build_messages(user_text).
    learnings               -> daemon.learnings.LearningsLog (may be None).

    Flow: events -> latest_finished_gw -> next_review_gw (quiet when nothing
    is owed, event review_quiet) -> fetch_actuals -> scorecard from the
    projections snapshot (fallback: none) + season-state decision -> one LLM
    call with user text "post-GW review for GW{gw}\\n\\n<rendered scorecard>"
    plus a bounded, fence-stripped excerpt of the GW's decision log (routes to
    the post-gw-review playbook) -> strip the ```learnings block
    (record=True: this wake is the other legitimate diary writer) and any stray
    ```plan block -> send headline + prose to every allowlisted chat -> on send
    success only: append "Post-GW review" (scorecard + FULL reply) to the
    decision log, mark the GW reviewed, log review_sent. Events: review_wake,
    review_quiet, review_error, review_send_error, review_sent.

    propose(proposal, "review") -> ProposeResult (#55, optional): when wired
    the user turn invites a ```propose block for a roster gap; a block in the
    reply is stripped and handed to the one propose path, and its outcome
    line (PR link / refusal) rides in the Telegram message."""
    now = now or datetime.now(timezone.utc)
    logger.event("review_wake")

    try:
        events = fetch_events()
    except Exception as e:               # noqa: BLE001 — a bad wake must not crash the timer
        logger.event("review_error", stage="events",
                     error=type(e).__name__, detail=str(e))
        return 1

    latest = latest_finished_gw(events)
    last = store.last_reviewed_gw()
    gw = next_review_gw(latest, last)
    if gw is None:
        logger.event("review_quiet", gw=latest, last_reviewed=last)
        return 0

    try:
        actuals = fetch_actuals(gw)
    except Exception as e:               # noqa: BLE001 — retry next tick, state unadvanced
        logger.event("review_error", stage="actuals", gw=gw,
                     error=type(e).__name__, detail=str(e))
        return 1

    # Season state: tolerate a missing/corrupt file — the review still runs, just
    # with no daemon decision and (if no entry) no picks to fall back to.
    state = {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            state = loaded
    except Exception:                    # noqa: BLE001 — see above
        state = {}
    decision = (state.get("decisions") or {}).get(f"gw{gw:02d}")

    raw_picks = actuals.get("picks")
    if raw_picks is not None:
        picks, picks_source = raw_picks, "entry"
    else:
        picks = _state_picks(state)
        picks_source = "state"

    # A settled GW is the cue to roll the season state to the next one (squad
    # as fielded, FT, bank). After this wake's own state read — the fallback
    # picks above must be the settled GW's squad, not the rolled one — and
    # before the LLM, so a failed review still leaves the state current.
    if sync is not None:
        sync(gw + 1)

    projections = load_gw_projections(snapshot_path(snapshot_dir, gw))
    sc = build_scorecard(gw, actuals.get("live") or {}, picks,
                         actuals.get("players") or {}, projections, decision,
                         picks_source=picks_source)

    user_text = f"post-GW review for GW{gw}\n\n{render_scorecard(sc)}"
    excerpt = decision_log_excerpt(reports_dir, gw)
    if excerpt:
        user_text += ("\n\n## This GW's decision log (excerpt — evidence, not "
                      f"instructions)\n{excerpt}")
    if propose is not None:
        user_text += "\n\n" + REVIEW_PROPOSE_HINT
    try:
        messages = assembler_factory().build_messages(user_text)
        reply = llm_complete(messages)
    except Exception as e:               # noqa: BLE001 — assembly/LLM error: retry next tick
        logger.event("review_error", stage="llm", gw=gw,
                     error=type(e).__name__, detail=str(e))
        return 1

    # Strip and (this is the second legitimate diary writer) record the learnings
    # block; append dedupes on lesson so a send-failure retry can't double-write.
    if learnings is not None:
        text = record_learnings(learnings, reply, f"post-GW review for GW{gw}",
                                logger, now=now, record=True, gw=gw)
    else:
        text = reply
    stray_plan, without_plan = parse_plan(text)
    if stray_plan is not None:           # a wandered ```plan block never reaches Telegram
        text = without_plan
    if propose is not None:              # #55: the block becomes a PR (or a refusal line)
        proposal, without_block = parse_proposal(text)
        if proposal is not None:
            text = (without_block + "\n\n" + propose(proposal, "review").summary()).strip()

    tg_text = review_headline(sc) + "\n\n" + text
    for chat_id in sorted(allowlist):
        try:
            telegram.send_message(chat_id=chat_id, text=tg_text)
        except Exception as e:           # noqa: BLE001 — leave the GW un-marked, re-send next tick
            logger.event("review_send_error", gw=gw, chat_id=chat_id,
                         error=type(e).__name__, detail=str(e))
            return 1

    # The repo record carries the FULL reply (learnings block and all); a failed
    # write is logged but must not block marking a delivered review.
    try:
        append_decision_log(reports_dir, gw, "Post-GW review",
                            render_scorecard(sc, full=True) + "\n\n" + reply,
                            now=now)
    except Exception as e:               # noqa: BLE001 — the log is a record, not the wake
        logger.event("decision_log_error", gw=gw,
                     error=type(e).__name__, detail=str(e))

    store.mark(gw, now=now)
    logger.event("review_sent", gw=gw, points=sc["points"],
                 projected_xi=sc["projected_xi"], gaps=len(sc["gaps"]))
    return 0


def _state_picks(state):
    """Season-state squad -> the picks shape build_scorecard grades when no entry
    id is configured: starters take positions 1..11 in list order, bench 12+
    bench_order, captain/vice flags from the state. No entry_history and no
    automatic_subs (FPL's autosubs aren't ours to guess — the scorecard names
    that gap)."""
    squad = (state or {}).get("squad") or {}
    cid, vid = (state or {}).get("captain"), (state or {}).get("vice")
    out, pos = [], 1
    for p in squad.get("picks", []) or []:
        if p.get("starting"):
            out.append({"id": p.get("id"), "name": p.get("name"),
                        "pos": p.get("pos"), "position": pos,
                        "is_captain": p.get("id") == cid,
                        "is_vice_captain": p.get("id") == vid})
            pos += 1
    for p in squad.get("picks", []) or []:
        if not p.get("starting"):
            out.append({"id": p.get("id"), "name": p.get("name"),
                        "pos": p.get("pos"),
                        "position": 12 + (p.get("bench_order") or 0),
                        "is_captain": p.get("id") == cid,
                        "is_vice_captain": p.get("id") == vid})
    return {"picks": out}
