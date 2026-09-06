"""The on-Pi engineer (spec §4–6) at its seams: the workspace ACL (the writable
set, `..`, and a real symlink escape), the test-fix budget, the PR body's
green/red `Closes #N`, and `run_build` end to end (clone → tool loop → tests →
push → PR) over a FakeGitHost + a fake LLM + a fake test_runner. No real
subprocess, no network (AGENTS.md rule)."""

import io
import json
import os
import tempfile
import unittest

from daemon import engineer
from daemon.agent import Caps
from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.propose import FakeGitHost
from tests.fakes import FakeTransport, tool_call_message

PRICES = {"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25}}
MODEL = "z-ai/glm-5.3-flash"
CAPS = Caps(turns=40, minutes=25, cost_usd=0.60)


def _small_src():
    """A tiny real-shaped repo tree (a tests/ folder) for FakeGitHost to clone."""
    src = tempfile.mkdtemp(prefix="eng-src-")
    os.makedirs(os.path.join(src, "tests"))
    with open(os.path.join(src, "tests", "test_placeholder.py"), "w") as f:
        f.write("import unittest\n\n\nclass T(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n")
    return src


class _Base(unittest.TestCase):
    def setUp(self):
        self.logbuf = io.StringIO()
        self.logger = StructuredLogger(stream=self.logbuf, secrets=[])

    def _llm(self, transport):
        return LLM(api_key="K", model=MODEL, transport=transport, logger=self.logger,
                   prices=PRICES, wake_id="w1")

    def _events(self, kind=None):
        ev = [json.loads(l) for l in self.logbuf.getvalue().splitlines()]
        return [e for e in ev if kind is None or e["event"] == kind]

    def _tools(self, workspace, fix_turns=2, test_runner=None):
        state = engineer._new_state()
        runner = test_runner or (lambda w, p: (True, "OK"))
        tools = engineer._build_tools(engineer.Issue(1, "t", "b"),
                                      os.path.realpath(workspace), state, fix_turns,
                                      runner, self.logger)
        return {t.name: t for t in tools}, state


# --- workspace ACL (spec §5) ----------------------------------------------------

class AclTest(_Base):
    def test_writable_denied_and_dotdot(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        tools, state = self._tools(ws)
        wf = tools["write_file"].fn
        self.assertIn("wrote", wf(path="daemon/x.py", content="x = 1\n"))
        self.assertIn("daemon/x.py", state["written"])
        self.assertTrue(os.path.exists(os.path.join(ws, "daemon", "x.py")))
        # denied directory, the engineer's own role file, and a `..` escape
        for bad in ("deploy/unit.service", "agent/roles/engineer.md", "../evil.py",
                    "season-state.json"):
            self.assertIn("refused", wf(path=bad, content="x"), bad)
        self.assertEqual(state["written"], {"daemon/x.py"})

    def test_symlink_escape_is_refused(self):
        # `daemon` is a symlink out of the workspace: path_allowed('daemon/..')
        # passes lexically, but the realpath check catches it (spec §5).
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        outside = tempfile.mkdtemp(prefix="eng-out-")
        os.symlink(outside, os.path.join(ws, "daemon"))
        tools, state = self._tools(ws)
        r = tools["write_file"].fn(path="daemon/evil.py", content="pwned")
        self.assertIn("refused", r)
        self.assertIn("outside the workspace", r)
        self.assertFalse(os.path.exists(os.path.join(outside, "evil.py")))
        self.assertEqual(state["written"], set())

    def test_read_and_grep_stay_in_the_workspace(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        with open(os.path.join(ws, "daemon", "a.py"), "w") as f:
            f.write("SENTINEL = 1\n")
        tools, _ = self._tools(ws)
        self.assertIn("SENTINEL", tools["read_file"].fn(path="daemon/a.py"))
        self.assertIn("refused", tools["read_file"].fn(path="../../etc/passwd"))
        self.assertIn("daemon/a.py:1", tools["grep"].fn(pattern="SENTINEL"))
        self.assertIn("no matches", tools["grep"].fn(pattern="NOPE"))


# --- fix-turn budget (spec §4) --------------------------------------------------

class FixBudgetTest(_Base):
    def test_third_red_exhausts_and_withholds_writes(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        tools, state = self._tools(ws, fix_turns=2,
                                   test_runner=lambda w, p: (False, "1 failed"))
        rt, wf = tools["run_tests"].fn, tools["write_file"].fn
        self.assertIn("wrote", wf(path="daemon/a.py", content="1"))
        self.assertIn("fix 1 of 2", rt())
        self.assertIn("wrote", wf(path="daemon/a.py", content="2"))
        self.assertIn("fix 2 of 2", rt())
        third = rt()                              # the 3rd red spends the budget
        self.assertIn("budget", third.lower())
        self.assertTrue(state["exhausted"])
        # Further writes are withheld with a fixed result, and nothing is written.
        r = wf(path="daemon/a.py", content="3")
        self.assertIn("fix budget", r.lower())
        with open(os.path.join(ws, "daemon", "a.py")) as f:
            self.assertEqual(f.read(), "2")       # the withheld write did not land

    def test_green_run_reports_pass(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        tools, state = self._tools(ws, test_runner=lambda w, p: (True, "OK"))
        self.assertIn("GREEN", tools["run_tests"].fn())
        self.assertEqual(state["reds"], 0)


# --- PR body (spec §4) ----------------------------------------------------------

class PrBodyTest(_Base):
    def test_closes_only_when_green(self):
        issue = engineer.Issue(9, "TC window", "the full spec")
        green = engineer._pr_body(issue, "OK", 4, 0.03, green=True)
        self.assertIn("the full spec", green)
        self.assertIn("Closes #9", green)
        red = engineer._pr_body(issue, "1 failed", 7, 0.05, green=False)
        self.assertNotIn("Closes #9", red)
        self.assertIn("1 failed", red)


# --- run_build end to end -------------------------------------------------------

class RunBuildTest(_Base):
    def _build(self, replies, test_runner, issue_num=1):
        host = FakeGitHost(url_base="https://github.com/x/y/pull/",
                           clone_source=_small_src())
        n, _ = host.open_issue("Add marker", "Create fpl_marker.py.",
                               labels=["gaffer", "build"])
        data_dir = tempfile.mkdtemp(prefix="eng-data-")
        transport = FakeTransport(llm_replies=replies,
                                  usage={"prompt_tokens": 1000, "completion_tokens": 100})
        res = engineer.run_build(engineer.Issue(n, "Add marker", "Create fpl_marker.py."),
                                 host, self._llm(transport), MODEL, CAPS, 2, data_dir,
                                 engineer.REPO_RULES, self.logger,
                                 test_runner=test_runner)
        return res, host, data_dir, n

    def test_green_pushes_and_opens_a_closing_pr(self):
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            tool_call_message("run_tests", {}, "t1"),
            "Done — added fpl_marker.py; suite green."]
        res, host, data_dir, n = self._build(replies, lambda w, p: (True, "OK\n"))
        self.assertEqual(res.status, "green")
        self.assertTrue(res.pr_url)
        self.assertEqual(len(host.build_prs), 1)
        self.assertFalse(host.build_prs[0]["draft"])
        self.assertIn(f"Closes #{n}", host.build_prs[0]["body"])
        self.assertEqual(host.pushes[0]["branch"], f"gaffer/build-{n}")
        self.assertEqual(host.pushes[0]["message"], f"Add marker (#{n})")
        self.assertTrue(os.path.exists(
            os.path.join(data_dir, "work", f"build-{n}", "fpl_marker.py")))
        kinds = {e["event"] for e in self._events()}
        self.assertTrue({"build_start", "build_tests", "build_pr"} <= kinds)

    def test_red_opens_a_draft_without_closes(self):
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            "Tried, but the suite is red."]
        res, host, _, n = self._build(replies, lambda w, p: (False, "1 failed"))
        self.assertEqual(res.status, "red")
        self.assertTrue(host.build_prs[0]["draft"])
        self.assertNotIn("Closes", host.build_prs[0]["body"])

    def test_no_changes_is_a_clean_error(self):
        res, host, _, n = self._build(["Nothing to do here."],
                                      lambda w, p: (True, "OK"))
        self.assertEqual(res.status, "error")
        self.assertEqual(res.reason, "no changes")
        self.assertEqual(host.build_prs, [])
        self.assertEqual(host.pushes, [])
        self.assertEqual([e["event"] for e in self._events()][-1], "build_fail")

    def test_clone_failure_is_a_clean_error(self):
        class BoomHost(FakeGitHost):
            def clone(self, dest, branch):
                raise RuntimeError("network down")
        host = BoomHost()
        n, _ = host.open_issue("T", "b")
        transport = FakeTransport(llm_replies=["x"])
        res = engineer.run_build(engineer.Issue(n, "T", "b"), host, self._llm(transport),
                                 MODEL, CAPS, 2, tempfile.mkdtemp(), engineer.REPO_RULES,
                                 self.logger, test_runner=lambda w, p: (True, "OK"))
        self.assertEqual(res.status, "error")
        self.assertIn("clone failed", res.reason)


if __name__ == "__main__":
    unittest.main()
