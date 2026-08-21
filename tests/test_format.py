"""Markdown -> Telegram-HTML conversion.

The model replies in CommonMark (**bold**, `- ` bullets, `code`); Telegram shows
that raw unless a parse_mode is set. We render to Telegram's HTML flavour, which
needs only three characters escaped, so free-form model output can't 400 the send.
"""

import unittest

from daemon.format import to_telegram_html


class ToTelegramHtmlTest(unittest.TestCase):
    def test_double_asterisk_becomes_bold(self):
        self.assertEqual(to_telegram_html("**Bank is zero.**"), "<b>Bank is zero.</b>")

    def test_dash_bullets_become_dots(self):
        self.assertEqual(to_telegram_html("- Haaland\n- Bruno"), "• Haaland\n• Bruno")

    def test_inline_code_becomes_code_tag(self):
        self.assertEqual(to_telegram_html("reply `yes` to lock"),
                         "reply <code>yes</code> to lock")

    def test_html_special_chars_are_escaped(self):
        # ampersand/angle brackets in model text must not inject markup
        self.assertEqual(to_telegram_html("a < b & c > d"), "a &lt; b &amp; c &gt; d")

    def test_plain_text_is_unchanged(self):
        self.assertEqual(to_telegram_html("Haaland (C) — solid XI"), "Haaland (C) — solid XI")

    def test_bold_inside_a_bullet_line(self):
        self.assertEqual(to_telegram_html("- **Bench** is thin"), "• <b>Bench</b> is thin")

    def test_no_literal_asterisks_survive_a_bold_headline(self):
        out = to_telegram_html("**Data file's garbled — here's what I can see.**")
        self.assertNotIn("*", out)
        self.assertTrue(out.startswith("<b>") and out.endswith("</b>"))


if __name__ == "__main__":
    unittest.main()
