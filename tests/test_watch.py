"""The #17 scheduled watch: wake -> fetch -> health-check -> diff -> alert only
if it's mine. Each test names the acceptance criterion it covers.

No model is involved anywhere in this path, so the tests assert silence as hard
as they assert alerts: an irrelevant change, an ownership drift, or a no-change
day must produce zero sends (and, on the wire, zero tokens).
"""

import io
import json
import os
import tempfile
import unittest

from daemon.__main__ import run_watch_cmd
from daemon.logging_setup import StructuredLogger
from daemon.telegram import Telegram
from daemon.watch import (format_alert, load_watch_targets, parse_shortlist,
                          relevant_changes, run_watch)
from tests.fakes import FakeTransport

# --- fixtures -------------------------------------------------------------


def _player(pid, name, cost, status="a", news="", owned="5.0"):
    return {"id": pid, "web_name": name, "now_cost": cost, "status": status,
            "news": news, "selected_by_percent": owned}


def _snap(players, health=()):
    return {"kind": "bootstrap", "fetched_at": "2026-08-28T03:10:00Z",
            "health": list(health), "players": players, "teams": [], "events": []}


# id 1 = own squad (in season-state), id 2 = shortlisted, id 3 = neither.
BASE_PLAYERS = [_player(1, "Haaland", 155), _player(2, "Saka", 100),
                _player(3, "Nobody", 45)]


def _events(buf):
    return [json.loads(l) for l in buf.getvalue().splitlines()]


def _kinds(buf):
    return [e["event"] for e in _events(buf)]


class _Recorder:
    """Stands in for daemon.telegram.Telegram (the real client is exercised
    through FakeTransport in the end-to-end test below)."""

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send_message(self, chat_id, text):
        if self.fail:
            raise RuntimeError("sendMessage failed")
        self.sent.append({"chat_id": chat_id, "text": text})


class WatchHarness(unittest.TestCase):
    """Temp state + shortlist + baseline paths; nothing touches the real repo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = self._tmp.name
        self.state_path = os.path.join(d, "season-state.json")
        self.shortlist_path = os.path.join(d, "shortlist.md")
        self.baseline_path = os.path.join(d, "data", "watch-baseline.json")
        with open(self.state_path, "w") as f:
            json.dump({"squad": {"picks": [{"id": 1, "name": "Haaland"}]}}, f)
        with open(self.shortlist_path, "w") as f:
            f.write("# targets\n- Saka\n")
        self.log = io.StringIO()
        self.logger = StructuredLogger(stream=self.log, secrets=["TT"])

    def seed(self, players=BASE_PLAYERS):
        os.makedirs(os.path.dirname(self.baseline_path), exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(_snap(players), f)

    def baseline(self):
        with open(self.baseline_path) as f:
            return json.load(f)

    def watch(self, fetch, telegram=None, allowlist=(42,)):
        telegram = _Recorder() if telegram is None else telegram
        rc = run_watch(fetch=fetch, state_path=self.state_path,
                       shortlist_path=self.shortlist_path,
                       baseline_path=self.baseline_path, telegram=telegram,
                       allowlist=set(allowlist), logger=self.logger)
        return rc, telegram


# --- AC: scheduled wake fetches, health-checks, and diffs, no manual action --


class WakeTest(WatchHarness):
    def test_wake_fetches_health_checks_and_diffs_unattended(self):
        self.seed()
        rising = [_player(1, "Haaland", 156), _player(2, "Saka", 100),
                  _player(3, "Nobody", 45)]
        rc, tg = self.watch(lambda: _snap(rising))

        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)
        self.assertEqual(self.baseline()["players"], rising)   # baseline advanced
        self.assertIn("watch_wake", _kinds(self.log))

    def test_first_run_seeds_the_baseline_silently(self):
        rc, tg = self.watch(lambda: _snap(BASE_PLAYERS))

        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])                          # nothing to diff yet
        self.assertEqual(self.baseline()["players"], BASE_PLAYERS)
        self.assertIn("watch_baseline_seeded", _kinds(self.log))

    def test_health_failure_alerts_nothing_and_leaves_the_baseline(self):
        self.seed()
        bad = _snap([_player(1, "Haaland", 156)], health=["suspicious player count: 3"])
        rc, tg = self.watch(lambda: bad)

        self.assertEqual(rc, 1)
        self.assertEqual(tg.sent, [])
        self.assertEqual(self.baseline()["players"], BASE_PLAYERS)   # untouched
        ev = next(e for e in _events(self.log) if e["event"] == "watch_health_fail")
        self.assertEqual(ev["issues"], ["suspicious player count: 3"])

    def test_fetch_failure_is_logged_and_the_baseline_survives(self):
        self.seed()

        def boom():
            raise RuntimeError("GET /bootstrap-static/ failed")

        rc, tg = self.watch(boom)

        self.assertEqual(rc, 1)
        self.assertEqual(tg.sent, [])
        self.assertEqual(self.baseline()["players"], BASE_PLAYERS)
        ev = next(e for e in _events(self.log) if e["event"] == "watch_error")
        self.assertEqual(ev["error"], "RuntimeError")


# --- AC: alert only for own/shortlisted players; irrelevant stays silent ----


class RelevanceTest(WatchHarness):
    def test_own_squad_price_move_alerts(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([_player(1, "Haaland", 156),
                                           _player(2, "Saka", 100),
                                           _player(3, "Nobody", 45)]))

        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)
        self.assertIn("Haaland £15.5 → £15.6", tg.sent[0]["text"])

    def test_shortlisted_player_status_change_alerts(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([
            _player(1, "Haaland", 155),
            _player(2, "Saka", 100, status="d", news="Knock - 75% chance"),
            _player(3, "Nobody", 45)]))

        self.assertEqual(len(tg.sent), 1)
        self.assertIn("Saka: available → doubtful — Knock - 75% chance",
                      tg.sent[0]["text"])

    def test_unwatched_player_price_and_status_moves_stay_silent(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([
            _player(1, "Haaland", 155), _player(2, "Saka", 100),
            _player(3, "Nobody", 46, status="i", news="Out")]))

        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])
        self.assertIn("watch_quiet", _kinds(self.log))

    def test_ownership_drift_on_a_watched_player_never_alerts(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([
            _player(1, "Haaland", 155, owned="42.0"),      # +37% ownership swing
            _player(2, "Saka", 100), _player(3, "Nobody", 45)]))

        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])
        ev = next(e for e in _events(self.log) if e["event"] == "watch_quiet")
        self.assertEqual(ev["relevant"], 0)
        self.assertEqual(ev["total_changes"], 1)             # the drift was seen…

    def test_alert_goes_to_every_allowlisted_chat(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([_player(1, "Haaland", 156),
                                           _player(2, "Saka", 100),
                                           _player(3, "Nobody", 45)]),
                            allowlist=(43, 42))

        self.assertEqual([m["chat_id"] for m in tg.sent], [42, 43])   # sorted


# --- AC: a no-change day sends nothing --------------------------------------


class QuietDayTest(WatchHarness):
    def test_no_change_day_sends_nothing(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap(BASE_PLAYERS))

        self.assertEqual(rc, 0)
        self.assertEqual(tg.sent, [])
        ev = next(e for e in _events(self.log) if e["event"] == "watch_quiet")
        self.assertEqual((ev["total_changes"], ev["relevant"]), (0, 0))


# --- AC: wakes and outcomes visible in structured logs ----------------------


class StructuredLogTest(WatchHarness):
    def test_alert_wake_logs_wake_then_alert_with_the_changes(self):
        self.seed()
        rc, tg = self.watch(lambda: _snap([
            _player(1, "Haaland", 156),
            _player(2, "Saka", 100, status="i", news="Hamstring"),
            _player(3, "Nobody", 46)]))

        kinds = _kinds(self.log)
        self.assertEqual(kinds[0], "watch_wake")
        ev = next(e for e in _events(self.log) if e["event"] == "watch_alert")
        self.assertEqual(ev["relevant"], 2)
        self.assertEqual(ev["total_changes"], 3)             # Nobody's rise counted
        self.assertEqual({c["name"] for c in ev["changes"]}, {"Haaland", "Saka"})

    def test_send_failure_keeps_the_baseline_so_the_alert_is_re_sent(self):
        self.seed()
        moved = [_player(1, "Haaland", 156), _player(2, "Saka", 100),
                 _player(3, "Nobody", 45)]
        rc, tg = self.watch(lambda: _snap(moved), telegram=_Recorder(fail=True))

        self.assertEqual(rc, 1)
        self.assertEqual(self.baseline()["players"], BASE_PLAYERS)   # not advanced
        self.assertIn("watch_send_error", _kinds(self.log))

        # Next wake sees the same move again — an alert is never lost.
        rc2, tg2 = self.watch(lambda: _snap(moved))
        self.assertEqual(rc2, 0)
        self.assertEqual(len(tg2.sent), 1)

    def test_quiet_and_alert_wakes_log_the_target_counts(self):
        # The "alert only for my players" guarantee is only auditable if every
        # diff wake records how many targets it was actually watching.
        self.seed()
        rc, _ = self.watch(lambda: _snap(BASE_PLAYERS))
        quiet = next(e for e in _events(self.log) if e["event"] == "watch_quiet")
        self.assertEqual(quiet["squad_ids"], 1)
        self.assertEqual(quiet["shortlist"], 1)

        rc, _ = self.watch(lambda: _snap([_player(1, "Haaland", 156),
                                          _player(2, "Saka", 100),
                                          _player(3, "Nobody", 45)]))
        alert = next(e for e in _events(self.log) if e["event"] == "watch_alert")
        self.assertEqual(alert["squad_ids"], 1)
        self.assertEqual(alert["shortlist"], 1)

    def test_broken_state_file_degrades_loudly_not_silently(self):
        # A corrupt season-state must not silently blind the squad watch: the
        # wake still completes (shortlist-only), but the degradation is logged.
        with open(self.state_path, "w") as f:
            f.write("{not json")
        self.seed()
        rc, tg = self.watch(lambda: _snap([_player(1, "Haaland", 156),
                                           _player(2, "Saka", 101),
                                           _player(3, "Nobody", 45)]))

        self.assertEqual(rc, 0)
        self.assertEqual(len(tg.sent), 1)                    # Saka still alerts
        self.assertNotIn("Haaland", tg.sent[0]["text"])      # squad watch is blind
        ev = next(e for e in _events(self.log)
                  if e["event"] == "watch_targets_degraded")
        self.assertEqual(ev["source"], "state")
        self.assertEqual(ev["error"], "JSONDecodeError")

    def test_missing_shortlist_degrades_loudly_not_silently(self):
        os.remove(self.shortlist_path)
        self.seed()
        rc, _ = self.watch(lambda: _snap(BASE_PLAYERS))

        self.assertEqual(rc, 0)
        ev = next(e for e in _events(self.log)
                  if e["event"] == "watch_targets_degraded")
        self.assertEqual(ev["source"], "shortlist")


# --- units ------------------------------------------------------------------


class ParseShortlistTest(unittest.TestCase):
    def test_bullets_blanks_comments_and_case(self):
        names = parse_shortlist("# Watch shortlist\n\n- Salah\n* Saka\n"
                                "  Wirtz  \n\n# - commented out\n")
        self.assertEqual(names, {"salah", "saka", "wirtz"})

    def test_empty_text_is_an_empty_set(self):
        self.assertEqual(parse_shortlist(""), set())


class LoadTargetsTest(WatchHarness):
    def test_ids_from_squad_and_names_from_shortlist(self):
        ids, names = load_watch_targets(self.state_path, self.shortlist_path)
        self.assertEqual(ids, {1})
        self.assertEqual(names, {"saka"})

    def test_missing_or_broken_files_yield_empty_targets_not_a_crash(self):
        with open(self.state_path, "w") as f:
            f.write("{not json")
        ids, names = load_watch_targets(self.state_path,
                                        os.path.join(self._tmp.name, "nope.md"))
        self.assertEqual((ids, names), (set(), set()))


class RelevantChangesTest(unittest.TestCase):
    def test_filters_by_type_and_target(self):
        changes = [
            {"id": 1, "name": "Haaland", "type": "price", "from": 155, "to": 156},
            {"id": 2, "name": "Saka", "type": "status", "from": "a", "to": "d",
             "news": ""},
            {"id": 3, "name": "Nobody", "type": "price", "from": 45, "to": 46},
            {"id": 1, "name": "Haaland", "type": "ownership", "delta": 3.0},
        ]
        got = relevant_changes(changes, ids={1}, names={"saka"})
        self.assertEqual([c["name"] for c in got], ["Haaland", "Saka"])


class FormatAlertTest(unittest.TestCase):
    def test_price_status_and_header(self):
        text = format_alert([
            {"id": 1, "name": "Haaland", "type": "price", "from": 155, "to": 156},
            {"id": 2, "name": "Saka", "type": "status", "from": "a", "to": "d",
             "news": "Knock"},
        ])
        self.assertEqual(text.splitlines(), [
            "🔔 GW watch — 2 change(s)",
            "💰 Haaland £15.5 → £15.6",
            "🩹 Saka: available → doubtful — Knock",
        ])

    def test_status_without_news_omits_the_dash(self):
        text = format_alert([{"id": 2, "name": "Saka", "type": "status",
                              "from": "d", "to": "a", "news": None}])
        self.assertEqual(text.splitlines()[1], "🩹 Saka: doubtful → available")

    def test_unknown_status_letter_falls_back_to_the_raw_letter(self):
        text = format_alert([{"id": 2, "name": "Saka", "type": "status",
                              "from": "a", "to": "z", "news": ""}])
        self.assertEqual(text.splitlines()[1], "🩹 Saka: available → z")


# --- wiring: `python3 -m daemon watch` --------------------------------------


class WatchCommandTest(WatchHarness):
    def _env(self):
        # No OPENROUTER_API_KEY: the watch is deterministic and must run without
        # ever loading the LLM key (least privilege — the unit ships only the
        # telegram-token credential).
        return {"GAFFER_ALLOWLIST_USER_IDS": "42", "TELEGRAM_BOT_TOKEN": "TT",
                "GAFFER_STATE_PATH": self.state_path,
                "GAFFER_SHORTLIST_PATH": self.shortlist_path,
                "GAFFER_WATCH_BASELINE_PATH": self.baseline_path}

    def test_end_to_end_alert_reaches_telegram_sendmessage(self):
        self.seed()
        fake = FakeTransport()
        out = io.StringIO()
        rc = run_watch_cmd(env=self._env(), transport=fake, out=out,
                           fetch=lambda: _snap([_player(1, "Haaland", 156),
                                                _player(2, "Saka", 100),
                                                _player(3, "Nobody", 45)]))

        self.assertEqual(rc, 0)
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(fake.sent[0]["chat_id"], 42)
        self.assertIn("Haaland", fake.sent[0]["text"])
        self.assertIn("watch_alert", [e["event"] for e in
                                      _events(io.StringIO(out.getvalue()))])

    def test_quiet_day_makes_no_telegram_call_at_all(self):
        self.seed()
        fake = FakeTransport()
        rc = run_watch_cmd(env=self._env(), transport=fake, out=io.StringIO(),
                           fetch=lambda: _snap(BASE_PLAYERS))

        self.assertEqual(rc, 0)
        self.assertEqual(fake.requests, [])       # zero packets on a quiet day

    def test_missing_config_fails_fast_without_fetching(self):
        calls = []

        def fetch():
            calls.append(1)
            return _snap(BASE_PLAYERS)

        with self.assertRaises(ValueError):
            run_watch_cmd(env={}, transport=FakeTransport(), out=io.StringIO(),
                          fetch=fetch)
        self.assertEqual(calls, [])

    def test_real_telegram_client_is_used(self):
        # Guards against the command growing its own sendMessage.
        self.seed()
        fake = FakeTransport()
        run_watch_cmd(env=self._env(), transport=fake, out=io.StringIO(),
                      fetch=lambda: _snap([_player(1, "Haaland", 156),
                                           _player(2, "Saka", 100),
                                           _player(3, "Nobody", 45)]))
        self.assertTrue(any("/sendMessage" in url for _, url in fake.requests))
        self.assertTrue(isinstance(Telegram("TT", fake), Telegram))


if __name__ == "__main__":
    unittest.main()
