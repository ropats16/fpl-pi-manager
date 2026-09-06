"""The on-Pi engineer (spec §4–6) at its seams: the workspace ACL (writable set,
`..`, a real symlink escape), the minimal test-child env + secret-scrubbed tail,
the write-gated fix budget and its hard stop, the real-tree re-check before push,
the PR body's green/red `Closes #N`, and `run_build` end to end over a
FakeGitHost + a fake LLM + a fake test_runner. No real subprocess, no network."""

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

    def _tools(self, workspace, fix_turns=2, test_runner=None, scrub=None):
        state = engineer._new_state()
        runner = test_runner or (lambda w, p: (True, "OK"))
        tools = engineer._build_tools(engineer.Issue(1, "t", "b"),
                                      os.path.realpath(workspace), state, fix_turns,
                                      runner, self.logger, scrub=scrub)
        return {t.name: t for t in tools}, state

    def _build(self, replies, test_runner, fix_turns=2):
        """run_build end to end over a FakeGitHost clone of a tiny tree."""
        host = FakeGitHost(url_base="https://github.com/x/y/pull/",
                           clone_source=_small_src())
        n, _ = host.open_issue("Add marker", "Create fpl_marker.py.",
                               labels=["gaffer", "build"])
        data_dir = tempfile.mkdtemp(prefix="eng-data-")
        transport = FakeTransport(llm_replies=replies,
                                  usage={"prompt_tokens": 1000, "completion_tokens": 100})
        res = engineer.run_build(engineer.Issue(n, "Add marker", "Create fpl_marker.py."),
                                 host, self._llm(transport), MODEL, CAPS, fix_turns,
                                 data_dir, engineer.REPO_RULES, self.logger,
                                 test_runner=test_runner)
        return res, host, data_dir, n, transport


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
        for bad in ("deploy/unit.service", "agent/roles/engineer.md", "../evil.py",
                    "season-state.json"):
            self.assertIn("refused", wf(path=bad, content="x"), bad)
        self.assertEqual(state["written"], {"daemon/x.py"})

    def test_symlink_escape_is_refused(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        outside = tempfile.mkdtemp(prefix="eng-out-")
        os.symlink(outside, os.path.join(ws, "daemon"))
        tools, state = self._tools(ws)
        r = tools["write_file"].fn(path="daemon/evil.py", content="pwned")
        self.assertIn("refused", r)
        self.assertIn("outside the workspace", r)
        self.assertFalse(os.path.exists(os.path.join(outside, "evil.py")))
        self.assertEqual(state["written"], set())

    def test_read_grep_stay_in_workspace_and_skip_git(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        os.makedirs(os.path.join(ws, ".git"))
        with open(os.path.join(ws, "daemon", "a.py"), "w") as f:
            f.write("SENTINEL = 1\n")
        with open(os.path.join(ws, ".git", "config"), "w") as f:
            f.write("[core]\n")
        tools, _ = self._tools(ws)
        self.assertIn("SENTINEL", tools["read_file"].fn(path="daemon/a.py"))
        self.assertIn("refused", tools["read_file"].fn(path="../../etc/passwd"))
        self.assertIn(".git", tools["read_file"].fn(path=".git/config"))  # refused
        self.assertIn("daemon/a.py:1", tools["grep"].fn(pattern="SENTINEL"))
        self.assertIn("no matches", tools["grep"].fn(pattern="NOPE"))


# --- test child env + tail scrub (spec §5/§1) -----------------------------------

class TestChildTest(_Base):
    def test_env_is_minimal_and_carries_no_service_secrets(self):
        env = engineer._build_test_env("/ws", "/home")
        self.assertEqual(set(env), {"PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL"})
        self.assertEqual(env["PYTHONPATH"], "/ws")
        self.assertEqual(env["HOME"], "/home")
        for leaked in ("GITHUB_TOKEN", "OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN",
                       "GAFFER_GITHUB_TOKEN", "GH_TOKEN"):
            self.assertNotIn(leaked, env)

    def test_run_tests_tail_is_secret_scrubbed(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        logger = StructuredLogger(stream=io.StringIO(), secrets=["ghp_LEAK"])
        state = engineer._new_state()
        tools = engineer._build_tools(
            engineer.Issue(1, "t", "b"), os.path.realpath(ws), state, 2,
            lambda w, p: (True, "OK — token ghp_LEAK printed"), logger,
            scrub=logger.scrub)
        out = {t.name: t for t in tools}["run_tests"].fn()
        self.assertNotIn("ghp_LEAK", out)
        self.assertIn("[REDACTED]", out)


# --- fix-turn budget, gated on an intervening write (spec §4) --------------------

class FixBudgetTest(_Base):
    def test_third_counted_red_exhausts_and_hard_withholds(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        tools, state = self._tools(ws, fix_turns=2,
                                   test_runner=lambda w, p: (False, "1 failed"))
        rt, wf = tools["run_tests"].fn, tools["write_file"].fn
        for i, expect in enumerate(("fix 1 of 2", "fix 2 of 2"), 1):
            self.assertIn("wrote", wf(path="daemon/a.py", content=str(i)))
            self.assertIn(expect, rt())
        self.assertIn("wrote", wf(path="daemon/a.py", content="3"))
        third = rt()
        self.assertIn("budget", third.lower())
        self.assertTrue(state["exhausted"])
        self.assertEqual(state["reds"], 3)
        r = wf(path="daemon/a.py", content="4")            # withheld
        self.assertIn("fix budget", r.lower())
        with open(os.path.join(ws, "daemon", "a.py")) as f:
            self.assertEqual(f.read(), "3")                # the withheld write didn't land

    def test_two_reds_with_no_write_between_count_once(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        tools, state = self._tools(ws, fix_turns=2,
                                   test_runner=lambda w, p: (False, "1 failed"))
        rt, wf = tools["run_tests"].fn, tools["write_file"].fn
        wf(path="daemon/a.py", content="1")
        self.assertIn("fix 1 of 2", rt())
        self.assertIn("no file changed", rt())             # no write since the last red
        self.assertEqual(state["reds"], 1)                 # not double-counted
        self.assertFalse(state["exhausted"])

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
    def test_green_stages_only_the_diff_and_opens_a_closing_pr(self):
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            tool_call_message("run_tests", {}, "t1"),
            "Done — added fpl_marker.py; suite green."]
        res, host, data_dir, n, _ = self._build(replies, lambda w, p: (True, "OK\n"))
        self.assertEqual(res.status, "green")
        self.assertTrue(res.pr_url)
        self.assertFalse(host.build_prs[0]["draft"])
        self.assertIn(f"Closes #{n}", host.build_prs[0]["body"])
        self.assertEqual(host.pushes[0]["branch"], f"gaffer/build-{n}")
        self.assertEqual(host.pushes[0]["message"], f"Add marker (#{n})")
        self.assertEqual(host.pushes[0]["paths"], ["fpl_marker.py"])   # only the diff
        self.assertTrue(os.path.exists(
            os.path.join(data_dir, "work", f"build-{n}", "fpl_marker.py")))
        self.assertTrue({"build_start", "build_tests", "build_pr"}
                        <= {e["event"] for e in self._events()})

    def test_red_opens_a_draft_without_closes(self):
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            "Tried, but the suite is red."]
        res, host, _, n, _ = self._build(replies, lambda w, p: (False, "1 failed"))
        self.assertEqual(res.status, "red")
        self.assertTrue(host.build_prs[0]["draft"])
        self.assertNotIn("Closes", host.build_prs[0]["body"])

    def test_no_changes_is_a_clean_error(self):
        res, host, _, n, _ = self._build(["Nothing to do here."],
                                         lambda w, p: (True, "OK"))
        self.assertEqual(res.status, "error")
        self.assertEqual(res.reason, "no changes")
        self.assertEqual(host.build_prs, [])
        self.assertEqual(host.pushes, [])
        self.assertEqual([e["event"] for e in self._events()][-1], "build_fail")

    def test_side_effect_file_in_the_tree_aborts_the_push(self):
        # A test that drops a denied file into the workspace: write_file never saw
        # it, but the real-tree re-check (status_paths) must catch it (spec §5).
        def sneaky(workspace, paths):
            d = os.path.join(workspace, ".github", "workflows")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "x.yml"), "w") as f:
                f.write("on: push\n")
            return True, "OK"
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            tool_call_message("run_tests", {}, "t1"),
            "done."]
        res, host, _, n, _ = self._build(replies, sneaky)
        self.assertEqual(res.status, "error")
        self.assertIn("denied path in tree", res.reason)
        self.assertIn(".github/workflows/x.yml", res.reason)
        self.assertEqual(host.pushes, [])
        self.assertEqual(host.build_prs, [])

    def test_spent_budget_hard_stops_before_the_turns_cap(self):
        # Three writes + three reds spend the budget; the loop must stop at once
        # (not consume the trailing tool calls) and open a red draft.
        replies = []
        for i in range(3):
            replies.append(tool_call_message("write_file",
                           {"path": "fpl_marker.py", "content": str(i)}, f"w{i}"))
            replies.append(tool_call_message("run_tests", {}, f"t{i}"))
        # Trailing calls that MUST NOT run once the budget is spent.
        replies += [tool_call_message("read_file", {"path": "fpl_marker.py"}, "r9"),
                    tool_call_message("run_tests", {}, "t9"), "unreached summary"]
        res, host, _, n, transport = self._build(replies, lambda w, p: (False, "fail"),
                                                  fix_turns=2)
        self.assertEqual(res.status, "red")
        self.assertTrue(host.build_prs[0]["draft"])
        self.assertLess(len(transport.llm_requests), len(replies))    # stopped early
        self.assertLess(res.turns, CAPS.turns)

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


# --- hardening after live build #78 (PR #80, 2026-09-06) ---------------------------
# The first live engineer never wrote an implementation: it used run_tests as a
# file-reading harness (an atexit dump of daemon/brief.py into tests/_d*.txt, to
# dodge the read_file cap) and shipped only that harness. Three rails close it.


class PagedReadTest(_Base):
    def _ws(self, lines=300):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        with open(os.path.join(ws, "daemon", "big.py"), "w") as f:
            f.write("".join(f"line{i}\n" for i in range(1, lines + 1)))
        return ws

    def test_default_read_is_the_first_page_with_a_continuation_hint(self):
        tools, _ = self._tools(self._ws())
        out = tools["read_file"].fn(path="daemon/big.py")
        self.assertTrue(out.startswith("line1\n"))
        self.assertIn(f"line{engineer.READ_MAX_LINES}\n", out)
        self.assertNotIn(f"line{engineer.READ_MAX_LINES + 1}\n", out)
        self.assertIn(f"start_line={engineer.READ_MAX_LINES + 1}", out)   # how to page
        self.assertIn("of 300", out)

    def test_start_line_and_max_lines_page_through_a_big_file(self):
        tools, _ = self._tools(self._ws())
        out = tools["read_file"].fn(path="daemon/big.py", start_line=201, max_lines=50)
        self.assertTrue(out.startswith("line201\n"))
        self.assertIn("line250\n", out)
        self.assertNotIn("line251\n", out)
        self.assertIn("start_line=251", out)
        last = tools["read_file"].fn(path="daemon/big.py", start_line=251)
        self.assertIn("line300\n", last)
        self.assertNotIn("start_line=", last)                            # no more pages
        self.assertIn("past the end", tools["read_file"].fn(path="daemon/big.py",
                                                            start_line=400))

    def test_budget_cut_page_reports_only_the_lines_it_emitted(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "daemon"))
        wide = "x" * 3000                                  # ~750 tokens per line
        with open(os.path.join(ws, "daemon", "wide.py"), "w") as f:
            f.write("".join(f"{wide}{i}\n" for i in range(1, 21)))
        tools, _ = self._tools(ws)
        out = tools["read_file"].fn(path="daemon/wide.py")
        shown = [l for l in out.splitlines() if l.startswith("x")]
        self.assertLess(len(shown), 20)                    # the budget cut the page
        self.assertIn(f"lines 1–{len(shown)} of 20", out)
        self.assertIn(f"start_line={len(shown) + 1}", out) # next page = first unseen line
        nxt = tools["read_file"].fn(path="daemon/wide.py", start_line=len(shown) + 1)
        self.assertTrue(nxt.startswith(f"{wide}{len(shown) + 1}\n"))

    def test_small_file_reads_whole_with_no_hint(self):
        tools, _ = self._tools(self._ws(lines=5))
        out = tools["read_file"].fn(path="daemon/big.py")
        self.assertEqual(out, "".join(f"line{i}\n" for i in range(1, 6)))


class NoScratchTest(_Base):
    def test_write_file_refuses_non_python_under_tests(self):
        ws = tempfile.mkdtemp(prefix="eng-ws-")
        os.makedirs(os.path.join(ws, "tests"))
        tools, state = self._tools(ws)
        wf = tools["write_file"].fn
        for bad in ("tests/_d1.txt", "tests/dump.json", "tests/notes.md"):
            out = wf(path=bad, content="x")
            self.assertIn("refused", out, bad)
            self.assertIn("scratch", out, bad)
            self.assertFalse(os.path.exists(os.path.join(ws, bad)), bad)
        self.assertIn("wrote", wf(path="tests/test_new.py", content="import unittest\n"))
        self.assertEqual(state["written"], {"tests/test_new.py"})


class FinishGateTest(_Base):
    def test_tests_only_diff_is_refused_as_no_implementation(self):
        replies = [
            tool_call_message("write_file",
                              {"path": "tests/test_marker.py",
                               "content": "import unittest\n"}, "w1"),
            tool_call_message("run_tests", {}, "t1"),
            "done."]
        res, host, _, n, _ = self._build(replies, lambda w, p: (True, "OK"))
        self.assertEqual(res.status, "error")
        self.assertIn("tests only", res.reason)
        self.assertEqual(host.pushes, [])
        self.assertEqual(host.build_prs, [])

    def test_scratch_file_left_by_a_test_aborts_the_push(self):
        def dumper(workspace, paths):
            with open(os.path.join(workspace, "tests", "_d1.txt"), "w") as f:
                f.write("chunk\n")
            return True, "OK"
        replies = [
            tool_call_message("write_file",
                              {"path": "fpl_marker.py", "content": "VERSION = 1\n"}, "w1"),
            tool_call_message("run_tests", {}, "t1"),
            "done."]
        res, host, _, n, _ = self._build(replies, dumper)
        self.assertEqual(res.status, "error")
        self.assertIn("scratch file", res.reason)
        self.assertIn("tests/_d1.txt", res.reason)
        self.assertEqual(host.pushes, [])


if __name__ == "__main__":
    unittest.main()
