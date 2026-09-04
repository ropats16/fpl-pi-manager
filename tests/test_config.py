"""Config loading — allowlist + secrets, creds-dir preferred over env (#8/#10)."""

import os
import tempfile
import unittest

from daemon.config import (DEFAULT_MODEL, HELPER_MODEL, AM_MODEL, load_config,
                           load_helper_settings)


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



def _env(**over):
    base = {"GAFFER_ALLOWLIST_USER_IDS": "1", "TELEGRAM_BOT_TOKEN": "t",
            "OPENROUTER_API_KEY": "k"}
    base.update(over)
    return base


class HelperSettingsTest(unittest.TestCase):
    """#54: the helper runtime's tier-1 config — role->model map, seed allowlist,
    per-helper ceilings, price table, Odds API credential — with #51 defaults so
    an unchanged Pi env just works, env-overridable like everything else."""

    def test_defaults_match_the_51_decisions(self):
        cfg = load_config(env=_env())
        h = cfg.helpers
        for role in ("availability", "fixtures", "quality", "market", "chips", "scout"):
            self.assertEqual(h.models[role], HELPER_MODEL)
        self.assertEqual(h.models["am"], AM_MODEL)
        self.assertEqual(h.caps, {"fetches": 25, "searches": 15, "turns": 40,
                                  "minutes": 15})
        for dom in ("fantasy.premierleague.com", "fantasyfootballscout.co.uk",
                    "understat.com", "football-data.co.uk", "api.the-odds-api.com"):
            self.assertIn(dom, h.allowlist)
        self.assertEqual(h.prices["z-ai/glm-5.3-flash"], {"prompt": 0.075, "completion": 0.25})
        self.assertEqual(h.search_provider, "exa")
        self.assertIsNone(cfg.odds_api_key)

    def test_env_overrides(self):
        cfg = load_config(env=_env(
            GAFFER_HELPER_MODEL="x/cheap", GAFFER_AM_MODEL="y/judge",
            GAFFER_FETCH_ALLOWLIST="a.test, b.test",
            GAFFER_HELPER_MAX_FETCHES="3", GAFFER_HELPER_MAX_SEARCHES="1",
            GAFFER_HELPER_MAX_TURNS="5", GAFFER_HELPER_MAX_MINUTES="2",
            GAFFER_PRICE_TABLE='{"x/cheap": {"prompt": 1, "completion": 2}}'))
        h = cfg.helpers
        self.assertEqual(h.models["availability"], "x/cheap")
        self.assertEqual(h.models["am"], "y/judge")
        self.assertEqual(h.allowlist, {"a.test", "b.test"})
        self.assertEqual(h.caps, {"fetches": 3, "searches": 1, "turns": 5, "minutes": 2})
        self.assertEqual(h.prices["x/cheap"], {"prompt": 1, "completion": 2})
        self.assertIn("z-ai/glm-5.3-flash", h.prices)     # extends, never drops defaults

    def test_odds_key_is_a_credential_and_a_secret(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "odds-api-key"), "w") as f:
                f.write("ODDSKEY\n")
            cfg = load_config(env=_env(CREDENTIALS_DIRECTORY=d, ODDS_API_KEY="env-odds"))
        self.assertEqual(cfg.odds_api_key, "ODDSKEY")
        self.assertIn("ODDSKEY", cfg.secrets())
        self.assertEqual(load_config(env=_env(ODDS_API_KEY="env-odds")).odds_api_key,
                         "env-odds")

    def test_github_token_is_an_optional_credential_and_a_secret(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "github-token"), "w") as f:
                f.write("ghp_FILE\n")
            cfg = load_config(env=_env(CREDENTIALS_DIRECTORY=d, GITHUB_TOKEN="ghp_env"))
        self.assertEqual(cfg.github_token, "ghp_FILE")
        self.assertIn("ghp_FILE", cfg.secrets())
        self.assertEqual(load_config(env=_env(GITHUB_TOKEN="ghp_env")).github_token, "ghp_env")
        cfg = load_config(env=_env())
        self.assertIsNone(cfg.github_token)                 # unprovisioned Pi still boots
        self.assertEqual(cfg.github_repo, "ropats16/fpl-pi-manager")
        self.assertEqual(load_config(env=_env(GAFFER_GITHUB_REPO="o/r")).github_repo, "o/r")

    def test_per_role_model_override_is_a_config_change(self):
        h = load_helper_settings({"GAFFER_HELPER_MODEL_MARKET": "x/other",
                                  "GAFFER_HELPER_MODEL": "x/cheap"})
        self.assertEqual(h.models["market"], "x/other")
        self.assertEqual(h.models["availability"], "x/cheap")
        self.assertEqual(h.models["am"], AM_MODEL)

    def test_zero_or_junk_ceiling_falls_back_to_the_default(self):
        h = load_helper_settings({"GAFFER_HELPER_MAX_TURNS": "0",
                                  "GAFFER_HELPER_MAX_FETCHES": "-3",
                                  "GAFFER_HELPER_MAX_SEARCHES": "ten"})
        self.assertEqual(h.caps, {"fetches": 25, "searches": 15, "turns": 40, "minutes": 15})

    def test_bad_price_table_json_falls_back_to_defaults(self):
        h = load_helper_settings({"GAFFER_PRICE_TABLE": "{nope"})
        self.assertIn("z-ai/glm-5.3-flash", h.prices)

    def test_wake_rails_and_ledger_defaults(self):
        h = load_config(env=_env()).helpers
        self.assertEqual(h.wake_rails, {"calls": 200, "tokens": 5_000_000,
                                        "cost_usd": 1.0, "minutes": 90})
        self.assertEqual(h.ledger, {"search_off_usd": 4.0, "helpers_off_usd": 4.75})

    def test_wake_rails_and_ledger_env_overrides(self):
        h = load_helper_settings(_env(
            GAFFER_WAKE_MAX_CALLS="50", GAFFER_WAKE_MAX_TOKENS="1000000",
            GAFFER_WAKE_MAX_USD="0.5", GAFFER_WAKE_MAX_MINUTES="30",
            GAFFER_LEDGER_SEARCH_OFF_USD="2", GAFFER_LEDGER_HELPERS_OFF_USD="3"))
        self.assertEqual(h.wake_rails, {"calls": 50, "tokens": 1000000,
                                        "cost_usd": 0.5, "minutes": 30.0})
        self.assertEqual(h.ledger, {"search_off_usd": 2.0, "helpers_off_usd": 3.0})

    def test_junk_wake_rails_fall_back_to_defaults(self):
        h = load_helper_settings(_env(
            GAFFER_WAKE_MAX_CALLS="0", GAFFER_WAKE_MAX_TOKENS="-1",
            GAFFER_WAKE_MAX_USD="nope", GAFFER_WAKE_MAX_MINUTES="-2"))
        self.assertEqual(h.wake_rails, {"calls": 200, "tokens": 5_000_000,
                                        "cost_usd": 1.0, "minutes": 90})

    def test_negative_ledger_thresholds_fall_back(self):
        h = load_helper_settings(_env(GAFFER_LEDGER_SEARCH_OFF_USD="-1"))
        self.assertEqual(h.ledger["search_off_usd"], 4.0)

    def test_helpers_off_below_search_off_keeps_both_defaults(self):
        h = load_helper_settings(_env(GAFFER_LEDGER_SEARCH_OFF_USD="5",
                                      GAFFER_LEDGER_HELPERS_OFF_USD="1"))
        self.assertEqual(h.ledger, {"search_off_usd": 4.0, "helpers_off_usd": 4.75})


if __name__ == "__main__":
    unittest.main()
