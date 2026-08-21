"""Test doubles for the daemon's HTTP-edge harness.

The one seam the whole skeleton is testable through is the HTTP transport
(daemon.http.Transport). FakeTransport routes requests by URL to the three
faked externals — Telegram getUpdates/sendMessage and the OpenRouter chat
endpoint — so the *real* Telegram and LLM client code runs while zero packets
leave the box. This mirrors run_pipeline.sh's offline seam for the network edge.
"""

import json

from daemon.http import Response


class FakeTransport:
    """Records outbound requests and answers them from queued fakes.

    - Telegram getUpdates: pops from `updates_batches` (list of update-lists);
      empty/exhausted -> returns no updates (an idle long-poll).
    - Telegram sendMessage: appended to `sent` and answered ok.
    - OpenRouter chat/completions: answers with `llm_reply` and records the
      request body in `llm_requests`.
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
                "choices": [{"message": {"role": "assistant", "content": self.llm_reply}}]
            })
        raise AssertionError(f"unexpected request to {url}")


def _json_response(obj):
    return Response(status=200, body=json.dumps(obj).encode("utf-8"))


def private_message(from_id, text, chat_id=None, update_id=1):
    """A Telegram getUpdates entry for a 1:1 private text message."""
    chat_id = from_id if chat_id is None else chat_id
    return {
        "update_id": update_id,
        "message": {
            "message_id": 100,
            "from": {"id": from_id, "is_bot": False, "first_name": "T"},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }
