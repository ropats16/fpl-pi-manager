"""Telegram Bot API client — long-poll getUpdates + sendMessage.

Only 1:1 plain text messages are surfaced. Edited messages, channel posts,
group chats, and callback/inline updates are dropped here, before the allowlist
check and long before any text reaches the model (#10 §2: "Accept only plain
messages from the 1:1 chat").
"""

import json

from daemon.format import to_telegram_html

API = "https://api.telegram.org"


class TelegramError(Exception):
    """A getUpdates/sendMessage call the API rejected (bad token, 409 conflict…).

    Raised rather than swallowed so the daemon's poll loop logs it and backs off
    — an invisible ok:false would hide a stuck daemon (auditability, #15)."""


class Message:
    __slots__ = ("update_id", "from_id", "chat_id", "text")

    def __init__(self, update_id, from_id, chat_id, text):
        self.update_id = update_id
        self.from_id = from_id
        self.chat_id = chat_id
        self.text = text


class Telegram:
    def __init__(self, token, transport, poll_timeout=25):
        self._token = token
        self._transport = transport
        self._poll_timeout = poll_timeout

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
        # Only plain incoming messages — ignore edited/channel/callback/inline.
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

    def _post_message(self, chat_id, text, parse_mode=None):
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        resp = self._transport.request("POST", self._url("sendMessage"), headers, body)
        return resp.json()

    def send_message(self, chat_id, text):
        """Send as Telegram HTML (rendered from the model's markdown). A parse
        error must never eat the reply, so fall back to the raw text on rejection;
        only a failed plain send raises (so the poll loop logs it)."""
        data = self._post_message(chat_id, to_telegram_html(text), parse_mode="HTML")
        if data.get("ok"):
            return
        data = self._post_message(chat_id, text)   # plain-text fallback
        if not data.get("ok"):
            raise TelegramError(data.get("description", "sendMessage failed"))
