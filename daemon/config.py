"""Daemon configuration — tier-1 core, never model-writable (#10 §4).

Secrets are read from systemd's LoadCredentialEncrypted target
($CREDENTIALS_DIRECTORY, a service-private tmpfs — never env, never the
workspace disk), falling back to environment variables for local dev. The
Telegram allowlist is numeric user IDs (never @username) and lives outside every
gaffer-writable path so a poisoned gaffer cannot widen it (#10 §2).
"""

import os

from daemon.llm import DEFAULT_BASE_URL, DEFAULT_MODEL

DEFAULT_SYSTEM_PROMPT = (
    "You are the gaffer, an autonomous Fantasy Premier League manager assistant "
    "for Rohit. Answer concisely and helpfully."
)


class Config:
    __slots__ = ("allowlist", "telegram_token", "openrouter_key", "model",
                 "base_url", "system_prompt")

    def __init__(self, allowlist, telegram_token, openrouter_key, model,
                 base_url, system_prompt):
        self.allowlist = allowlist
        self.telegram_token = telegram_token
        self.openrouter_key = openrouter_key
        self.model = model
        self.base_url = base_url
        self.system_prompt = system_prompt

    def secrets(self):
        """Values that must never appear in logs (fed to StructuredLogger)."""
        return [self.telegram_token, self.openrouter_key]


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

    raw_ids = env.get("GAFFER_ALLOWLIST_USER_IDS", "").strip()
    allowlist = {int(x) for x in raw_ids.replace(",", " ").split()}

    telegram_token = _read_credential(env, "telegram-token", "TELEGRAM_BOT_TOKEN")
    openrouter_key = _read_credential(env, "openrouter-key", "OPENROUTER_API_KEY")

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
    )
