"""Daemon configuration — tier-1 core, never model-writable (#10 §4).

Secrets are read from systemd's LoadCredentialEncrypted target
($CREDENTIALS_DIRECTORY, a service-private tmpfs — never env, never the
workspace disk), falling back to environment variables for local dev. The
Telegram allowlist is numeric user IDs (never @username) and lives outside every
gaffer-writable path so a poisoned gaffer cannot widen it (#10 §2).

#54 adds the helper runtime's settings (`HelperSettings`): the role->model map,
the fetch domain allowlist, the per-helper ceilings and the price table — all
tier-1 (daemon config the gaffer cannot edit, #52 story 20), defaults matching
the #51 decisions so an unchanged Pi env works, env-overridable like the rest.
"""

import json
import os

from daemon.llm import DEFAULT_BASE_URL, DEFAULT_MODEL

DEFAULT_SYSTEM_PROMPT = (
    "You are the gaffer, an autonomous Fantasy Premier League manager assistant "
    "for Rohit. Answer concisely and helpfully."
)

# --- #51 role->model map -----------------------------------------------------------
HELPER_MODEL = "z-ai/glm-5.3-flash"      # analysts + Scout (+ the search sub-call)
AM_MODEL = "qwen/qwen3.8-max"            # assistant-manager: a third model family
HELPER_ROLES = ("availability", "fixtures", "quality", "market", "scout", "am")

# --- #51 seed fetch allowlist (bare domains; subdomains match) -----------------------
DEFAULT_FETCH_ALLOWLIST = frozenset({
    "fantasy.premierleague.com",       # official FPL API
    "fantasyfootballscout.co.uk",      # team news + presser pages
    "understat.com",                   # xG / xA
    "football-data.co.uk",             # closing lines CSV (calibration only)
    "api.the-odds-api.com",            # The Odds API (keyed by the fetcher)
})

# --- #51 per-helper ceilings: circuit breakers ~3x above a thorough run --------------
DEFAULT_HELPER_CAPS = {"fetches": 25, "searches": 10, "turns": 40, "minutes": 15}

# --- price table, USD per 1M tokens (openrouter.ai/models, verified 2026-09-03) -----
DEFAULT_PRICES = {
    "openai/gpt-5.6-sol": {"prompt": 2.0, "completion": 10.0},
    "z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25},
    "qwen/qwen3.8-max": {"prompt": 2.0, "completion": 6.0},
}
# OpenRouter web plugin, engine Exa: $0.007/request incl. 10 results.
DEFAULT_SEARCH_COST_USD = 0.007
DEFAULT_GITHUB_REPO = "ropats16/fpl-pi-manager"   # #55 auto-PR target (owner/name)


class HelperSettings:
    __slots__ = ("models", "allowlist", "caps", "prices", "search_provider",
                 "search_model", "search_cost_usd")

    def __init__(self, models, allowlist, caps, prices, search_provider="exa",
                 search_model=HELPER_MODEL, search_cost_usd=DEFAULT_SEARCH_COST_USD):
        self.models = models
        self.allowlist = allowlist
        self.caps = caps
        self.prices = prices
        self.search_provider = search_provider
        self.search_model = search_model
        self.search_cost_usd = search_cost_usd


def default_helper_settings():
    models = {r: HELPER_MODEL for r in HELPER_ROLES}
    models["am"] = AM_MODEL
    return HelperSettings(models=models, allowlist=set(DEFAULT_FETCH_ALLOWLIST),
                          caps=dict(DEFAULT_HELPER_CAPS),
                          prices={k: dict(v) for k, v in DEFAULT_PRICES.items()})


def _int_env(env, key, default):
    """A positive int from env, else the default (a 0 or negative ceiling
    would make every helper cap out on its first turn)."""
    try:
        v = int(env.get(key, default))
    except (TypeError, ValueError):
        return default
    return v if v >= 1 else default


def load_helper_settings(env=None):
    """HelperSettings from #51 defaults + env overrides. A malformed override
    falls back to the default for that one field (never a crash: a typo in
    gaffer.env must not take the daemon down)."""
    env = os.environ if env is None else env
    h = default_helper_settings()
    helper_model = env.get("GAFFER_HELPER_MODEL")
    if helper_model:
        for r in HELPER_ROLES:
            if r != "am":
                h.models[r] = helper_model
        h.search_model = helper_model
    am_model = env.get("GAFFER_AM_MODEL")
    if am_model:
        h.models["am"] = am_model
    # Per-role override (story 24: swapping one role's model is a config change).
    for r in HELPER_ROLES:
        per_role = env.get(f"GAFFER_HELPER_MODEL_{r.upper()}")
        if per_role:
            h.models[r] = per_role
    raw = env.get("GAFFER_FETCH_ALLOWLIST", "").strip()
    if raw:
        h.allowlist = {d.strip().lower() for d in raw.replace(",", " ").split() if d.strip()}
    h.caps = {
        "fetches": _int_env(env, "GAFFER_HELPER_MAX_FETCHES", h.caps["fetches"]),
        "searches": _int_env(env, "GAFFER_HELPER_MAX_SEARCHES", h.caps["searches"]),
        "turns": _int_env(env, "GAFFER_HELPER_MAX_TURNS", h.caps["turns"]),
        "minutes": _int_env(env, "GAFFER_HELPER_MAX_MINUTES", h.caps["minutes"]),
    }
    raw = env.get("GAFFER_PRICE_TABLE")
    if raw:
        try:
            table = json.loads(raw)
            if isinstance(table, dict):
                for model, row in table.items():
                    if isinstance(row, dict):
                        h.prices[model] = {"prompt": float(row.get("prompt", 0)),
                                           "completion": float(row.get("completion", 0))}
        except (TypeError, ValueError):
            pass
    h.search_provider = env.get("GAFFER_SEARCH_PROVIDER", h.search_provider)
    return h


class Config:
    __slots__ = ("allowlist", "telegram_token", "openrouter_key", "model",
                 "base_url", "system_prompt", "odds_api_key", "helpers",
                 "github_token", "github_repo")

    def __init__(self, allowlist, telegram_token, openrouter_key, model,
                 base_url, system_prompt, odds_api_key=None, helpers=None,
                 github_token=None, github_repo=DEFAULT_GITHUB_REPO):
        self.allowlist = allowlist
        self.telegram_token = telegram_token
        self.openrouter_key = openrouter_key
        self.model = model
        self.base_url = base_url
        self.system_prompt = system_prompt
        self.odds_api_key = odds_api_key
        self.helpers = helpers if helpers is not None else default_helper_settings()
        self.github_token = github_token
        self.github_repo = github_repo

    def secrets(self):
        """Values that must never appear in logs (fed to StructuredLogger)."""
        return [self.telegram_token, self.openrouter_key, self.odds_api_key,
                self.github_token]


def _parse_allowlist(env):
    """Numeric Telegram user IDs from GAFFER_ALLOWLIST_USER_IDS (comma/space)."""
    raw_ids = env.get("GAFFER_ALLOWLIST_USER_IDS", "").strip()
    return {int(x) for x in raw_ids.replace(",", " ").split()}


def load_notify_config(env=None):
    """Minimal config for the `notify` push: Telegram token + allowlist only.
    The deploy path reports a reload/blocked deploy without ever touching the LLM
    key, so this deliberately does NOT require openrouter_key — the pull unit then
    loads only the telegram-token credential (least privilege, #10)."""
    env = os.environ if env is None else env
    allowlist = _parse_allowlist(env)
    telegram_token = _read_credential(env, "telegram-token", "TELEGRAM_BOT_TOKEN")
    missing = [n for n, v in (("allowlist", allowlist),
                              ("telegram token", telegram_token)) if not v]
    if missing:
        raise ValueError(f"missing required config: {', '.join(missing)}")
    return allowlist, telegram_token


def _read_credential(env, name, env_var):
    creds_dir = env.get("CREDENTIALS_DIRECTORY")
    if creds_dir:
        path = os.path.join(creds_dir, name)
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read().strip()
    return env.get(env_var)


def load_config(env=None):
    env = os.environ if env is None else env

    allowlist = _parse_allowlist(env)

    telegram_token = _read_credential(env, "telegram-token", "TELEGRAM_BOT_TOKEN")
    openrouter_key = _read_credential(env, "openrouter-key", "OPENROUTER_API_KEY")
    # The 5th secret (#51/#54): optional — only the fixtures/odds fetch needs it,
    # and a missing key degrades that one fetch to an error text, never the wake.
    odds_api_key = _read_credential(env, "odds-api-key", "ODDS_API_KEY") or None
    # The GitHub token (#55 auto-PR; "4th secret" in the #11 numbering): optional
    # — without it a role proposal degrades to a "no token" reply, never a crash.
    github_token = _read_credential(env, "github-token", "GITHUB_TOKEN") or None

    missing = [n for n, v in (("allowlist", allowlist),
                              ("telegram token", telegram_token),
                              ("openrouter key", openrouter_key)) if not v]
    if missing:
        raise ValueError(f"missing required config: {', '.join(missing)}")

    return Config(
        allowlist=allowlist,
        telegram_token=telegram_token,
        openrouter_key=openrouter_key,
        model=env.get("GAFFER_MODEL", DEFAULT_MODEL),
        base_url=env.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL),
        system_prompt=env.get("GAFFER_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        odds_api_key=odds_api_key,
        helpers=load_helper_settings(env),
        github_token=github_token,
        github_repo=env.get("GAFFER_GITHUB_REPO", DEFAULT_GITHUB_REPO),
    )
