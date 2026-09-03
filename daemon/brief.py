"""The timer-driven deadline brief wake (#18) — mirrors the #17 watch shape:
the systemd timer wakes this hourly, it does a cheap clock check against the next
FPL deadline, and only spends LLM tokens inside the draft / final windows.

Two approval-bearing touchpoints per GW (weekly-cycle.md §1): a leisurely DRAFT
in Rohit's IST evening (~24–48h out) that opens the approve/debate/iterate
window, and a T−2h FINAL checkpoint that re-decides and diffs against the
approved snapshot. At T−30m the daemon acts — but only on an explicit approval:
an unapproved deadline is a loud no-write, never an autonomous change.

Same never-lose-a-wake posture as the watch: a fetch/LLM error logs and returns
non-zero with state UNadvanced (the next hourly tick retries); a Telegram send
failure does not mark the touchpoint sent, so it re-sends next tick. Silence
(outside every window) is the default and costs zero tokens.
"""

import json
from datetime import datetime, timedelta, timezone

from daemon.plan import (append_decision_log, parse_plan, plan_summary,
                         plans_differ, record_decision)
from daemon.prompt import estimate_tokens
from daemon.review import snapshot_path, snapshot_projections

IST = timezone(timedelta(hours=5, minutes=30))


def _parse_dt(s):
    """FPL deadline_time ('2026-08-29T11:00:00Z') -> aware UTC datetime.
    stdlib fromisoformat needs the 'Z' spelled as an offset before 3.11."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def next_deadline(events, now_utc):
    """(gw_id, deadline datetime) of the earliest unfinished event whose deadline
    is still in the future; None if no future deadline. Fed the distilled
    bootstrap events (id, deadline_time, finished, is_next)."""
    best = None
    for e in events:
        if e.get("finished"):
            continue
        raw = e.get("deadline_time")
        if not raw:
            continue
        dt = _parse_dt(raw)
        if dt > now_utc and (best is None or dt < best[1]):
            best = (e.get("id"), dt)
    return best


def decide_wake(now_utc, deadline_utc, st):
    """One of None | 'draft' | 'final' | 'act' for this tick (weekly-cycle.md §1).

    - act  : T−30m..deadline, unless already acted/no-write.
    - final: T−2h..T−30m, once (not final_sent). draft_sent OR the draft window
             is by-now missed both satisfy the "a brief precedes the final" rule
             — inside the final window the draft window is always past, so this
             reduces to "send the final if it has not gone yet".
    - draft: within 48h and not yet sent, if now is in Rohit's evening IST window
             (18:00–23:00) OR the deadline is within 24h (the missed-evening
             fallback that guarantees a brief always precedes the final).
    - None : after the deadline, or any tick outside a live window.
    """
    if now_utc >= deadline_utc:
        return None
    to_deadline = deadline_utc - now_utc

    if to_deadline <= timedelta(minutes=30):
        return "act" if st.phase not in ("acted", "no_write") else None

    if to_deadline <= timedelta(hours=2):
        if not st.final_sent and st.phase not in ("acted", "no_write"):
            return "final"
        return None

    if to_deadline <= timedelta(hours=48) and not st.draft_sent:
        evening = 18 <= now_utc.astimezone(IST).hour < 23
        if evening or to_deadline <= timedelta(hours=24):
            return "draft"
    return None


def _send_all(telegram, allowlist, text, logger, gw):
    """Send one text to every allowlisted chat. Returns False (and logs) on the
    first failure so the caller can leave the touchpoint un-marked and retry."""
    for chat_id in sorted(allowlist):
        try:
            telegram.send_message(chat_id=chat_id, text=text)
        except Exception as e:           # noqa: BLE001 — retry next tick, never crash
            logger.event("brief_send_error", gw=gw, chat_id=chat_id,
                         error=type(e).__name__, detail=str(e))
            return False
    return True


def _generate(assembler_factory, llm_complete, user_text):
    """Assemble a fresh grounded prompt and get one LLM reply. The assembler is
    built per-call so a pulled markdown/state change applies to this wake (#7)."""
    messages = assembler_factory().build_messages(user_text)
    return llm_complete(messages), messages


def _generate_plan(llm_complete, assembler_factory, user_text, logger, gw):
    """Generate a brief and parse its machine block, retrying ONCE with an
    explicit re-emit instruction. Returns (plan|None, stripped_text, full_reply)
    — a model that drops the block must never leave the protocol snapshotless
    without a logged trail (draft) or silently void an approval (final)."""
    reply, messages = _generate(assembler_factory, llm_complete, user_text)
    plan, text = parse_plan(reply)
    if plan is None:
        logger.event("brief_plan_missing", gw=gw, attempt=1)
        messages = list(messages) + [{
            "role": "user",
            "content": ("You did not end with the required ```plan JSON block. "
                        "Re-emit the FULL brief and end it with the plan block."),
        }]
        reply = llm_complete(messages)
        plan, text = parse_plan(reply)
        if plan is None:
            logger.event("brief_plan_missing", gw=gw, attempt=2)
            text = reply
    return plan, text, reply


def _snapshot(projections_path, snapshot_dir, gw, logger):
    """Freeze the GW's projection rows so the post-GW review (#21) can grade the
    call against exactly what it was made on. Draft writes the first copy; the
    final and act overwrite it with the copy closest to the deadline. Best-effort: with either
    path unset it does nothing (no event); any error logs brief_projections_error
    and never blocks the brief."""
    if not (projections_path and snapshot_dir):
        return
    try:
        out_path = snapshot_path(snapshot_dir, gw)
        rows = snapshot_projections(projections_path, gw, out_path)
        logger.event("brief_projections_snapshot", gw=gw, rows=rows, path=out_path)
    except Exception as e:               # noqa: BLE001 — a snapshot never blocks a brief
        logger.event("brief_projections_error", gw=gw,
                     error=type(e).__name__, detail=str(e))


def _do_draft(llm_complete, assembler_factory, store, telegram, allowlist,
              logger, gw, reports_dir, now, projections_path=None,
              snapshot_dir=None):
    # If the block is missing even after the retry, the brief still goes out;
    # pending stays None so a `yes` can't approve half a protocol.
    plan, text, reply = _generate_plan(
        llm_complete, assembler_factory,
        f"produce the GW{gw} draft deadline brief", logger, gw)

    if not _send_all(telegram, allowlist, text, logger, gw):
        return 1
    store.set_pending(gw, plan)          # plan may be None (no usable block)
    store.draft_sent = True
    store.save()
    # The FULL reply (plan block and all) is the repo record (§2); the lean
    # stripped text is what went to Telegram.
    append_decision_log(reports_dir, gw, "Deadline brief", reply, now=now)
    # The send is out: freeze the projections the review will grade this call on.
    _snapshot(projections_path, snapshot_dir, gw, logger)
    logger.event("brief_draft_sent", gw=gw, tokens=estimate_tokens(reply),
                 has_plan=plan is not None)
    return 0


def _do_final(llm_complete, assembler_factory, store, telegram, allowlist,
              logger, gw, projections_path=None, snapshot_dir=None):
    new_plan, text, _ = _generate_plan(
        llm_complete, assembler_factory,
        f"final pre-deadline check for GW{gw}", logger, gw)
    approved = store.approved_plan
    has_chip = bool(new_plan and new_plan.get("chip"))
    # The final is where the last real decision is made: freeze the projections
    # it was made on (act overwrites again at T−30m only if they moved).
    _snapshot(projections_path, snapshot_dir, gw, logger)

    if new_plan is None:
        # Unverifiable final: no machine plan even after a retry. The carry-void
        # diff (§3③) cannot run, so nothing may auto-lock — but the message must
        # name the recovery path: without it, "fresh yes required" points at a
        # `yes` that can't approve (pending is None) 2h before the deadline.
        msg = (f"⚠ GW{gw} FINAL — no machine plan came back, so the approved "
               "plan can't be verified and will NOT auto-lock. Ask me to "
               "re-issue the plan, then reply yes.")
        if not _send_all(telegram, allowlist, msg, logger, gw):
            return 1
        store.void_carry(None)
        store.final_sent = True
        store.save()
        logger.event("brief_final_sent", gw=gw, changed=True, has_plan=False)
        return 0

    unchanged = (approved is not None and new_plan is not None
                 and not plans_differ(new_plan, approved) and not has_chip)
    if unchanged:
        msg = (f"GW{gw} FINAL — no change since your yes. Locking at T−30m. "
               "Reply STOP to hold.")
        if not _send_all(telegram, allowlist, msg, logger, gw):
            return 1
        store.phase = "locked"
        store.final_sent = True
        store.save()
        logger.event("brief_final_sent", gw=gw, changed=False)
        return 0

    # Changed, chip present, or nothing approved -> carry-void, fresh yes needed.
    marker = ("chip plan — fresh yes required" if has_chip
              else f"⚠ GW{gw} CHANGED — fresh yes required")
    if not _send_all(telegram, allowlist, f"{marker}\n\n{text}", logger, gw):
        return 1
    store.void_carry(new_plan)
    store.final_sent = True
    store.save()
    logger.event("brief_final_sent", gw=gw, changed=True)
    return 0


def _state_captain(state_path):
    """The current captain's name from season state, for the no-write alert
    (§3⑤ names the standing captain: '(C)=X'). Any read problem -> None — the
    alert must fire regardless."""
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        cid = state.get("captain")
        for p in state.get("squad", {}).get("picks", []):
            if p.get("id") == cid:
                return p.get("name")
    except Exception:                    # noqa: BLE001 — cosmetic, never blocking
        pass
    return None


def _do_act(store, telegram, allowlist, logger, actuator, state_path, gw, now,
            projections_path=None, snapshot_dir=None):
    approved = store.approved_plan
    if store.phase in ("approved", "locked") and approved is not None:
        instructions = actuator.apply(approved, gw)
        record_decision(state_path, gw, approved, "locked", now=now)
        receipt = f"✅ GW{gw} locked: {plan_summary(approved)}"
        # Overwrite the draft's snapshot with the copy closest to the deadline —
        # the projections this locked call is actually being graded on (#21).
        _snapshot(projections_path, snapshot_dir, gw, logger)
        if not _send_all(telegram, allowlist, f"{instructions}\n\n{receipt}",
                         logger, gw):
            return 1
        store.phase = "acted"
        store.save()
        logger.event("brief_acted", gw=gw)
        return 0

    # No valid approval at the act-moment: NO actuator call (§3⑤ no-write).
    record_decision(state_path, gw, approved, "no_write", now=now)
    cap = _state_captain(state_path)
    msg = (f"⚠ GW{gw} locked with NO changes — no approval in time. "
           f"Last team stands{f', (C) {cap}' if cap else ''}, FT banks.")
    # A no-write still fielded a team; snapshot the projections it stood on (#21).
    _snapshot(projections_path, snapshot_dir, gw, logger)
    if not _send_all(telegram, allowlist, msg, logger, gw):
        return 1
    store.phase = "no_write"
    store.save()
    logger.event("brief_no_write", gw=gw)
    return 0


def run_brief(fetch, llm_complete, assembler_factory, store, telegram, allowlist,
              logger, actuator, state_path, reports_dir, projections_path=None,
              snapshot_dir=None, now=None):
    """One hourly wake. Returns a process exit code (0 ok, 1 the wake did not
    complete). Every external edge is injected so the whole path runs offline in
    tests — same seam posture as run_watch (#17).

    When both `projections_path` and `snapshot_dir` are set, the draft and act
    touchpoints freeze the GW's projection rows into
    `<snapshot_dir>/projections-gwNN.csv` so the post-GW review (#21) can grade
    the call against exactly what it was made on; a snapshot failure is logged,
    never fatal."""
    now = now or datetime.now(timezone.utc)
    logger.event("brief_wake")
    try:
        events = fetch()
    except Exception as e:               # noqa: BLE001 — a bad wake must not crash the timer
        logger.event("brief_error", error=type(e).__name__, detail=str(e))
        return 1

    nd = next_deadline(events, now)
    if nd is None:
        logger.event("brief_quiet", reason="no_deadline")
        return 0
    gw, deadline = nd

    st = store.load()
    if st.gw != gw:                      # a new deadline cycle — clean idle state
        store.reset_for(gw)
        st = store

    action = decide_wake(now, deadline, st)
    if action is None:
        logger.event("brief_quiet", gw=gw, phase=st.phase)
        return 0

    try:
        if action == "draft":
            return _do_draft(llm_complete, assembler_factory, store, telegram,
                             allowlist, logger, gw, reports_dir, now,
                             projections_path=projections_path,
                             snapshot_dir=snapshot_dir)
        if action == "final":
            return _do_final(llm_complete, assembler_factory, store, telegram,
                             allowlist, logger, gw,
                             projections_path=projections_path,
                             snapshot_dir=snapshot_dir)
        return _do_act(store, telegram, allowlist, logger, actuator, state_path,
                       gw, now, projections_path=projections_path,
                       snapshot_dir=snapshot_dir)
    except Exception as e:               # noqa: BLE001 — LLM/state error: retry next tick
        # State is not advanced past this point on the failing action, so the
        # next hourly tick re-attempts the same window (never lose a wake).
        logger.event("brief_error", gw=gw, action=action,
                     error=type(e).__name__, detail=str(e))
        return 1
