"""The wake->reply loop — the glue above the mockable HTTP edges.

The allowlist check is the first gate: an unknown sender's text never reaches
the model and never draws a reply (replying confirms a live bot — #10 §2).
Every wake, prompt and reply is logged as one structured record for audit.
"""

import time


def process_message(msg, cfg, telegram, llm, logger, assembler=None):
    """Handle one incoming Telegram message. Returns True if a reply was sent.

    When an `assembler` is wired, the system prompt is assembled fresh from the
    workspace + distilled season facts (#16); otherwise the static system prompt
    is used (the #15 walking-skeleton path)."""
    if msg.from_id not in cfg.allowlist:
        # Silent drop, no reply — replying confirms a live bot to a stranger.
        logger.event("drop", reason="not_allowlisted",
                     from_id=msg.from_id, update_id=msg.update_id)
        return False

    logger.event("wake", from_id=msg.from_id, chat_id=msg.chat_id,
                 update_id=msg.update_id, text=msg.text)

    messages = None
    if assembler is not None:
        try:
            messages = assembler.build_messages(msg.text)
        except Exception as e:
            # A broken workspace/state must not mute the bot — fall back to the
            # static prompt so the wake still gets a reply, and log why.
            logger.event("assemble_error", from_id=msg.from_id,
                         error=type(e).__name__, detail=str(e))
    if messages is None:
        messages = [
            {"role": "system", "content": cfg.system_prompt},
            {"role": "user", "content": msg.text},
        ]
    reply = llm.complete(messages)

    logger.event("reply", from_id=msg.from_id, chat_id=msg.chat_id,
                 prompt=msg.text, reply=reply)
    telegram.send_message(msg.chat_id, reply)
    return True


def poll_once(cfg, telegram, llm, logger, offset, assembler=None):
    """One long-poll cycle. Returns the next offset to request."""
    for msg in telegram.get_updates(offset):
        try:
            process_message(msg, cfg, telegram, llm, logger, assembler=assembler)
        except Exception as e:  # one bad message must not kill the daemon
            logger.event("error", from_id=getattr(msg, "from_id", None),
                         error=type(e).__name__, detail=str(e))
        offset = max(offset, msg.update_id + 1)
    return offset


def run(cfg, telegram, llm, logger, should_continue=lambda: True, idle_sleep=1.0,
        assembler=None):
    """Resident loop: long-poll Telegram forever, waking on each message."""
    offset = 0
    logger.event("startup", model=cfg.model, allowlist_size=len(cfg.allowlist))
    while should_continue():
        try:
            offset = poll_once(cfg, telegram, llm, logger, offset, assembler=assembler)
        except Exception as e:  # network blip — log and keep cycling
            logger.event("poll_error", error=type(e).__name__, detail=str(e))
            time.sleep(idle_sleep)
