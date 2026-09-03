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


def tool_call_message(name, arguments, call_id="call_1", content=None):
    """An assistant message carrying one function tool call, in the
    OpenAI-compatible shape OpenRouter returns (arguments as a JSON string).
    Shipped here because the selftest queues these too."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [{"id": call_id, "type": "function",
                        "function": {"name": name,
                                     "arguments": json.dumps(arguments)}}],
    }


DEFAULT_USAGE = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}


class FakeTransport:
    """Canonical offline fake for the network seam — the whole wake->reply loop
    runs through it with zero packets leaving the box (the #7 "own the HTTP
    edges" guarantee). Used by both the shipped `daemon selftest` and the tests.

    Routes by URL: Telegram getUpdates pops from `updates_batches` (empty ->
    idle poll), sendMessage is recorded in `sent` and answered ok, and the
    OpenRouter chat endpoint answers with `llm_reply`, recording each request
    body in `llm_requests`.

    #54 extensions (the helper tool loop's seam):
    - a queued reply may be a full assistant *message* dict (with `tool_calls`)
      instead of a content string;
    - every chat reply carries a `usage` block (`usage`) so cost logging is
      exercised;
    - a chat request carrying `plugins` is the search sub-call: it is recorded
      in `search_requests` and answered with `search_reply` (never popped from
      the helper's reply queue);
    - `pages` maps fetchable URLs (exact, or sans query string) to canned
      bodies; any other GET raises — so an off-allowlist fetch that *did* reach
      the wire is loud, and `requests` is the log tests assert on.
    """

    def __init__(self, updates_batches=None, llm_reply="ok", llm_replies=None,
                 pages=None, search_reply="no results", usage=None):
        self.updates_batches = list(updates_batches or [])
        self.llm_reply = llm_reply
        # Optional queue of distinct replies, popped one per chat/completions
        # request (a brief wake can make two: a plan-block retry, or the final
        # re-generation). Falls back to `llm_reply` once drained — backward
        # compatible with callers that only set `llm_reply`.
        self.llm_replies = list(llm_replies) if llm_replies is not None else None
        self.pages = dict(pages or {})
        self.search_reply = search_reply
        self.usage = dict(usage or DEFAULT_USAGE)
        self.sent = []          # [{chat_id, text}]
        self.llm_requests = []  # [parsed request body dict] (helper/gaffer calls)
        self.search_requests = []  # [parsed request body dict] (plugin sub-calls)
        self.requests = []      # [(method, url)] — every request, in order

    def _chat_response(self, reply):
        if isinstance(reply, dict):
            message = dict(reply)
            message.setdefault("role", "assistant")
        else:
            message = {"role": "assistant", "content": reply}
        finish = "tool_calls" if message.get("tool_calls") else "stop"
        return _json_response({
            "choices": [{"message": message, "finish_reason": finish}],
            "usage": dict(self.usage),
        })

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
            payload = json.loads(body.decode("utf-8"))
            if payload.get("plugins"):
                self.search_requests.append(payload)
                return self._chat_response(self.search_reply)
            self.llm_requests.append(payload)
            if self.llm_replies:
                reply = self.llm_replies.pop(0)
            else:
                reply = self.llm_reply
            return self._chat_response(reply)
        if method == "GET":
            page = self.pages.get(url)
            if page is None:
                page = self.pages.get(url.split("?", 1)[0])
            if page is not None:
                body = page.encode("utf-8") if isinstance(page, str) else page
                return Response(status=200, body=body)
        raise AssertionError(f"unexpected request to {url}")
