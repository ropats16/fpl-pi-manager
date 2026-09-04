"""The wake->reply loop — the glue above the mockable HTTP edges.

The allowlist check is the first gate: an unknown sender's text never reaches
the model and never draws a reply (replying confirms a live bot — #10 §2).
Every wake, prompt and reply is logged as one structured record for audit.

When an `approvals` gate is wired (#18), the approve/stop tokens are matched in
DAEMON CODE before the LLM is ever consulted: an exact `yes` while a plan is
AWAITING flips the write gate with no model call, and an iterate (a reply that
carries a fresh ```plan``` block) carry-voids the snapshot so a new `yes` is
required. Everything else — `yes but…`, `why?`, plain chat — routes to the model
as debate, grounded on the pending/approved plan via the assembler.

When a `learnings` diary is wired (#20), the reply's ```learnings block is the
second machine block the loop strips: it is vetted and appended before the plan
parse runs, so both blocks are gone by the time Telegram sees the text.
"""

import time

from daemon.learnings import record_learnings
from daemon.prompt import select_playbook
from daemon.plan import (append_decision_log, is_approval, is_stop, parse_plan,
                         plan_summary)
from daemon.propose import PROPOSE_HINT, is_propose_request, parse_proposal


def process_message(msg, cfg, telegram, llm, logger, assembler=None,
                    approvals=None, learnings=None, proposer=None):
    """Handle one incoming Telegram message. Returns True if a reply was sent.

    When an `assembler` is wired, the system prompt is assembled fresh from the
    workspace + distilled season facts (#16); otherwise the static system prompt
    is used (the #15 walking-skeleton path). When an `approvals` gate is wired,
    the deterministic approve/stop path runs before any LLM call (#18). When a
    `learnings` log is wired, an analysis reply's learnings block is vetted and
    recorded, and the block stripped, before anything else touches the text
    (#20). The other diary writer is the #21 review WAKE (daemon.review), never
    a chat reply — a chat "how did I do?" has no code-computed scorecard to
    ground a lesson on. When a `proposer` is wired (#55), a `propose role: X`
    request carries the block format into the user turn, and any reply's
    ```propose block is stripped and handed to the one propose path — the
    result line (PR link / refusal) rides in the reply."""
    if msg.from_id not in cfg.allowlist:
        # Silent drop, no reply — replying confirms a live bot to a stranger.
        logger.event("drop", reason="not_allowlisted",
                     from_id=msg.from_id, update_id=msg.update_id)
        return False

    logger.event("wake", from_id=msg.from_id, chat_id=msg.chat_id,
                 update_id=msg.update_id, text=msg.text)

    st = approvals.store.load() if approvals is not None else None

    # --- deterministic approval gate (#18) — daemon code, never the model ------
    if st is not None:
        if is_approval(msg.text):
            if st.phase == "awaiting_approval" and st.pending_plan:
                approvals.store.approve()
                logger.event("approve", gw=st.gw)
                receipt = (f"✅ GW{st.gw} plan approved — locking at T−30m unless "
                           f"news voids it. {plan_summary(st.pending_plan)}")
                telegram.send_message(msg.chat_id, receipt)
                return True
            # A bare `yes` with nothing pending is just chat -> fall through.
        elif is_stop(msg.text) and st.phase == "locked":
            # STOP holds the lock: the approved plan reverts to pending, awaiting
            # a fresh yes (§3⑤ opt-out). No model call.
            approvals.store.pending_plan = st.approved_plan
            approvals.store.approved_plan = None
            approvals.store.phase = "awaiting_approval"
            approvals.store.save()
            logger.event("stop", gw=st.gw)
            telegram.send_message(msg.chat_id, "⏸ hold — awaiting fresh yes")
            return True

    # --- debate / iterate / chat -> the model ---------------------------------
    user_text = msg.text
    if proposer is not None and is_propose_request(msg.text):
        user_text = msg.text + "\n\n" + PROPOSE_HINT
    messages = None
    if assembler is not None:
        try:
            messages = assembler.build_messages(user_text)
        except Exception as e:
            # A broken workspace/state must not mute the bot — fall back to the
            # static prompt so the wake still gets a reply, and log why.
            logger.event("assemble_error", from_id=msg.from_id,
                         error=type(e).__name__, detail=str(e))
    if messages is None:
        messages = [
            {"role": "system", "content": cfg.system_prompt},
            {"role": "user", "content": user_text},
        ]
    reply = llm.complete(messages)

    # The learnings diary (#20) reads the RAW reply and hands back the text with
    # its own machine block removed. Only a question that routed to the analysis
    # playbook may WRITE from chat — any other reply carrying a block is stripped
    # and logged, so a poisoned report can't coach a squad-review answer into
    # memory (the #21 review wake writes on its own, scorecard-grounded path).
    # It runs before the plan parse so a reply carrying both blocks loses both;
    # the decision log below still records the full `reply`, because the repo
    # record wants what the gaffer actually said.
    answer = reply
    if learnings is not None:
        answer = record_learnings(learnings, reply, msg.text, logger,
                                  record=select_playbook(msg.text) == "analysis")

    send_text = answer
    # An iterate is a debate reply that re-emits a full plan block: it becomes
    # the new pending snapshot (fresh yes required) and the machine block is
    # stripped before Telegram (§3② — the block never reaches the human).
    if st is not None and st.phase in ("awaiting_approval", "approved", "locked"):
        plan, stripped = parse_plan(answer)
        if plan is not None:
            approvals.store.void_carry(plan)
            logger.event("iterate", gw=st.gw)
            send_text = stripped
            if approvals.reports_dir and st.gw is not None:
                # The full revised brief — the gaffer's dissent on a complied
                # `change X` included — is the repo record §3④ scores post-GW.
                try:
                    append_decision_log(approvals.reports_dir, st.gw,
                                        "Iterate (revised plan)", reply)
                except Exception as e:   # noqa: BLE001 — a log write never mutes a reply
                    logger.event("decision_log_error", gw=st.gw,
                                 error=type(e).__name__, detail=str(e))

    # A role proposal (#55): the block never reaches Telegram; the outcome
    # line does. The path itself never raises (refused/failed are results).
    if proposer is not None:
        proposal, without = parse_proposal(send_text)
        if proposal is not None:
            send_text = (without + "\n\n" + proposer(proposal, "chat").summary()).strip()

    logger.event("reply", from_id=msg.from_id, chat_id=msg.chat_id,
                 prompt=msg.text, reply=send_text)
    telegram.send_message(msg.chat_id, send_text)
    return True


def poll_once(cfg, telegram, llm, logger, offset, assembler=None, approvals=None,
              learnings=None, proposer=None):
    """One long-poll cycle. Returns the next offset to request."""
    for msg in telegram.get_updates(offset):
        try:
            process_message(msg, cfg, telegram, llm, logger, assembler=assembler,
                            approvals=approvals, learnings=learnings,
                            proposer=proposer)
        except Exception as e:  # one bad message must not kill the daemon
            logger.event("error", from_id=getattr(msg, "from_id", None),
                         error=type(e).__name__, detail=str(e))
        offset = max(offset, msg.update_id + 1)
    return offset


def run(cfg, telegram, llm, logger, should_continue=lambda: True, idle_sleep=1.0,
        assembler=None, approvals=None, learnings=None, proposer=None):
    """Resident loop: long-poll Telegram forever, waking on each message."""
    offset = 0
    logger.event("startup", model=cfg.model, allowlist_size=len(cfg.allowlist))
    while should_continue():
        try:
            offset = poll_once(cfg, telegram, llm, logger, offset,
                               assembler=assembler, approvals=approvals,
                               learnings=learnings, proposer=proposer)
        except Exception as e:  # network blip — log and keep cycling
            logger.event("poll_error", error=type(e).__name__, detail=str(e))
            time.sleep(idle_sleep)
