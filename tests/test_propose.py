"""Role proposal via auto-PR (#55): the ```propose block, the roles-dir ACL,
the one propose path over the recording fake runner, and the real git/gh
runner over a fake subprocess — asserted on what would leave the box (argv,
env, files in the worktree), never on loop internals."""

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from daemon.logging_setup import StructuredLogger
from daemon.propose import (FakeGitHost, GhGitHost, GitHostError, Proposal,
                            parse_proposal, path_violation, run_propose, slugify)

NOW = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
ROLE_MD = "# Chips analyst\n\nWatch chip timing across the roster.\n"
BLOCK = ("Roster gap noted.\n\n```propose\nname: Chips analyst\n"
         "evidence: no seat covers chip timing; cap_hit on availability 3 GWs running\n"
         "---\n" + ROLE_MD + "```\n")


def _logger(secrets=()):
    buf = io.StringIO()
    return StructuredLogger(stream=buf, secrets=list(secrets)), buf


def _events(buf):
    return [json.loads(l) for l in buf.getvalue().splitlines()]


class SlugTest(unittest.TestCase):
    def test_slug_is_ascii_lower_hyphen(self):
        self.assertEqual(slugify("Chips analyst!"), "chips-analyst")
        self.assertEqual(slugify("  ../../etc  "), "etc")
        self.assertEqual(slugify("***"), "")


class ParseProposalTest(unittest.TestCase):
    def test_block_parses_to_a_proposal_and_is_stripped(self):
        p, text = parse_proposal(BLOCK)
        self.assertEqual(p.name, "Chips analyst")
        self.assertEqual(p.slug, "chips-analyst")
        self.assertEqual(p.branch, "gaffer/chips-analyst")
        self.assertEqual(p.path, "agent/roles/chips-analyst.md")
        self.assertEqual(p.note_path, "agent/roles/chips-analyst.evidence.md")
        self.assertIn("cap_hit", p.evidence)
        self.assertTrue(p.role_body.startswith("# Chips analyst"))
        self.assertEqual(text, "Roster gap noted.")

    def test_explicit_path_is_kept_for_the_acl_to_judge(self):
        p, _ = parse_proposal("```propose\nname: x\npath: daemon/evil.py\n---\nbody\n```")
        self.assertEqual(p.path, "daemon/evil.py")

    def test_no_block_or_unreadable_block_leaves_text_untouched(self):
        self.assertEqual(parse_proposal("plain"), (None, "plain"))
        bad = "```propose\nevidence: only\n---\nbody\n```"
        self.assertEqual(parse_proposal(bad), (None, bad))          # no name
        bad2 = "```propose\nname: x\nno separator\n```"
        self.assertEqual(parse_proposal(bad2), (None, bad2))


class PathAclTest(unittest.TestCase):
    def test_roles_markdown_is_allowed(self):
        self.assertIsNone(path_violation("agent/roles/analyst-chips.md"))
        self.assertIsNone(path_violation("agent/roles/analyst-availability.md"))  # changed file

    def test_everything_else_is_refused(self):
        for rel in ("daemon/evil.py", "agent/GAFFER.md", "agent/roles/../GAFFER.md",
                    "/agent/roles/x.md", "agent/roles/.hidden.md", "agent/roles/x.py",
                    "agent/roles//x.md", "deploy/fpl-gaffer.service", "", "agent/roles"):
            self.assertIsNotNone(path_violation(rel), rel)


class RunProposeTest(unittest.TestCase):
    def _run(self, proposal, host=None, secrets=()):
        logger, buf = _logger(secrets)
        host = FakeGitHost() if host is None else host
        res = run_propose(proposal, host, logger, trigger="chat", now=NOW)
        return res, host, _events(buf)

    def test_happy_path_branch_files_title_body(self):
        p, _ = parse_proposal(BLOCK)
        res, host, ev = self._run(p)
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.url, "https://github.com/x/y/pull/1")
        (pr,) = host.proposals
        self.assertEqual(pr["branch"], "gaffer/chips-analyst")
        self.assertEqual(sorted(pr["files"]), ["agent/roles/chips-analyst.evidence.md",
                                               "agent/roles/chips-analyst.md"])
        self.assertEqual(pr["files"]["agent/roles/chips-analyst.md"], ROLE_MD)
        note = pr["files"]["agent/roles/chips-analyst.evidence.md"]
        self.assertIn("cap_hit", note)
        self.assertIn("trigger: chat", note)
        self.assertEqual(pr["title"], "Propose role: Chips analyst (gaffer)")
        self.assertIn("cap_hit", pr["body"])
        self.assertIn("agent/roles/chips-analyst.md", pr["body"])
        self.assertIn("https://github.com/x/y/pull/1", res.summary())
        self.assertEqual([e["event"] for e in ev], ["propose_start", "propose_opened"])

    def test_path_outside_roles_dir_is_refused_logged_and_never_reaches_the_runner(self):
        for path in ("daemon/evil.py", "agent/GAFFER.md", "agent/roles/../../.env"):
            p = Proposal("sneaky", "ev", "body", path=path)
            res, host, ev = self._run(p)
            self.assertEqual(res.status, "refused", path)
            self.assertEqual(host.proposals, [])
            self.assertEqual(ev[0]["event"], "propose_refused")
            self.assertEqual(ev[0]["path"], path)
            self.assertIn(path, res.summary())

    def test_empty_name_or_body_is_refused(self):
        self.assertEqual(self._run(Proposal("!!!", "e", "body"))[0].status, "refused")
        self.assertEqual(self._run(Proposal("ok", "e", "  "))[0].status, "refused")

    def test_existing_branch_is_write_once_refused(self):
        p, _ = parse_proposal(BLOCK)
        res, host, ev = self._run(p, host=FakeGitHost(existing={"gaffer/chips-analyst"}))
        self.assertEqual(res.status, "refused")
        self.assertIn("already exists", res.reason)
        self.assertEqual(host.proposals, [])

    def test_runner_failure_degrades_to_a_failed_result(self):
        p, _ = parse_proposal(BLOCK)
        res, _, ev = self._run(p, host=FakeGitHost(fail="push rejected"))
        self.assertEqual(res.status, "failed")
        self.assertIn("push rejected", res.reason)
        self.assertEqual(ev[-1]["event"], "propose_failed")

    def test_no_host_means_failed_not_crash(self):
        p, _ = parse_proposal(BLOCK)
        logger, buf = _logger()
        res = run_propose(p, None, logger, now=NOW)
        self.assertEqual(res.status, "failed")
        self.assertIn("token", res.reason)


class GhGitHostTest(unittest.TestCase):
    """The real runner over a fake subprocess: what argv/env/cwd would run."""

    TOKEN = "ghp_SECRET123"

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="repo-")
        self.calls = []
        self.fail_on = None
        self.ls_remote = ""

        def run(argv, env, cwd):
            self.calls.append((argv, env, cwd))
            if self.fail_on and argv[:2] == self.fail_on:
                return 1, "", "remote: permission denied"
            if argv[:2] == ["git", "ls-remote"]:
                return 0, self.ls_remote, ""
            if argv[:2] == ["gh", "pr"]:
                return 0, "https://github.com/ropats16/fpl-pi-manager/pull/99\n", ""
            return 0, "", ""

        self.host = GhGitHost(self.repo, self.TOKEN, repo="ropats16/fpl-pi-manager",
                              run=run)
        self.files = {"agent/roles/chips.md": "# Chips\n",
                      "agent/roles/chips.evidence.md": "# ev\n"}

    def _argv(self):
        return [a for a, _, _ in self.calls]

    def test_branch_exists_asks_the_remote(self):
        self.assertFalse(self.host.branch_exists("gaffer/x"))
        self.ls_remote = "abc\trefs/heads/gaffer/x\n"
        self.assertTrue(self.host.branch_exists("gaffer/x"))
        argv, env, cwd = self.calls[0]
        self.assertEqual(argv, ["git", "ls-remote", "--heads", "origin", "refs/heads/gaffer/x"])
        self.assertEqual(cwd, self.repo)

    def test_open_pr_sequence_and_token_only_in_env(self):
        url = self.host.open_pr("gaffer/chips", self.files, "Propose role: chips", "body")
        self.assertEqual(url, "https://github.com/ropats16/fpl-pi-manager/pull/99")
        heads = [a[:3] for a in self._argv()]
        self.assertEqual(heads[0], ["git", "fetch", "--quiet"])
        self.assertEqual(heads[1], ["git", "worktree", "add"])
        self.assertEqual(heads[2], ["git", "add", "--"])
        self.assertEqual(heads[3][:2], ["git", "-c"])                       # commit
        self.assertEqual(heads[5][:2], ["gh", "pr"])
        self.assertEqual(heads[6], ["git", "worktree", "remove"])
        push = self._argv()[4]
        self.assertEqual(push[-2:], ["https://github.com/ropats16/fpl-pi-manager.git",
                                     "HEAD:refs/heads/gaffer/chips"])
        self.assertIn("push", push)
        gh = self._argv()[5]
        self.assertIn("--head", gh)
        self.assertEqual(gh[gh.index("--head") + 1], "gaffer/chips")
        self.assertEqual(gh[gh.index("--base") + 1], "main")
        for argv, env, _ in self.calls:
            self.assertNotIn(self.TOKEN, " ".join(argv))
            self.assertEqual(env["GH_TOKEN"], self.TOKEN)
            self.assertEqual(env["GAFFER_GITHUB_TOKEN"], self.TOKEN)
        # The change set was written into the worktree (cwd of add/commit), not the repo.
        wt = self.calls[2][2]
        self.assertNotEqual(wt, self.repo)
        self.assertFalse(os.path.exists(os.path.join(self.repo, "agent")))

    def test_push_failure_raises_and_still_removes_the_worktree(self):
        self.fail_on = ["git", "-c"]                     # first -c call is the commit
        with self.assertRaises(GitHostError) as cm:
            self.host.open_pr("gaffer/chips", self.files, "t", "b")
        self.assertIn("permission denied", str(cm.exception))
        self.assertNotIn(self.TOKEN, str(cm.exception))
        self.assertEqual(self._argv()[-1][:3], ["git", "worktree", "remove"])
        self.assertFalse(any(a[:2] == ["gh", "pr"] for a in self._argv()))


if __name__ == "__main__":
    unittest.main()
