"""Config loading — allowlist + secrets, creds-dir preferred over env (#8/#10)."""

import os
import tempfile
import unittest

from daemon.config import load_config, DEFAULT_MODEL


class LoadConfigTest(unittest.TestCase):
    def test_parses_numeric_allowlist(self):
        cfg = load_config(env={
            "GAFFER_ALLOWLIST_USER_IDS": "42, 99",
            "TELEGRAM_BOT_TOKEN": "t",
            "OPENROUTER_API_KEY": "k",
        })
        self.assertEqual(cfg.allowlist, {42, 99})

    def test_defaults_model_when_unset(self):
        cfg = load_config(env={
            "GAFFER_ALLOWLIST_USER_IDS": "1",
            "TELEGRAM_BOT_TOKEN": "t", "OPENROUTER_API_KEY": "k",
        })
        self.assertEqual(cfg.model, DEFAULT_MODEL)

    def test_credentials_directory_takes_precedence_over_env(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "telegram-token"), "w") as f:
                f.write("cred-token\n")
            with open(os.path.join(d, "openrouter-key"), "w") as f:
                f.write("cred-key\n")
            cfg = load_config(env={
                "GAFFER_ALLOWLIST_USER_IDS": "1",
                "TELEGRAM_BOT_TOKEN": "env-token",
                "OPENROUTER_API_KEY": "env-key",
                "CREDENTIALS_DIRECTORY": d,
            })
        self.assertEqual(cfg.telegram_token, "cred-token")
        self.assertEqual(cfg.openrouter_key, "cred-key")

    def test_missing_required_config_raises(self):
        with self.assertRaises(ValueError):
            load_config(env={"GAFFER_ALLOWLIST_USER_IDS": "1"})


if __name__ == "__main__":
    unittest.main()
