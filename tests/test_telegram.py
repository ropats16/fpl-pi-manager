"""Telegram long-poll client — parses updates, filters to 1:1 plain messages."""

import unittest

from daemon.http import Response
from daemon.telegram import Telegram
from tests.fakes import FakeTransport, private_message


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


class SendMessageTest(unittest.TestCase):
    def test_posts_chat_id_and_text(self):
        fake = FakeTransport()
        t = Telegram(token="TT", transport=fake)

        t.send_message(chat_id=42, text="hello")

        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "hello"}])


if __name__ == "__main__":
    unittest.main()
