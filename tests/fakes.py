"""Test fixtures for the daemon's HTTP-edge harness.

FakeTransport is the canonical offline fake, shipped in daemon.http (the
selftest uses it too) — re-exported here so tests import one name. This module
adds the Telegram-update builder that only tests need.
"""

from daemon.http import FakeTransport, tool_call_message  # noqa: F401  (re-exported)


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



def callback_query(from_id, data, chat_id=None, update_id=1, chat_type="private",
                   callback_id="cb1"):
    """A Telegram getUpdates entry for an inline-keyboard button press."""
    chat_id = from_id if chat_id is None else chat_id
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": from_id, "is_bot": False, "first_name": "T"},
            "message": {"message_id": 100,
                        "chat": {"id": chat_id, "type": chat_type},
                        "text": "the brief"},
            "data": data,
        },
    }
