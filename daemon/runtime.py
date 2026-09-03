"""Wiring factory — one place that builds the daemon's component stack.

Both the real entrypoint (UrllibTransport) and the offline selftest/tests
(FakeTransport) construct the same Telegram + LLM + logger stack from a Config;
the transport is the only thing that varies.
"""

from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.telegram import Telegram
from daemon.tools import ExaSearch, Fetcher


def build_stack(cfg, transport, out):
    """Return (telegram, llm, logger) wired from cfg over the given transport.
    The LLM gets the logger + price table so every call logs usage and an
    estimated cost (#54)."""
    logger = StructuredLogger(stream=out, secrets=cfg.secrets())
    telegram = Telegram(token=cfg.telegram_token, transport=transport)
    llm = LLM(api_key=cfg.openrouter_key, model=cfg.model, transport=transport,
              base_url=cfg.base_url, logger=logger, prices=cfg.helpers.prices)
    return telegram, llm, logger


def build_helper_tools(cfg, transport, llm, logger):
    """Return (fetcher, searcher) for one wake from the tier-1 helper settings:
    the allowlisted, cached fetcher (with the Odds API credential) and the
    search provider named in config. Only `exa` is wired (#51); any other name
    is a config error raised here, at wiring time, never mid-helper."""
    h = cfg.helpers
    fetcher = Fetcher(transport, h.allowlist, odds_api_key=cfg.odds_api_key,
                      logger=logger)
    if h.search_provider != "exa":
        raise ValueError(f"unsupported search provider {h.search_provider!r} "
                         "(only 'exa' is wired; Brave is documented in daemon/tools.py)")
    searcher = ExaSearch(llm, h.search_model, logger=logger, cost_usd=h.search_cost_usd)
    return fetcher, searcher
