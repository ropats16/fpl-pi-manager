"""TEMPORARY read harness (issue #78 authoring aid), phase 3: daemon/brief.py
into chunk files for batch reading (its wake-window logic is needed to drive
run_brief_cmd to its first LLM call in the wiring tests); removes consumed
chunks. A later scratch phase deletes the rest; the shipped tests/test_pipeline.py
is the real harness. Nothing here edits any source."""

import atexit
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BRIEF = os.path.join(ROOT, "daemon", "brief.py")
CHUNKS = [(BRIEF, a, a + 199, "_d%d.txt" % (i + 17))
          for i, a in enumerate(range(1, 599, 200))]
READ = ["_d%d.txt" % n for n in range(9, 17)]


def _dump_all():
    for name in READ:
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            os.remove(path)
    with open(BRIEF, encoding="utf-8") as fh:
        lines = fh.readlines()
    for _src, a, b, name in CHUNKS:
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as out:
            out.write("".join(lines[a - 1:b]))
    sys.__stderr__.write("COUNTS brief.py=%d\n" % len(lines))


class TestTempDump(unittest.TestCase):
    def test_chunk_sources_for_batch_read(self):
        self.assertTrue(os.path.exists(BRIEF))


atexit.register(_dump_all)

if __name__ == "__main__":
    unittest.main()
