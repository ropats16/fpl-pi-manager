"""Wiring factory — one place that builds the daemon's component stack.

Both the real entrypoint (UrllibTransport) and the offline selftest/tests
(FakeTransport) construct the same Telegram + LLM + logger stack from a Config;
the transport is the only thing that varies.
"""

from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.telegram import Telegram


def build_stack(cfg, transport, out):
    """Return (telegram, llm, logger) wired from cfg over the given transport."""
    logger = StructuredLogger(stream=out, secrets=cfg.secrets())
    telegram = Telegram(token=cfg.telegram_token, transport=transport)
    llm = LLM(api_key=cfg.openrouter_key, model=cfg.model, transport=transport,
              base_url=cfg.base_url)
    return telegram, llm, logger
