"""Telegram Bot API client — long-poll getUpdates + sendMessage.

Only 1:1 plain text messages and 1:1 inline-button presses are surfaced.
Edited messages, channel posts, group chats and inline-mode updates are dropped
here, before the allowlist check and long before any text reaches the model
(#10 §2: "Accept only plain messages from the 1:1 chat"). A button press
(`callback_query`) becomes a Message whose text is the button's callback data,
tagged with `callback_id`; the loop accepts only the approve/stop tokens from
that path and drops the rest (plans/chat-caps-progress-buttons.md §4).
"""

import json
import threading

from daemon.format import to_telegram_html

API = "https://api.telegram.org"

# sendChatAction "typing" shows for ~5 s; re-post under that while a wake runs.
TYPING_INTERVAL_SECONDS = 4.0


class TelegramError(Exception):
    """A getUpdates/sendMessage call the API rejected (bad token, 409 conflict…).

    Raised rather than swallowed so the daemon's poll loop logs it and backs off
    — an invisible ok:false would hide a stuck daemon (auditability, #15)."""


class Message:
    __slots__ = ("update_id", "from_id", "chat_id", "text", "callback_id")

    def __init__(self, update_id, from_id, chat_id, text, callback_id=None):
        self.update_id = update_id
        self.from_id = from_id
        self.chat_id = chat_id
        self.text = text
        self.callback_id = callback_id       # set only for a button press


class Telegram:
    def __init__(self, token, transport, poll_timeout=25,
                 typing_interval=TYPING_INTERVAL_SECONDS):
        self._token = token
        self._transport = transport
        self._poll_timeout = poll_timeout
        self._typing_interval = typing_interval

    def _url(self, method):
        return f"{API}/bot{self._token}/{method}"

    def get_updates(self, offset, timeout=None):
        timeout = self._poll_timeout if timeout is None else timeout
        url = self._url("getUpdates") + f"?offset={offset}&timeout={timeout}"
        resp = self._transport.request("GET", url)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(data.get("description", "getUpdates failed"))
        return [m for m in (self._parse(u) for u in data.get("result", [])) if m]

    @staticmethod
    def _parse(update):
        # A 1:1 button press: the callback data is the message text (§4).
        cb = update.get("callback_query")
        if cb:
            chat = (cb.get("message") or {}).get("chat", {})
            if chat.get("type") != "private" or "data" not in cb:
                return None
            return Message(update_id=update["update_id"], from_id=cb["from"]["id"],
                           chat_id=chat["id"], text=cb["data"], callback_id=cb["id"])
        # Otherwise only plain incoming messages — ignore edited/channel/inline.
        msg = update.get("message")
        if not msg or "text" not in msg:
            return None
        if msg.get("chat", {}).get("type") != "private":
            return None
        return Message(
            update_id=update["update_id"],
            from_id=msg["from"]["id"],
            chat_id=msg["chat"]["id"],
            text=msg["text"],
        )

    def _post(self, method, payload):
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        resp = self._transport.request("POST", self._url(method), headers, body)
        return resp.json()

    def _post_message(self, chat_id, text, parse_mode=None, buttons=None):
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": label, "callback_data": data} for label, data in buttons]]}
        return self._post("sendMessage", payload)

    def send_message(self, chat_id, text, buttons=None):
        """Send as Telegram HTML (rendered from the model's markdown), in
        order-preserving chunks under Telegram's 4096-char limit (a 07:29Z
        2026-09-04 research reply was lost to "message is too long"). A parse
        error must never eat the reply, so each chunk falls back to raw text on
        rejection; only a failed plain send raises (so the poll loop logs it).
        `buttons` — [(label, callback_data), …] — is one inline-keyboard row on
        the LAST chunk (§4), on the HTML send and its plain fallback alike."""
        chunks = split_message(text)
        for i, chunk in enumerate(chunks):
            row = buttons if i == len(chunks) - 1 else None
            data = self._post_message(chat_id, to_telegram_html(chunk),
                                      parse_mode="HTML", buttons=row)
            if data.get("ok"):
                continue
            data = self._post_message(chat_id, chunk, buttons=row)   # plain-text fallback
            if not data.get("ok"):
                raise TelegramError(data.get("description", "sendMessage failed"))

    def answer_callback(self, callback_id):
        """Acknowledge a button press (clears the client's spinner). Best-effort:
        a failure here changes nothing about how the press was handled."""
        self._post_quiet("answerCallbackQuery", {"callback_query_id": callback_id})

    def typing(self, chat_id):
        """Context manager: keep the chat's "typing…" indicator alive while the
        block runs (a wake with staff asks can take many minutes — §3). A daemon
        thread re-posts sendChatAction every `typing_interval` seconds until
        exit; a failed post is ignored, an indicator must never fail a wake."""
        return _Typing(self, chat_id, self._typing_interval)

    def _chat_action(self, chat_id, action="typing"):
        self._post_quiet("sendChatAction", {"chat_id": chat_id, "action": action})

    def _post_quiet(self, method, payload):
        """A cosmetic call (spinner, typing dot): its failure is not an event —
        the wake it decorates is logged on its own path."""
        try:
            self._post(method, payload)
        except Exception:                # noqa: BLE001 — cosmetic, never a failed wake
            pass


class _Typing:
    """The `Telegram.typing` context: one keep-alive thread per `with` block.
    Not re-entrant — build a fresh one per wake (the loop does)."""

    __slots__ = ("_tg", "_chat_id", "_interval", "_stop", "_thread")

    def __init__(self, telegram, chat_id, interval):
        self._tg = telegram
        self._chat_id = chat_id
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            self._tg._chat_action(self._chat_id)
            self._stop.wait(self._interval)

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, name="tg-typing", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=self._interval + 1)
        return False


# Telegram caps a message at 4096 chars; the HTML rendering adds tags, so the
# raw-text chunks stay well under it.
MAX_MESSAGE_CHARS = 4096
CHUNK_CHARS = 3600


def split_message(text, limit=CHUNK_CHARS):
    """Split `text` into pieces of at most `limit` chars, preferring a
    paragraph break, then a line break, then a hard cut. Never drops text;
    "" -> [""] so an empty send still goes out as before."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 3:
            cut = window.rfind("\n")
        if cut < limit // 3:
            cut = limit
        chunks.append(rest[:cut].rstrip("\n"))
        rest = rest[cut:].lstrip("\n")
    if rest:
        chunks.append(rest)
    return chunks
