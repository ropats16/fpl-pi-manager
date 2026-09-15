# Chat caps, safety net, progress pings, approval buttons (spec, 2026-09-15)

Decided with Rohit 2026-09-15. Trigger: two chats (13/14 Sep) came back as
`(the assistant reached a limit before it produced a reply)`. Journal shows
both were `cap_hit:minutes` on the 6-min chat loop: the gaffer's first turn
asked two staff seats, each ask ran 5–8 min (its own 4-min ceiling plus the
write-up), so the loop was over 6 min before the gaffer got a second turn, and
the gaffer had written no text yet. The chat loop also never logs its own cap.

## 0. Decisions (locked)

- Chunk, don't poll: no background helpers, no "check progress" tool. The gaffer
  asks narrow questions and asks again (prompt line in `GAFFER.md`).
- Caps are the safety. A longer ceiling is a ceiling, not a target.
- Button presses go through the SAME allowlist and the SAME approve/stop code
  path as typed `yes`/`stop`. Only those two callback payloads are accepted;
  anything else is dropped and logged. This is the one loosening of the
  "plain 1:1 messages only" rule (#10 §2).
- Merge stays human; one PR.

## 1. Caps

| | today | new |
|---|---|---|
| chat turns / minutes / cost (`config.DEFAULT_CHAT_CAPS`) | 12 / 6 / $0.40 | 40 / 60 / $1.50 |
| ask: turns / minutes / searches / fetches (`__main__.ASK_HELPER_CAPS`) | 10 / 4 / 3 / 5 | 10 / 12 / 6 / 10 |
| `ask_helper` calls per chat (`gaffer_tools`) | 2 | 6 |

Env overrides unchanged (`GAFFER_CHAT_MAX_*`). Six asks × 12 min can exceed
60 min; the chat cap plus §2 covers that.

`run_agent` logs `agent_cap_hit` (`role, status, turns, cost_usd`) whenever it
ends on a cap, so the chat loop's ceilings are visible in the journal like the
helpers' `cap_hit` already is.

## 2. Safety net (final no-tools turn)

`run_agent(..., finish_on_cap=None)`: an optional prompt string. When set and
the loop ends on `cap_hit:*` or `error` with at least one tool turn behind it
and no final text, the loop appends that prompt as a user turn and makes ONE
more `llm.chat` with no tools. Non-empty content becomes `reply`; `status`
keeps the cap name (truth in the log). A failed final turn falls back to the
placeholder line as today. `None` (helper/engineer callers) = today's
behaviour, no extra call. The chat wake passes:

> "You have hit the {status} limit for this chat. Answer Rohit now from what
> you have already gathered — no more tools. Say plainly what you could not
> check."

## 3. Progress pings

- **Typing indicator.** `Telegram.typing(chat_id)` is a context manager: a
  daemon thread posts `sendChatAction typing` every 4 s until exit; errors are
  swallowed (an indicator must never fail a wake). `process_message` wraps the
  model/tool phase in it.
- **Notes.** `run_agent(..., progress=None)`: a `progress(text)` callable. The
  loop calls it (a) with the assistant's own text when a turn carries both
  text and tool calls (the gaffer thinking aloud), and (b) with a tool's note
  when `Tool.progress(phase, arguments, result)` returns one — `phase` is
  `"start"` (result None) or `"done"`. Only `ask_helper` defines one:
  `⏳ asking {role}: {question}` and `✅ {role} answered — {first line}`.
  In chat, `progress` sends the text to the chat and logs `progress`; a failed
  send is logged and ignored. Nothing else pings (no per-fetch spam).

## 4. Approval buttons

- `Telegram.send_message(chat_id, text, buttons=None)`: `buttons` is a list of
  `(label, callback_data)`; when given, the LAST chunk carries an inline
  keyboard (one row). Both the HTML send and the plain fallback carry it.
- `get_updates` also parses `callback_query` updates whose message chat is
  private into a `Message` with `text = data`, `from_id = callback_query.from.id`,
  `chat_id = message.chat.id`, and a new `callback_id`. Everything else is
  still dropped in the client.
- `process_message`: allowlist check first, as today. Then, for a callback
  message: `answerCallbackQuery` (clears the spinner; failure ignored); if the
  data is not an approve token or `stop`, log `drop reason=callback_not_a_token`
  and return; the gate runs as for typed text; if the gate did not consume it
  (nothing pending / not locked) reply `⚠ nothing awaiting that` and return —
  a stale button never reaches the model.
- Where the buttons ride: draft brief and changed final → `✅ Approve` (`yes`);
  unchanged final ("locking at T−30m") → `⛔ Stop` (`stop`); a chat iterate
  that re-emits a plan → `✅ Approve`. Approve receipt itself has no buttons.
- `FakeTransport`: records `sendChatAction` in `actions`, answers
  `answerCallbackQuery` ok, and `sent[i]["buttons"]` is present only when a
  keyboard was sent (existing exact-equality asserts stay valid).
  `tests/fakes.callback_query(from_id, data, …)` builds the update.

## 5. Tests (HTTP-edge harness, as the rest)

- agent: cap logs `agent_cap_hit`; `finish_on_cap` makes exactly one extra
  toolless call and its text is the reply, status unchanged; None makes none;
  `progress` receives think-aloud text and tool notes in order.
- telegram: callback parse (private only, `callback_id` set); buttons on the
  last chunk only, on HTML and fallback; `typing` posts `sendChatAction`.
- loop/approval: button `yes` approves with zero LLM packets; button `stop`
  holds a locked plan; a non-token callback is dropped; a stale button gets the
  "nothing awaiting" line, no LLM; typing action recorded during a chat wake;
  ask progress notes reach the chat before the reply.
- brief: draft/changed-final carry Approve, unchanged-final carries Stop.
- config / gaffer_tools: new defaults and the ask cap of 6.
- `AGENTS.md`: a short note on buttons + progress under the daemon section.
