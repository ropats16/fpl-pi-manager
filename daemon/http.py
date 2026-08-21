"""The one network seam. Stdlib-only (Pi-friendly, no pip).

Every outbound request in the daemon goes through a Transport. Production uses
UrllibTransport; tests inject a fake (tests/fakes.py) so the whole wake->reply
loop runs offline. Keeping the HTTP edge injectable is the #7-locked
testability guarantee ("you own the HTTP edges").
"""

import json
import urllib.error
import urllib.request


class Response:
    __slots__ = ("status", "body")

    def __init__(self, status, body):
        self.status = status
        self.body = body  # bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class UrllibTransport:
    """Real transport over urllib. GET/POST only — no other verbs are used."""

    def __init__(self, timeout=30):
        self.timeout = timeout

    def request(self, method, url, headers=None, body=None):
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return Response(status=resp.status, body=resp.read())
        except urllib.error.HTTPError as e:
            return Response(status=e.code, body=e.read())


def _json_response(obj):
    return Response(status=200, body=json.dumps(obj).encode("utf-8"))


class FakeTransport:
    """Canonical offline fake for the network seam — the whole wake->reply loop
    runs through it with zero packets leaving the box (the #7 "own the HTTP
    edges" guarantee). Used by both the shipped `daemon selftest` and the tests.

    Routes by URL: Telegram getUpdates pops from `updates_batches` (empty ->
    idle poll), sendMessage is recorded in `sent` and answered ok, and the
    OpenRouter chat endpoint answers with `llm_reply`, recording each request
    body in `llm_requests`.
    """

    def __init__(self, updates_batches=None, llm_reply="ok"):
        self.updates_batches = list(updates_batches or [])
        self.llm_reply = llm_reply
        self.sent = []          # [{chat_id, text}]
        self.llm_requests = []  # [parsed request body dict]
        self.requests = []      # [(method, url)]

    def request(self, method, url, headers=None, body=None):
        self.requests.append((method, url))
        if "/getUpdates" in url:
            batch = self.updates_batches.pop(0) if self.updates_batches else []
            return _json_response({"ok": True, "result": batch})
        if "/sendMessage" in url:
            payload = json.loads(body.decode("utf-8"))
            self.sent.append({"chat_id": payload["chat_id"], "text": payload["text"]})
            return _json_response({"ok": True, "result": {"message_id": 1}})
        if "chat/completions" in url:
            self.llm_requests.append(json.loads(body.decode("utf-8")))
            return _json_response({
                "choices": [{"message": {"role": "assistant",
                                         "content": self.llm_reply}}]
            })
        raise AssertionError(f"unexpected request to {url}")
