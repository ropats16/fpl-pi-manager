"""Telegram long-poll client — parses updates, filters to 1:1 plain messages."""

import unittest

from daemon.http import Response
from daemon.telegram import Telegram, TelegramError
from tests.fakes import FakeTransport, private_message


class _OkFalseTransport:
    def request(self, method, url, headers=None, body=None):
        import json
        return Response(status=409, body=json.dumps(
            {"ok": False, "description": "Conflict: terminated by other getUpdates"}
        ).encode("utf-8"))


class GetUpdatesTest(unittest.TestCase):
    def test_parses_private_message(self):
        t = Telegram(token="TT", transport=FakeTransport(
            updates_batches=[[private_message(from_id=42, text="hi", update_id=7)]]))

        msgs = t.get_updates(offset=0)

        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].from_id, 42)
        self.assertEqual(msgs[0].text, "hi")
        self.assertEqual(msgs[0].chat_id, 42)
        self.assertEqual(msgs[0].update_id, 7)

    def test_ignores_non_message_and_group_updates(self):
        edited = {"update_id": 2, "edited_message": {"from": {"id": 42},
                  "chat": {"id": 42, "type": "private"}, "text": "x"}}
        channel = {"update_id": 3, "channel_post": {"chat": {"id": -1, "type": "channel"},
                   "text": "x"}}
        group = {"update_id": 4, "message": {"from": {"id": 42},
                 "chat": {"id": -100, "type": "group"}, "text": "x"}}
        t = Telegram(token="TT", transport=FakeTransport(
            updates_batches=[[edited, channel, group]]))

        self.assertEqual(t.get_updates(offset=0), [])

    def test_raises_on_api_error_instead_of_silent_empty(self):
        t = Telegram(token="TT", transport=_OkFalseTransport())

        with self.assertRaises(TelegramError) as ctx:
            t.get_updates(offset=0)
        self.assertIn("Conflict", str(ctx.exception))


class _ScriptedSendTransport:
    """Records each sendMessage payload and returns ok per a scripted sequence."""

    def __init__(self, ok_sequence):
        self.ok_sequence = list(ok_sequence)
        self.sends = []

    def request(self, method, url, headers=None, body=None):
        import json
        payload = json.loads(body.decode("utf-8"))
        self.sends.append(payload)
        ok = self.ok_sequence.pop(0) if self.ok_sequence else True
        return Response(status=200 if ok else 400, body=json.dumps(
            {"ok": ok, "description": "Bad Request: can't parse entities"}).encode("utf-8"))


class SendMessageTest(unittest.TestCase):
    def test_posts_chat_id_and_text(self):
        fake = FakeTransport()
        t = Telegram(token="TT", transport=fake)

        t.send_message(chat_id=42, text="hello")

        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "hello"}])

    def test_sends_html_parse_mode_with_converted_markup(self):
        tp = _ScriptedSendTransport(ok_sequence=[True])
        Telegram(token="TT", transport=tp).send_message(chat_id=42, text="**hi**")

        self.assertEqual(len(tp.sends), 1)
        self.assertEqual(tp.sends[0]["parse_mode"], "HTML")
        self.assertEqual(tp.sends[0]["text"], "<b>hi</b>")

    def test_falls_back_to_plain_text_when_html_send_is_rejected(self):
        tp = _ScriptedSendTransport(ok_sequence=[False, True])   # HTML 400s, plain ok
        Telegram(token="TT", transport=tp).send_message(chat_id=42, text="**hi**")

        self.assertEqual(len(tp.sends), 2)
        self.assertNotIn("parse_mode", tp.sends[1])              # retried as plain text
        self.assertEqual(tp.sends[1]["text"], "**hi**")          # original, unconverted

    def test_raises_when_even_the_plain_fallback_fails(self):
        tp = _ScriptedSendTransport(ok_sequence=[False, False])
        with self.assertRaises(TelegramError):
            Telegram(token="TT", transport=tp).send_message(chat_id=42, text="**hi**")


if __name__ == "__main__":
    unittest.main()
