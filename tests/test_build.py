"""Commissioning builds (spec §3 / §5 / §6) at the unit seams: the ```build
block parse/strip, the approval tokens, the path ACL, the spawn argv, the
pending/running state machine incl. dead-pid recovery, and the git-host issue/PR
ops. The loop-level wiring is asserted in tests/test_build_loop.py."""

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.build import (BuildGate, cancel_pending_build, commission_build,
                          is_build_approval, is_build_cancel, is_build_request,
                          parse_build, path_allowed, pid_alive, recover_builds,
                          spawn_build, start_pending_build)
from daemon.logging_setup import StructuredLogger
from daemon.plan import ApprovalStore
from daemon.propose import FakeGitHost

NOW = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
SPEC = "Goal: add a TC-window model.\n\nFiles: fpl_tc_window.py\n\nTests: test_tc.py"
BLOCK = ("On it — spec below.\n\n```build\nticket: new\n"
         "title: TC window model\n---\n" + SPEC + "\n```")


def _logger():
    buf = io.StringIO()
    return StructuredLogger(stream=buf), buf


def _events(buf):
    return [json.loads(l) for l in buf.getvalue().splitlines()]


def _store():
    tmp = tempfile.mkdtemp(prefix="build-store-")
    return ApprovalStore(os.path.join(tmp, "approval-state.json"))


class FakeTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append({"chat_id": chat_id, "text": text})


# --- parse ----------------------------------------------------------------------

class ParseBuildTest(unittest.TestCase):
    def test_new_ticket_parses_and_strips(self):
        req, text = parse_build(BLOCK)
        self.assertTrue(req.is_new)
        self.assertIsNone(req.number)
        self.assertEqual(req.title, "TC window model")
        self.assertTrue(req.spec.startswith("Goal: add a TC-window model."))
        self.assertEqual(text, "On it — spec below.")

    def test_existing_number_ticket(self):
        req, _ = parse_build("```build\nticket: 42\ntitle: fix X\n---\nbody here\n```")
        self.assertFalse(req.is_new)
        self.assertEqual(req.number, 42)
        req2, _ = parse_build("```build\nticket: #42\ntitle: fix X\n---\nbody\n```")
        self.assertEqual(req2.number, 42)

    def test_no_block_leaves_text_untouched(self):
        self.assertEqual(parse_build("plain text"), (None, "plain text"))

    def test_malformed_is_none_and_logged_and_text_untouched(self):
        logger, buf = _logger()
        for bad in ("```build\ntitle: x\n---\nbody\n```",           # no ticket
                    "```build\nticket: new\n---\nbody\n```",         # no title
                    "```build\nticket: new\ntitle: x\n---\n\n```",   # empty spec
                    "```build\nticket: new\ntitle: x\nno sep\n```",  # no ---
                    "```build\nticket: bogus\ntitle: x\n---\nb\n```"):  # bad number
            req, text = parse_build(bad, logger)
            self.assertIsNone(req, bad)
            self.assertEqual(text, bad)
        self.assertTrue(all(e["event"] == "build_malformed" for e in _events(buf)))
        self.assertEqual(len(_events(buf)), 5)


# --- tokens ---------------------------------------------------------------------

class TokenTest(unittest.TestCase):
    def test_is_build_request_only_on_explicit_prefixes(self):
        self.assertTrue(is_build_request("build: add a TC model"))
        self.assertTrue(is_build_request("ticket: 12 please"))
        self.assertTrue(is_build_request("BUILD: caps ok"))
        for no in ("build me a lineup", "how's my team?", "build", "build #3",
                   "should I build a bench?", ""):
            self.assertFalse(is_build_request(no), no)

    def test_is_build_approval(self):
        self.assertEqual(is_build_approval("build #3"), 3)
        self.assertEqual(is_build_approval("build #12"), 12)
        self.assertEqual(is_build_approval("build 4"), 4)
        self.assertEqual(is_build_approval("build"), 0)
        self.assertEqual(is_build_approval("BUILD #7"), 7)
        for no in ("yes", "build: do X", "build a lineup", "cancel build", ""):
            self.assertIsNone(is_build_approval(no), no)

    def test_is_build_cancel(self):
        self.assertTrue(is_build_cancel("cancel build"))
        self.assertTrue(is_build_cancel("  Cancel Build  "))
        for no in ("cancel", "build", "cancel the build", ""):
            self.assertFalse(is_build_cancel(no), no)


# --- path ACL (spec §5) ---------------------------------------------------------

class PathAclTest(unittest.TestCase):
    def test_writable_paths(self):
        for ok in ("daemon/build.py", "tests/test_build.py", "agent/roles/scout.md",
                   "agent/playbooks/analysis.md", "docs/x.md", "plans/y.md",
                   "README.md", "AGENTS.md", "run_pipeline.py", "fpl_tc_window.py"):
            self.assertTrue(path_allowed(ok), ok)

    def test_denied_paths(self):
        for no in ("deploy/gaffer.service", ".github/workflows/ci.yml",
                   "season-state.json", "agent/memory/learnings.md",
                   "agent/reports/gw04/x.md", "agent/roles/engineer.md",
                   "data/projections.csv", "fixtures/squad.json", "agent/GAFFER.md",
                   "../etc/passwd", "daemon/../deploy/x", "/abs/path",
                   ".env", "agent/.hidden/x.md", "root.txt", ""):
            self.assertFalse(path_allowed(no), no)


# --- spawn / pid ----------------------------------------------------------------

class SpawnTest(unittest.TestCase):
    def test_spawn_argv_and_log_and_detached(self):
        import sys
        from daemon.build import REPO_ROOT
        calls = {}

        class FakeProc:
            pid = 4321

        def fake_popen(argv, **kw):
            calls["argv"] = argv
            calls["kw"] = kw
            return FakeProc()

        tmp = tempfile.mkdtemp(prefix="build-spawn-")
        pid = spawn_build(7, tmp, popen=fake_popen)
        self.assertEqual(pid, 4321)
        self.assertEqual(calls["argv"],
                         [sys.executable, "-m", "daemon", "build", "7"])
        self.assertTrue(calls["kw"]["start_new_session"])
        self.assertEqual(calls["kw"]["cwd"], REPO_ROOT)      # child runs from repo root
        self.assertTrue(os.path.exists(os.path.join(tmp, "work", "build-7.log")))

    def test_pid_alive(self):
        self.assertTrue(pid_alive(os.getpid()))
        self.assertFalse(pid_alive(0))
        self.assertFalse(pid_alive(2 ** 22))     # no such pid


# --- state machine + gate ops ---------------------------------------------------

class CommissionTest(unittest.TestCase):
    def test_new_ticket_opens_issue_and_queues(self):
        store, host = _store(), FakeGitHost()
        builds = BuildGate(store, host, tempfile.mkdtemp())
        logger, buf = _logger()
        req, _ = parse_build(BLOCK)
        line = commission_build(builds, req, logger, now=NOW)
        self.assertIn("build #1 queued", line)
        self.assertEqual(store.pending_build["issue"], 1)
        self.assertEqual(store.pending_build["title"], "TC window model")
        self.assertEqual(host.issues[1]["labels"], ["gaffer", "build"])
        # Persisted: a fresh store reads the pending build back.
        self.assertEqual(ApprovalStore(store.path).load().pending_build["issue"], 1)
        self.assertEqual([e["event"] for e in _events(buf)], ["build_queued"])

    def test_second_block_while_pending_is_dropped(self):
        store, host = _store(), FakeGitHost()
        builds = BuildGate(store, host, tempfile.mkdtemp())
        logger, buf = _logger()
        req, _ = parse_build(BLOCK)
        commission_build(builds, req, logger, now=NOW)
        line = commission_build(builds, req, logger, now=NOW)
        self.assertIn("already pending (#1)", line)
        self.assertEqual(len(host.issues), 1)                # no second issue
        self.assertEqual(_events(buf)[-1]["reason"], "already pending")

    def test_no_host_drops_with_fixed_line(self):
        store = _store()
        builds = BuildGate(store, None, tempfile.mkdtemp())
        logger, buf = _logger()
        req, _ = parse_build(BLOCK)
        line = commission_build(builds, req, logger, now=NOW)
        self.assertIn("GitHub token", line)
        self.assertIsNone(store.pending_build)
        self.assertEqual(_events(buf)[-1]["reason"], "no github token")

    def test_existing_ticket_does_not_open_an_issue(self):
        store, host = _store(), FakeGitHost()
        builds = BuildGate(store, host, tempfile.mkdtemp())
        logger, _ = _logger()
        req, _ = parse_build("```build\nticket: 42\ntitle: fix\n---\nbody\n```")
        line = commission_build(builds, req, logger, now=NOW)
        self.assertIn("build #42 queued", line)
        self.assertEqual(store.pending_build["issue"], 42)
        self.assertEqual(host.issues, {})

    def test_start_spawns_sets_running_and_clears_pending(self):
        store, host = _store(), FakeGitHost()
        spawned = {}

        def fake_spawn(n, data_dir):
            spawned["n"], spawned["dir"] = n, data_dir
            return 9999
        builds = BuildGate(store, host, "/tmp/data", spawn=fake_spawn)
        logger, buf = _logger()
        commission_build(builds, parse_build(BLOCK)[0], logger, now=NOW)
        tg = FakeTelegram()
        self.assertTrue(start_pending_build(builds, tg, 42, logger, now=NOW))
        self.assertEqual(spawned, {"n": 1, "dir": "/tmp/data"})
        self.assertEqual(store.running_build["issue"], 1)
        self.assertEqual(store.running_build["pid"], 9999)
        self.assertIsNone(store.pending_build)
        self.assertIn("build #1 started", tg.sent[0]["text"])
        self.assertEqual(_events(buf)[-1]["event"], "build_started")

    def test_start_number_mismatch_is_refused(self):
        store, host = _store(), FakeGitHost()
        spawned = []
        builds = BuildGate(store, host, "/tmp",
                           spawn=lambda n, d: spawned.append(n) or 5)
        logger, _ = _logger()
        commission_build(builds, parse_build(BLOCK)[0], logger, now=NOW)  # #1 pending
        tg = FakeTelegram()
        self.assertTrue(start_pending_build(builds, tg, 42, logger, now=NOW, number=12))
        self.assertIn("no pending build #12", tg.sent[0]["text"])
        self.assertEqual(spawned, [])                       # nothing spawned
        self.assertEqual(store.pending_build["issue"], 1)   # still queued
        # bare build (number 0) starts the single pending one regardless
        self.assertTrue(start_pending_build(builds, tg, 42, logger, now=NOW, number=0))
        self.assertEqual(spawned, [1])

    def test_start_with_nothing_pending_falls_through(self):
        store = _store()
        builds = BuildGate(store, FakeGitHost(), "/tmp", spawn=lambda *a: 1)
        self.assertIsNone(start_pending_build(builds, FakeTelegram(), 42,
                                              _logger()[0], now=NOW))

    def test_start_while_running_refuses(self):
        store, host = _store(), FakeGitHost()
        spawned = []
        builds = BuildGate(store, host, "/tmp",
                           spawn=lambda n, d: spawned.append(n) or 5,
                           alive=lambda pid: True)          # running is live
        logger, _ = _logger()
        commission_build(builds, parse_build(BLOCK)[0], logger, now=NOW)
        tg = FakeTelegram()
        start_pending_build(builds, tg, 42, logger, now=NOW)
        # Queue a second: while one runs (alive), the gate refuses, spawns nothing.
        store.queue_build({"issue": 2, "title": "t", "spec": "s", "queued_at": "x"})
        self.assertTrue(start_pending_build(builds, tg, 42, logger, now=NOW))
        self.assertIn("running — wait", tg.sent[-1]["text"])
        self.assertEqual(spawned, [1])                       # only the first

    def test_dead_running_build_is_finished_then_pending_starts(self):
        # A completed build (dead pid) must not block the next one forever.
        store, host = _store(), FakeGitHost()
        spawned = []
        builds = BuildGate(store, host, "/tmp",
                           spawn=lambda n, d: spawned.append(n) or 7,
                           alive=lambda pid: False)         # prior build finished
        store.run_build({"issue": 1, "pid": 999, "started_at": "x"})
        store.queue_build({"issue": 2, "title": "t", "spec": "s", "queued_at": "x"})
        logger, buf = _logger()
        tg = FakeTelegram()
        self.assertTrue(start_pending_build(builds, tg, 42, logger, now=NOW))
        self.assertEqual(spawned, [2])
        self.assertEqual(store.running_build["issue"], 2)
        kinds = [e["event"] for e in _events(buf)]
        self.assertIn("build_finished", kinds)
        self.assertIn("build_started", kinds)

    def test_cancel_pending_only_clears(self):
        store, host = _store(), FakeGitHost()
        builds = BuildGate(store, host, "/tmp", spawn=lambda *a: 5)
        logger, buf = _logger()
        commission_build(builds, parse_build(BLOCK)[0], logger, now=NOW)
        tg = FakeTelegram()
        self.assertTrue(cancel_pending_build(builds, tg, 42, logger))
        self.assertIsNone(store.pending_build)
        self.assertIn("build #1 cancelled", tg.sent[0]["text"])

    def test_cancel_nothing_falls_through(self):
        store = _store()
        builds = BuildGate(store, FakeGitHost(), "/tmp")
        self.assertIsNone(cancel_pending_build(builds, FakeTelegram(), 42, _logger()[0]))

    def test_cancel_kills_a_running_pid(self):
        # Seams faked: no real process. `alive` reports the running build live,
        # `kill` records the pid the cancel would signal.
        store, host = _store(), FakeGitHost()
        killed = []
        builds = BuildGate(store, host, "/tmp", spawn=lambda n, d: 4321,
                           alive=lambda pid: True, kill=killed.append)
        logger, _ = _logger()
        commission_build(builds, parse_build(BLOCK)[0], logger, now=NOW)
        start_pending_build(builds, FakeTelegram(), 42, logger, now=NOW)
        tg = FakeTelegram()
        self.assertTrue(cancel_pending_build(builds, tg, 42, logger))
        self.assertEqual(killed, [4321])                    # the pgroup was signalled
        self.assertIsNone(store.running_build)
        self.assertIsNone(store.pending_build)
        self.assertIn("cancelled", tg.sent[0]["text"])


# --- dead-pid recovery ----------------------------------------------------------

class RecoverTest(unittest.TestCase):
    def test_dead_running_build_is_cleared_and_pinged(self):
        store = _store()
        store.run_build({"issue": 5, "pid": 2 ** 22, "started_at": "x"})  # dead pid
        tg = FakeTelegram()
        logger, buf = _logger()
        n = recover_builds(store, tg, {42, 7}, logger)
        self.assertEqual(n, 5)
        self.assertIsNone(ApprovalStore(store.path).load().running_build)
        self.assertEqual(len(tg.sent), 2)                     # both chats pinged
        self.assertIn('build #5 died with the daemon restart', tg.sent[0]["text"])
        self.assertEqual(_events(buf)[0]["event"], "build_recovered")

    def test_live_running_build_is_left_alone(self):
        store = _store()
        store.run_build({"issue": 5, "pid": os.getpid(), "started_at": "x"})
        tg = FakeTelegram()
        self.assertIsNone(recover_builds(store, tg, {42}, _logger()[0]))
        self.assertEqual(tg.sent, [])
        self.assertEqual(store.running_build["issue"], 5)

    def test_no_running_build_is_a_noop(self):
        store = _store()
        self.assertIsNone(recover_builds(store, FakeTelegram(), {42}, _logger()[0]))


# --- git host issue/PR ops (spec §6) --------------------------------------------

class FakeGitHostOpsTest(unittest.TestCase):
    def test_open_issue_increments_and_records(self):
        host = FakeGitHost()
        n1, url1 = host.open_issue("A", "body A", labels=["gaffer", "build"])
        n2, url2 = host.open_issue("B", "body B")
        self.assertEqual((n1, n2), (1, 2))
        self.assertIn("/issues/1", url1)
        self.assertEqual(host.issue_body(1), ("A", "body A"))
        self.assertEqual(host.issues[1]["labels"], ["gaffer", "build"])

    def test_issue_and_pr_status_strings(self):
        host = FakeGitHost(issues={3: {"title": "T", "body": "B", "labels": ["x"],
                                       "state": "open", "comments": ["hi"]}},
                           prs={9: {"state": "OPEN", "draft": True,
                                    "mergeable": "MERGEABLE", "checks": "pass"}})
        self.assertIn("open · T", host.issue_status(3))
        self.assertIn("last: hi", host.issue_status(3))
        self.assertIn("draft=True", host.pr_status(9))
        self.assertIn("mergeable=MERGEABLE", host.pr_status(9))

    def test_unknown_issue_or_pr_raises(self):
        host = FakeGitHost()
        from daemon.propose import GitHostError
        self.assertRaises(GitHostError, host.issue_body, 99)
        self.assertRaises(GitHostError, host.pr_status, 99)


class GhGitHostOpsTest(unittest.TestCase):
    """The real runner's issue/PR ops over a fake subprocess: argv + token only
    in the child env, output parsed."""

    TOKEN = "ghp_SECRET"

    def _host(self, outputs):
        from daemon.propose import GhGitHost
        calls = []

        def run(argv, env, cwd):
            calls.append((argv, env, cwd))
            for match, rc, out, err in outputs:
                if match in argv:
                    return rc, out, err
            return 0, "", ""
        return GhGitHost(tempfile.mkdtemp(prefix="repo-"), self.TOKEN,
                         repo="ropats16/fpl-pi-manager", run=run), calls

    def test_open_issue_parses_number_from_url(self):
        host, calls = self._host([
            ("create", 0, "https://github.com/ropats16/fpl-pi-manager/issues/12\n", "")])
        n, url = host.open_issue("Title", "spec body", labels=["gaffer", "build"])
        self.assertEqual(n, 12)
        create = next(a for a, _, _ in calls if "create" in a)
        self.assertEqual(create[:4], ["gh", "issue", "create", "--repo"])
        self.assertIn("--label", create)
        # spec body never on the command line
        self.assertNotIn("spec body", " ".join(create))
        for _, env, _ in calls:
            self.assertEqual(env["GH_TOKEN"], self.TOKEN)

    def test_issue_body_and_status_json(self):
        host, _ = self._host([
            ("view", 0, json.dumps({"title": "T", "body": "the spec"}), "")])
        self.assertEqual(host.issue_body(12), ("T", "the spec"))

    def test_pr_status_summarises_checks(self):
        host, _ = self._host([("view", 0, json.dumps({
            "state": "OPEN", "isDraft": True, "mergeable": "MERGEABLE",
            "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}]}),
            "")])
        s = host.pr_status(4)
        self.assertIn("draft=True", s)
        self.assertIn("SUCCESS, FAILURE", s)


if __name__ == "__main__":
    unittest.main()
