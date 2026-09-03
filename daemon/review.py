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
from datetime import datetime, timezone

from daemon.learnings import record_learnings
from daemon.plan import append_decision_log, parse_plan
from daemon.prompt import normalize_name

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
    picks       : the fielded 15 as [{"id", "position" (1..15), "multiplier",
                   "is_captain", "is_vice_captain"}] plus optional
                   "entry_history" {"points", "points_on_bench", "rank",
                   "overall_rank", "event_transfers", "event_transfers_cost",
                   "bank"} — i.e. {"picks": [...], "entry_history": {...}}.
                   May be None when no entry id is configured; then the caller
                   passes the season-state squad shaped the same way
                   (multiplier 2 for the state captain, position from
                   starting/bench_order) and picks_source="state".
    players     : {int element id: {"web_name", "pos", "team"}} from the
                   distilled bootstrap (fpl_api.player_index()).
    projections : load_gw_projections() result (may be empty maps).
    decision    : season-state decisions.gwNN dict {"plan", "status",
                   "recorded_at"} or None.

    Returns a dict with (all optional fields None/[] when the data is missing,
    and every gap named in "gaps"):
      gw, points, points_on_bench, overall_rank, gw_rank, transfers_made,
      transfers_cost, picks_source,
      projected_xi (sum xpts over starters, captain doubled, over matched
        players only), matched (n matched / n starters), actual_xi (sum of
        points * multiplier over starters — equals `points` when entry data
        is present),
      rows: [{"name","pos","starter","multiplier","proj","actual","minutes",
              "delta"}] for all 15, sorted by |delta| desc (None deltas last),
      misses: {"under": top TOP_MISSES rows with actual < proj,
               "over":  top TOP_MISSES rows with actual > proj},
      captain: {"name","points","vice_name","vice_points",
                "best_name","best_points","gain_vs_best"} (points = raw GW pts
                of that player; best = highest raw pts among starters),
      plan_captain: the decision plan's captain when it differs from the
                fielded one (an override happened in the app) else None,
      transfers: [{"out","in","out_points","in_points","net"}] from the
                decision plan pairs (net = in - out; the hit is applied once
                in "transfers_net" = sum(net) - hits),
      transfers_net, hits,
      bench_calls: [{"bench","bench_points","starter","starter_points"}] for
                each bench player who outscored a starter of the same position,
      decision_status: "locked" | "no_write" | None,
      gaps: [str] e.g. "no projections snapshot for GW2", "no daemon decision
            recorded for GW2 (ad-hoc gameweek)", "picks from season state (no
            entry id) — autosubs not applied".

    Ids in `picks` may be synthetic (season-state before pull-squad); resolve
    each pick to a real element via `players` by id when present, else by
    (normalize_name(name), pos)."""
    live = live or {}
    players = players or {}
    projections = projections or {"by_id": {}, "by_name": {}}
    by_id = projections.get("by_id") or {}
    by_name = projections.get("by_name") or {}
    plan = decision.get("plan") if decision else None

    # Name join tables over the bootstrap: position-scoped (pick resolution and
    # projection-by-name) and position-agnostic (transfer-name -> live points).
    name_pos, name_any = {}, {}
    for pid, info in players.items():
        nn = normalize_name((info or {}).get("web_name"))
        if nn:
            name_pos.setdefault((nn, (info or {}).get("pos")), pid)
            name_any.setdefault(nn, pid)

    def _name_points(name):
        if not name:
            return None
        pid = name_any.get(normalize_name(name))
        if pid is None:
            return None
        return (live.get(pid) or {}).get("total_points")

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
        starter = isinstance(position, int) and 1 <= position <= 11
        mult = pick.get("multiplier")
        if mult is None:
            mult = 1 if starter else 0

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
            "name": name, "pos": pos, "starter": starter, "multiplier": mult,
            "proj": proj, "actual": actual, "minutes": minutes, "delta": delta,
            "position": position, "is_captain": bool(pick.get("is_captain")),
            "is_vice": bool(pick.get("is_vice_captain")), "id": rid})

    def _row(b):
        return {k: b[k] for k in ("name", "pos", "starter", "multiplier",
                                  "proj", "actual", "minutes", "delta")}

    starters = [b for b in built if b["starter"]]
    actual_xi = sum(b["actual"] * b["multiplier"] for b in starters
                    if b["actual"] is not None)
    projected_xi = sum(b["proj"] * (b["multiplier"] if b["multiplier"] > 1 else 1)
                       for b in starters if b["proj"] is not None)
    matched = (sum(1 for b in starters if b["proj"] is not None), len(starters))

    eh = (picks or {}).get("entry_history") or {}
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

    # Captain grade: raw (un-multiplied) points; best-in-XI keeps the captain on
    # a tie so a captain who tied the top scorer shows a 0 gain, not a phantom loss.
    cap = next((b for b in built if b["is_captain"]), None)
    vice = next((b for b in built if b["is_vice"]), None)
    best_b, best_val = None, None
    for b in starters:
        if b["actual"] is not None and (best_val is None or b["actual"] > best_val):
            best_b, best_val = b, b["actual"]
    if cap and cap["actual"] is not None and cap["actual"] == best_val:
        best_b = cap
    cap_pts = cap["actual"] if cap else None
    gain = ((cap_pts - best_val) * 2
            if (cap_pts is not None and best_val is not None) else None)
    captain = {
        "name": cap["name"] if cap else None, "points": cap_pts,
        "vice_name": vice["name"] if vice else None,
        "vice_points": vice["actual"] if vice else None,
        "best_name": best_b["name"] if best_b else None,
        "best_points": best_val, "gain_vs_best": gain}

    plan_captain = None
    if plan and plan.get("captain") and cap and cap["name"]:
        if (normalize_name(plan["captain"]).casefold()
                != normalize_name(cap["name"]).casefold()):
            plan_captain = plan["captain"]

    # Transfers: plan pairs (short side padded), each side priced from live by name.
    transfers, transfers_net, hits = [], None, (plan.get("hits") if plan else 0) or 0
    if plan:
        ti = plan.get("transfers_in") or []
        to = plan.get("transfers_out") or []
        for i in range(max(len(ti), len(to))):
            out_name = to[i] if i < len(to) else None
            in_name = ti[i] if i < len(ti) else None
            op, ip = _name_points(out_name), _name_points(in_name)
            net = (ip - op) if (ip is not None and op is not None) else None
            transfers.append({"out": out_name, "in": in_name,
                              "out_points": op, "in_points": ip, "net": net})
        if transfers:
            transfers_net = sum(t["net"] for t in transfers
                                if t["net"] is not None) - hits

    # Bench calls: a bench player who outscored a same-position starter names the
    # LOWEST-scoring starter he could have replaced.
    bench_calls = []
    for b in built:
        if not (isinstance(b["position"], int) and 12 <= b["position"] <= 15):
            continue
        if b["actual"] is None:
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
        "picks_source": picks_source, "projected_xi": projected_xi,
        "matched": matched, "actual_xi": actual_xi, "rows": rows, "misses": misses,
        "captain": captain, "plan_captain": plan_captain, "transfers": transfers,
        "transfers_net": transfers_net, "hits": hits, "bench_calls": bench_calls,
        "decision_status": (decision.get("status") if decision else None),
        "gaps": gaps}


def render_scorecard(sc):
    """The scorecard as distilled markdown for the prompt — headline numbers,
    the top misses, captain/transfer/bench grades, decision status, and the
    gaps spelled out. Never json.dumps (invariant #9/#10). Bounded: at most
    2*TOP_MISSES player lines plus the grades."""
    m, n = sc["matched"]
    pts = sc["points"]
    head = (f"GW{sc['gw']} scorecard — {_pts(pts)} pts "
            f"(proj {_proj(sc)}, {m}/{n} matched)")
    if sc.get("points_on_bench") is not None:
        head += f" · bench {sc['points_on_bench']}"
    if sc.get("overall_rank") is not None:
        head += f" · rank {_fmt_rank(sc['overall_rank'])}"
    lines = [head]

    def _miss(r):
        return (f"- {r['name']} ({r['pos']}) proj {r['proj']:.1f} → "
                f"actual {r['actual']} ({_signed(r['delta'])})")

    misses = sc["misses"]
    if misses["under"] or misses["over"]:
        lines += ["", "## Biggest misses"]
        lines += [_miss(r) for r in misses["under"]]
        lines += [_miss(r) for r in misses["over"]]

    cap = sc["captain"]
    cap_lines = []
    if cap and cap.get("name"):
        cap_lines.append(f"- (C) {cap['name']}: {_pts(cap['points'])} pts")
        if cap.get("vice_name"):
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
        lines += ["", "## Transfers"]
        for t in sc["transfers"]:
            lines.append(
                f"- {t['out'] or '—'} ({_pts(t['out_points'])}) → "
                f"{t['in'] or '—'} ({_pts(t['in_points'])}) = "
                f"net {_signed_int(t['net'])}")
        if sc["transfers_net"] is not None:
            lines.append(f"- net after −{sc['hits']} hit: "
                         f"{_signed_int(sc['transfers_net'])}")

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
    '(C) Bruno 4 — best in XI: Haaland 13 (−18 vs best)'
    'Yates→Slater: +6 net' (only when there were transfers)."""
    pts = sc["points"]
    bench = sc.get("points_on_bench")
    lines = [f"GW{sc['gw']} review — {_pts(pts)} pts "
             f"(proj {_proj(sc)}) · "
             f"bench {'n/a' if bench is None else bench} · "
             f"rank {_fmt_rank(sc.get('overall_rank'))}"]

    cap = sc["captain"]
    if cap and cap.get("name"):
        line = f"(C) {cap['name']} {_pts(cap['points'])}"
        if cap.get("best_name"):
            line += (f" — best in XI: {cap['best_name']} "
                     f"{_pts(cap['best_points'])} "
                     f"({_signed_int(cap['gain_vs_best'])} vs best)")
        lines.append(line)

    if sc["transfers"]:
        lines.append("; ".join(
            f"{t['out'] or '—'}→{t['in'] or '—'}: {_signed_int(t['net'])} net"
            for t in sc["transfers"]))

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
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"last_reviewed_gw": gw, "reviewed_at": ts}, f)
        os.replace(tmp, self.path)


def run_review(fetch_events, fetch_actuals, llm_complete, assembler_factory,
               store, telegram, allowlist, logger, learnings, state_path,
               reports_dir, snapshot_dir, entry_id=None, now=None):
    """One timer wake. Returns a process exit code (0 ok / quiet, 1 the wake
    did not complete and should retry next tick).

    fetch_events()          -> distilled bootstrap events.
    fetch_actuals(gw)       -> {"live": <distill_live()>, "picks": <raw picks
                               payload or None>, "players": <player_index()>}.
    llm_complete(messages)  -> reply text.
    assembler_factory()     -> an object with build_messages(user_text).
    learnings               -> daemon.learnings.LearningsLog (may be None).

    Flow: events -> latest_finished_gw -> quiet if None or <= store's last
    reviewed (event review_quiet) -> fetch_actuals -> scorecard from the
    projections snapshot (fallback: none) + season-state decision -> one LLM
    call with user text "post-GW review for GW{gw}\\n\\n<rendered scorecard>"
    (routes to the post-gw-review playbook) -> strip the ```learnings block
    (record=True: this wake is the other legitimate diary writer) and any stray
    ```plan block -> send headline + prose to every allowlisted chat -> on send
    success only: append "Post-GW review" (scorecard + FULL reply) to the
    decision log, mark the GW reviewed, log review_sent. Events: review_wake,
    review_quiet, review_error, review_send_error, review_sent."""
    now = now or datetime.now(timezone.utc)
    logger.event("review_wake")

    try:
        events = fetch_events()
    except Exception as e:               # noqa: BLE001 — a bad wake must not crash the timer
        logger.event("review_error", stage="events",
                     error=type(e).__name__, detail=str(e))
        return 1

    gw = latest_finished_gw(events)
    last = store.last_reviewed_gw()
    if gw is None or (last is not None and gw <= last):
        logger.event("review_quiet", gw=gw, last_reviewed=last)
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

    projections = load_gw_projections(snapshot_path(snapshot_dir, gw))
    sc = build_scorecard(gw, actuals.get("live") or {}, picks,
                         actuals.get("players") or {}, projections, decision,
                         picks_source=picks_source)

    user_text = f"post-GW review for GW{gw}\n\n{render_scorecard(sc)}"
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
                                logger, now=now, record=True)
    else:
        text = reply
    stray_plan, text2 = parse_plan(text)
    if stray_plan is not None:           # a wandered ```plan block never reaches Telegram
        text = text2

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
                            render_scorecard(sc) + "\n\n" + reply, now=now)
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
    bench_order, the state captain a 2× multiplier and the vice its flag. No
    entry_history (autosubs and the official points aren't ours to compute)."""
    squad = (state or {}).get("squad") or {}
    cid, vid = (state or {}).get("captain"), (state or {}).get("vice")
    out, pos = [], 1
    for p in squad.get("picks", []) or []:
        if p.get("starting"):
            out.append({"id": p.get("id"), "name": p.get("name"),
                        "pos": p.get("pos"), "position": pos,
                        "multiplier": 2 if p.get("id") == cid else 1,
                        "is_captain": p.get("id") == cid,
                        "is_vice_captain": p.get("id") == vid})
            pos += 1
    for p in squad.get("picks", []) or []:
        if not p.get("starting"):
            out.append({"id": p.get("id"), "name": p.get("name"),
                        "pos": p.get("pos"),
                        "position": 12 + (p.get("bench_order") or 0),
                        "multiplier": 0,
                        "is_captain": p.get("id") == cid,
                        "is_vice_captain": p.get("id") == vid})
    return {"picks": out}
