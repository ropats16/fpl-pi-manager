"""Telegram Bot API client — long-poll getUpdates + sendMessage.

Only 1:1 plain text messages are surfaced. Edited messages, channel posts,
group chats, and callback/inline updates are dropped here, before the allowlist
check and long before any text reaches the model (#10 §2: "Accept only plain
messages from the 1:1 chat").
"""

import json

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

    def send_message(self, chat_id, text):
        body = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        self._transport.request("POST", self._url("sendMessage"), headers, body)
