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
from daemon.reports import ReportRefused, ReportWriter, read_reports

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
        with open(os.path.join(self.tmp, "gw04", "decision-log.md"), "w") as f:
            f.write("not a helper report")
        got = read_reports(self.tmp, 4)
        self.assertEqual(list(got), ["availability"])
        self.assertIn("AVAIL BODY", got["availability"])
        self.assertNotIn("role: availability", got["availability"])   # header stripped


if __name__ == "__main__":
    unittest.main()
