"""Helper report writer (#54): one file per role per GW, write-once, capped at
write time, source-stamped header, and a path ACL that refuses anything
outside the current gameweek's report folder."""

import io
import json
import os
import tempfile
import unittest

from daemon.logging_setup import StructuredLogger
from daemon.prompt import estimate_tokens
from daemon.reports import (ReportRefused, ReportWriter, latest_scout_entry,
                            read_reports, read_scout_log, urgent_line)

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


HEADER = {"model": "z-ai/glm-5.3-flash", "started": "2026-09-03T18:00:00Z",
          "finished": "2026-09-03T18:04:10Z", "fetches": 3, "requests": 2,
          "searches": 1, "coverage": "complete", "status": "ok"}


class ReportWriterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="reports-")
        self.logbuf = io.StringIO()
        self.w = ReportWriter(self.tmp, gw=4, logger=StructuredLogger(stream=self.logbuf),
                              cap_tokens=700)

    def _events(self):
        return [json.loads(l) for l in self.logbuf.getvalue().splitlines()]

    def test_writes_headed_report_inside_the_gw_folder(self):
        path = self.w.write("availability", "Isak: fit (NUFC presser 2 Sep).", HEADER)
        self.assertEqual(path, os.path.join(self.tmp, "gw04", "availability.md"))
        text = _read(path)
        self.assertTrue(text.startswith("---\nrole: availability\n"))
        for line in ("model: z-ai/glm-5.3-flash", "started: 2026-09-03T18:00:00Z",
                     "finished: 2026-09-03T18:04:10Z", "fetches: 3 (2 requests)",
                     "searches: 1", "coverage: complete", "status: ok"):
            self.assertIn(line, text)
        self.assertTrue(text.rstrip().endswith("Isak: fit (NUFC presser 2 Sep)."))

    def test_second_write_is_refused_and_logged(self):
        self.w.write("availability", "first", HEADER)
        with self.assertRaises(ReportRefused):
            self.w.write("availability", "second", HEADER)
        self.assertIn("first", _read(self.w.path_for("availability")))
        ev = [e for e in self._events() if e["event"] == "report_refused"]
        self.assertEqual(ev[0]["reason"], "exists")
        self.assertTrue(self.w.exists("availability"))

    def test_body_is_capped_at_write_time(self):
        path = self.w.write("availability", "word " * 5000, HEADER)
        body = _read(path).split("---\n", 2)[2]
        self.assertLessEqual(estimate_tokens(body), 760)   # cap + the marker line
        self.assertIn("[truncated at write time", body)
        self.assertEqual(self._events()[0]["event"], "report_capped")

    def test_write_outside_the_gw_folder_is_refused(self):
        for bad in (os.path.join(self.tmp, "gw05", "x.md"),
                    os.path.join(self.tmp, "gw04", "..", "gw03", "x.md"),
                    "/tmp/x.md", os.path.join(self.tmp, "x.md")):
            with self.assertRaises(ReportRefused, msg=bad):
                self.w.write_path(bad, "x")
            self.assertFalse(os.path.exists(bad))
        ev = [e for e in self._events() if e["event"] == "report_refused"]
        self.assertEqual(len(ev), 4)
        self.assertEqual(ev[0]["reason"], "outside_gw_folder")

    def test_role_name_cannot_escape_via_path_tricks(self):
        with self.assertRaises(ReportRefused):
            self.w.write("../gw03/evil", "x", HEADER)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "gw03")))

    def test_stub_names_the_failure_and_no_coverage(self):
        path = self.w.stub("availability", "helper failed: TimeoutError: llm timeout",
                           HEADER)
        text = _read(path)
        self.assertIn("status: failed", text)
        self.assertIn("coverage: none", text)
        self.assertIn("helper failed: TimeoutError: llm timeout, coverage: none", text)

    def test_read_reports_returns_bodies_for_the_gw_only(self):
        self.w.write("availability", "AVAIL BODY", HEADER)
        other = ReportWriter(self.tmp, gw=3)
        other.write("market", "OLD", HEADER)
        for stray in ("decision-log.md", "scout-log.md", "draft.md"):
            with open(os.path.join(self.tmp, "gw04", stray), "w") as f:
                f.write("not a helper report")
        got = read_reports(self.tmp, 4)
        self.assertEqual(list(got), ["availability"])
        self.assertIn("AVAIL BODY", got["availability"])
        self.assertNotIn("role: availability", got["availability"])   # header stripped


SCOUT_HEADER = {"model": "z-ai/glm-5.3-flash", "started": "2026-09-03T10:00:00Z",
                "finished": "2026-09-03T10:03:00Z", "fetches": 2, "searches": 1,
                "coverage": "checked FPL flags", "status": "ok"}


class ScoutLogTest(unittest.TestCase):
    """The Scout's append-only log (#57 seam): scout-log.md, newest entry on top,
    never write-once. Every other role stays write-once (asserted elsewhere)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scoutlog-")
        self.logbuf = io.StringIO()
        self.w = ReportWriter(self.tmp, gw=4, logger=StructuredLogger(stream=self.logbuf),
                              cap_tokens=250)

    def _events(self):
        return [json.loads(l) for l in self.logbuf.getvalue().splitlines()]

    def test_path_is_scout_log_and_exists_is_always_false(self):
        self.assertEqual(self.w.path_for("scout"),
                         os.path.join(self.tmp, "gw04", "scout-log.md"))
        self.w.write("scout", "entry one", SCOUT_HEADER)
        self.assertFalse(self.w.exists("scout"))   # a log is never "already written"

    def test_two_writes_append_newest_first_under_one_header(self):
        self.w.write("scout", "OLDEST body", dict(SCOUT_HEADER, finished="2026-09-03T10:03:00Z"))
        self.w.write("scout", "NEWEST body", dict(SCOUT_HEADER, finished="2026-09-04T10:03:00Z"))
        text = _read(self.w.path_for("scout"))
        self.assertEqual(text.count("# Scout log — GW04"), 1)
        self.assertTrue(text.lstrip().startswith("# Scout log — GW04"))
        self.assertIn("OLDEST body", text)
        self.assertIn("NEWEST body", text)
        self.assertLess(text.index("NEWEST body"), text.index("OLDEST body"))
        self.assertLess(text.index("2026-09-04T10:03:00Z"), text.index("2026-09-03T10:03:00Z"))
        self.assertIn("scout (z-ai/glm-5.3-flash; fetches 2; searches 1; status ok", text)

    def test_write_logs_report_appended_not_report_written(self):
        self.w.write("scout", "x", SCOUT_HEADER)
        events = self._events()
        self.assertTrue(any(e["event"] == "report_appended" for e in events))
        self.assertFalse(any(e["event"] == "report_written" for e in events))

    def test_stub_appends_a_failed_entry(self):
        self.w.stub("scout", "helper failed: TimeoutError: llm timeout", SCOUT_HEADER)
        text = _read(self.w.path_for("scout"))
        self.assertIn("status failed", text)
        self.assertIn("coverage none", text)
        self.assertIn("helper failed: TimeoutError: llm timeout, coverage: none", text)

    def test_entry_body_is_capped_per_entry(self):
        self.w.write("scout", "word " * 5000, SCOUT_HEADER)
        text = _read(self.w.path_for("scout"))
        self.assertIn("[truncated at write time", text)

    def test_scout_write_outside_the_gw_folder_is_refused(self):
        self.w.path_for = lambda role: os.path.join(self.tmp, "gw05", "scout-log.md")
        with self.assertRaises(ReportRefused):
            self.w.write("scout", "x", SCOUT_HEADER)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "gw05")))

    def test_other_roles_stay_write_once_alongside_the_scout_log(self):
        self.w.write("availability", "AVAIL", SCOUT_HEADER)
        with self.assertRaises(ReportRefused):
            self.w.write("availability", "AVAIL2", SCOUT_HEADER)

    def test_read_scout_log_returns_content_or_empty(self):
        self.assertEqual(read_scout_log(self.tmp, 4), "")
        self.w.write("scout", "SCOUT ENTRY", SCOUT_HEADER)
        got = read_scout_log(self.tmp, 4)
        self.assertIn("SCOUT ENTRY", got)
        self.assertIn("# Scout log — GW04", got)

    def test_latest_scout_entry_is_the_top_entry_only(self):
        self.assertEqual(latest_scout_entry(self.tmp, 4), "")
        self.w.write("scout", "OLD: URGENT Saka out", SCOUT_HEADER)
        self.w.write("scout", "NEW: all quiet", dict(SCOUT_HEADER, finished="2026-09-04T10:03:00Z"))
        latest = latest_scout_entry(self.tmp, 4)
        self.assertTrue(latest.startswith("### 2026-09-04T10:03:00Z — scout"))
        self.assertIn("NEW: all quiet", latest)
        self.assertNotIn("OLD", latest)

    def test_urgent_line_is_the_first_urgent_line_of_an_entry_or_none(self):
        self.assertIsNone(urgent_line("### ts — scout (…)\n\nall quiet\n"))
        entry = ("### ts — scout (…)\n\n**URGENT** — Saka out 3 weeks (presser, 4 Sep).\n"
                 "URGENT: also Rice doubtful.\n")
        self.assertEqual(urgent_line(entry), "URGENT — Saka out 3 weeks (presser, 4 Sep).")
        self.assertIsNone(urgent_line(""))


if __name__ == "__main__":
    unittest.main()
