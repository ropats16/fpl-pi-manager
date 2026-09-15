"""Telegram long-poll client — parses updates, filters to 1:1 plain messages."""

import unittest

from daemon.http import Response
from daemon.telegram import MAX_MESSAGE_CHARS, Telegram, TelegramError, split_message
from tests.fakes import FakeTransport, callback_query, private_message


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

    def test_long_reply_is_sent_as_ordered_chunks_under_the_telegram_limit(self):
        # 2026-09-04 07:29Z: a research reply died on "Bad Request: message is
        # too long" and was lost. Now it goes out in order, in pieces.
        paras = [f"Para {i}. " + ("word " * 120).strip() for i in range(20)]   # ~12k chars
        text = "\n\n".join(paras)
        fake = FakeTransport()
        Telegram(token="TT", transport=fake).send_message(chat_id=42, text=text)

        self.assertGreaterEqual(len(fake.sent), 3)
        self.assertTrue(all(len(s["text"]) <= MAX_MESSAGE_CHARS for s in fake.sent))
        self.assertTrue(all(s["chat_id"] == 42 for s in fake.sent))
        self.assertTrue(fake.sent[0]["text"].startswith("Para 0."))
        self.assertIn("Para 19.", fake.sent[-1]["text"])
        # Split on paragraph breaks: every chunk starts at a paragraph.
        self.assertTrue(all(s["text"].startswith("Para ") for s in fake.sent))

    def test_split_message_prefers_paragraph_then_line_then_hard_cut(self):
        self.assertEqual(split_message("short"), ["short"])
        self.assertEqual(split_message(""), [""])
        two = "a" * 50 + "\n\n" + "b" * 50
        self.assertEqual(split_message(two, limit=60), ["a" * 50, "b" * 50])
        lines = "a" * 50 + "\n" + "b" * 50
        self.assertEqual(split_message(lines, limit=60), ["a" * 50, "b" * 50])
        wall = "c" * 130
        self.assertEqual(split_message(wall, limit=60), ["c" * 60, "c" * 60, "c" * 10])
        self.assertEqual("".join(split_message(wall, limit=60)), wall)   # nothing dropped

    def test_raises_when_even_the_plain_fallback_fails(self):
        tp = _ScriptedSendTransport(ok_sequence=[False, False])
        with self.assertRaises(TelegramError):
            Telegram(token="TT", transport=tp).send_message(chat_id=42, text="**hi**")


class CallbackQueryTest(unittest.TestCase):
    """Chat-caps spec §4: a private-chat button press is a Message whose text is
    the callback data, tagged with `callback_id` so the loop can answer it."""

    def test_parses_a_private_button_press(self):
        t = Telegram(token="TT", transport=FakeTransport(
            updates_batches=[[callback_query(from_id=42, data="yes", update_id=9,
                                             callback_id="cb77")]]))
        msgs = t.get_updates(offset=0)
        self.assertEqual(len(msgs), 1)
        self.assertEqual((msgs[0].from_id, msgs[0].chat_id, msgs[0].text,
                          msgs[0].update_id, msgs[0].callback_id),
                         (42, 42, "yes", 9, "cb77"))

    def test_a_plain_message_has_no_callback_id(self):
        t = Telegram(token="TT", transport=FakeTransport(
            updates_batches=[[private_message(from_id=42, text="hi")]]))
        self.assertIsNone(t.get_updates(offset=0)[0].callback_id)

    def test_a_group_button_press_is_dropped(self):
        t = Telegram(token="TT", transport=FakeTransport(
            updates_batches=[[callback_query(from_id=42, data="yes", chat_id=-100,
                                             chat_type="group")]]))
        self.assertEqual(t.get_updates(offset=0), [])

    def test_answer_callback_posts_the_id_and_never_raises(self):
        fake = FakeTransport()
        Telegram(token="TT", transport=fake).answer_callback("cb77")
        self.assertEqual(fake.answered, ["cb77"])
        Telegram(token="TT", transport=_OkFalseTransport()).answer_callback("cb1")


class ButtonsTest(unittest.TestCase):
    def test_buttons_ride_on_the_last_chunk_only(self):
        paras = [f"Para {i}. " + ("word " * 120).strip() for i in range(20)]
        fake = FakeTransport()
        Telegram(token="TT", transport=fake).send_message(
            chat_id=42, text="\n\n".join(paras), buttons=[("✅ Approve", "yes")])
        self.assertGreaterEqual(len(fake.sent), 3)
        self.assertTrue(all("buttons" not in s for s in fake.sent[:-1]))
        self.assertEqual(fake.sent[-1]["buttons"], [("✅ Approve", "yes")])

    def test_no_buttons_means_no_reply_markup_key(self):
        fake = FakeTransport()
        Telegram(token="TT", transport=fake).send_message(chat_id=42, text="hello")
        self.assertEqual(fake.sent, [{"chat_id": 42, "text": "hello"}])

    def test_keyboard_is_one_row_of_callback_buttons_on_html_and_fallback(self):
        tp = _ScriptedSendTransport(ok_sequence=[False, True])
        Telegram(token="TT", transport=tp).send_message(
            chat_id=42, text="**hi**", buttons=[("✅ Approve", "yes"), ("⛔ Stop", "stop")])
        self.assertEqual(len(tp.sends), 2)
        for payload in tp.sends:
            self.assertEqual(payload["reply_markup"], {"inline_keyboard": [[
                {"text": "✅ Approve", "callback_data": "yes"},
                {"text": "⛔ Stop", "callback_data": "stop"}]]})


class TypingTest(unittest.TestCase):
    def test_typing_posts_a_chat_action_while_the_block_runs(self):
        fake = FakeTransport()
        t = Telegram(token="TT", transport=fake)
        with t.typing(42):
            pass
        self.assertEqual(fake.actions[0], {"chat_id": 42, "action": "typing"})

    def test_typing_keeps_posting_while_the_block_runs(self):
        import time
        fake = FakeTransport()
        t = Telegram(token="TT", transport=fake, typing_interval=0.01)
        with t.typing(42):
            time.sleep(0.08)
        self.assertGreaterEqual(len(fake.actions), 3)
        n = len(fake.actions)
        time.sleep(0.05)
        self.assertEqual(len(fake.actions), n)          # stopped on exit

    def test_a_failing_action_never_breaks_the_block(self):
        t = Telegram(token="TT", transport=_OkFalseTransport())
        with t.typing(42):
            ran = True
        self.assertTrue(ran)


if __name__ == "__main__":
    unittest.main()
