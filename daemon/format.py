"""Render the model's CommonMark reply to Telegram's HTML flavour.

The gaffer answers in markdown (**bold**, `- ` bullets, `code`). Telegram prints
that literally unless sendMessage carries a parse_mode. We target HTML rather than
Markdown/MarkdownV2 because HTML needs only `& < >` escaped — so free-form model
output can't trip an unescaped-entity 400 — and `**double**` bold (which legacy
Markdown mode doesn't even recognise) maps cleanly to <b>. Stdlib-only.
"""

import re

_BULLET = re.compile(r"(?m)^[ \t]*[-*][ \t]+")   # "- x" / "* x" at line start
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)         # **x** (non-greedy, spans newlines)
_CODE = re.compile(r"`([^`]+?)`")                  # `x`


def to_telegram_html(text):
    """Convert markdown to Telegram-safe HTML. Escapes entities first so the only
    real tags in the result are the ones we insert."""
    s = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = _BULLET.sub("• ", s)
    s = _BOLD.sub(r"<b>\1</b>", s)
    s = _CODE.sub(r"<code>\1</code>", s)
    return s
