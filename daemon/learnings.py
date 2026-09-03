"""The learnings loop (#20) — an append-only, model-written diary of what past
analyses actually taught us, and the bounded, vetted path back into a prompt.

The gaffer ends an ad-hoc analysis with a fenced ```learnings JSON block; the
daemon strips it before Telegram (same posture as the ```plan block in #18),
vets every item in *code*, and appends one line per accepted item to
`agent/memory/learnings.md`. A later question pulls a handful of relevant lines
back into the system prompt as evidence to weigh — never as instructions.

Everything here is tier 3 under plans/security-hardening.md §4: the file is
written by the model, so it may only ever carry distilled words plus provenance.
That is why `vet` is paranoid rather than helpful — it collapses newlines (an
entry can never inject a heading or a standing order into the prompt), strips
control characters, refuses URLs (provenance is a citation, not something the
daemon might later be tempted to fetch), bounds every field, and caps how many
entries one reply may ever add. A rejected item is dropped and logged, never
"fixed up" into something that passes.

The read path is deliberately dumb and tolerant, like `parse_shortlist` in #17:
a strict regex over `- [` lines, everything else ignored, and a missing or
unreadable file degrades to no entries rather than crashing a wake. The write
path is `open(path, "a")` and nothing else — the log is a record, so the daemon
is not allowed the ability to rewrite it.
"""

import json
import os
import re
from datetime import datetime, timezone

KINDS = ("specific", "general")
MAX_PER_REPLY = 4          # accepted per reply; extras rejected reason "over_cap"
MAX_LESSON_CHARS = 280
MAX_EVIDENCE_CHARS = 200
MAX_QUESTION_CHARS = 80
SELECT_MAX_ENTRIES = 6
SELECT_MAX_CHARS = 1500

# The fenced block the analysis playbook tells the gaffer to end with. Named
# `learnings` so it never collides with the #18 ```plan block — a reply may
# carry both and each module strips only its own.
_LEARNINGS_BLOCK = re.compile(r"```learnings\b[ \t]*\r?\n(.*?)```", re.DOTALL)

# One entry per line. The " — " runs are structural separators, which is why
# `vet` neutralises them inside the fields (below).
_ENTRY = re.compile(
    r"^- \[(\d{4}-\d{2}-\d{2})\] \[GW(\d{2}|\?\?)\] \[(specific|general)\] "
    r"(.+?) — evidence: (.+?) — q: (.*)$")

# Anything that looks like a link. No verbatim fetched content ever lands in the
# diary, so a citation may name a source but never address one.
_URL = re.compile(r"(https?://|www\.)", re.IGNORECASE)

# Control characters (C0 + DEL) are deleted outright rather than collapsed: a
# lone \x07 between two words must not silently become a word separator.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_WORD = re.compile(r"[a-z0-9]+")

# Small and hand-picked: the point is to stop "what/should/about" from scoring
# every entry against every question, not to do real IR.
_STOPWORDS = frozenset((
    "the", "and", "for", "with", "from", "that", "this", "should", "would",
    "what", "about", "have", "does", "into", "than", "them", "they", "then",
    "there", "their"))


def parse_learnings(reply_text):
    """(items, text_without_block) when the reply carries a ```learnings block;
    (None, reply_text) otherwise.

    `items` are RAW and unvetted — `vet` is the gate — and come out in emission
    order: everything under "specific", then everything under "general".

    Malformed JSON or a non-dict payload is treated as "no usable block": the
    *original* text comes back untouched, so the human still sees the answer and
    nothing half-parsed reaches the log (same rule as `parse_plan`, #18)."""
    text = reply_text or ""
    m = _LEARNINGS_BLOCK.search(text)
    if not m:
        return None, reply_text
    try:
        raw = json.loads(m.group(1))
    except (ValueError, TypeError):
        return None, reply_text
    if not isinstance(raw, dict):
        return None, reply_text
    items = []
    for kind in KINDS:
        elements = raw.get(kind)
        if not isinstance(elements, list):
            continue                 # {"specific": 5} is garbage, not a crash
        for el in elements:
            # A non-dict element still becomes an item so it is *rejected* with
            # a reason rather than vanishing silently.
            el = el if isinstance(el, dict) else {}
            items.append({"kind": kind, "lesson": el.get("lesson"),
                          "evidence": el.get("evidence")})
    return items, _strip_block(text, m)


def _strip_block(text, m):
    """Rejoin the prose around the cut. The block is normally last, but a reply
    that keeps talking afterwards must not reach Telegram with the fence's blank
    lines left behind as a gap."""
    head, tail = text[:m.start()].rstrip(), text[m.end():].lstrip()
    return "\n\n".join(p for p in (head, tail) if p)


def _sanitize(value):
    """Model text -> one bounded, single-line, separator-safe string. Control
    chars deleted, ALL whitespace (newlines included) collapsed to single
    spaces, and the structural " — " neutralised to " - "."""
    if not isinstance(value, str):
        return ""
    s = _CONTROL.sub("", value)
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace(" — ", " - ")


def vet(items):
    """(accepted, rejected) — the memory-write gate (security-hardening.md §4).

    accepted items are sanitized *copies*; rejected is [(original item, reason)]
    with reason ∈ bad_kind / empty_lesson / no_evidence / link / too_long /
    duplicate / over_cap. Rules are checked in that order, one reason per item,
    so the journal names the first thing that was wrong with it."""
    accepted, rejected, seen = [], [], set()
    for item in items or []:
        kind = item.get("kind") if isinstance(item, dict) else None
        if kind not in KINDS:
            rejected.append((item, "bad_kind"))
            continue
        lesson = _sanitize(item.get("lesson"))
        evidence = _sanitize(item.get("evidence"))
        if not lesson:
            rejected.append((item, "empty_lesson"))
        elif not evidence:
            # Provenance is mandatory: an unsourced "lesson" is just an
            # assertion the model would later read back as fact.
            rejected.append((item, "no_evidence"))
        elif _URL.search(lesson) or _URL.search(evidence):
            rejected.append((item, "link"))
        elif len(lesson) > MAX_LESSON_CHARS or len(evidence) > MAX_EVIDENCE_CHARS:
            rejected.append((item, "too_long"))
        elif lesson.casefold() in seen:
            rejected.append((item, "duplicate"))
        elif len(accepted) >= MAX_PER_REPLY:
            # One reply may not flood the diary; the earliest items win.
            rejected.append((item, "over_cap"))
        else:
            seen.add(lesson.casefold())
            accepted.append({"kind": kind, "lesson": lesson,
                             "evidence": evidence})
    return accepted, rejected


def _words(text):
    return {w for w in _WORD.findall((text or "").casefold())
            if len(w) >= 3 and w not in _STOPWORDS}


class LearningsLog:
    """`agent/memory/learnings.md` — append-only tier-3 diary.

    `state_path` (optional) is read at append time for `current_gw`, so an entry
    is stamped with the gameweek it was learned in without the caller having to
    know one. Every read here is tolerant: a missing, corrupt or unreadable file
    yields no entries, never an exception, because a broken diary must degrade
    the prompt, not kill the wake."""

    def __init__(self, path, state_path=None):
        self.path = path
        self.state_path = state_path

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:            # noqa: BLE001 — see class docstring
            return ""

    def entries(self):
        """Parsed entry lines, in file order (oldest first). Header comments,
        blank lines and anything that is not an exact entry line are ignored —
        the file is model-writable, so the parser only ever recognises the one
        shape it wrote itself."""
        out = []
        for line in self._read().splitlines():
            m = _ENTRY.match(line)
            if m:
                out.append({"date": m.group(1), "gw": m.group(2),
                            "kind": m.group(3), "lesson": m.group(4),
                            "evidence": m.group(5), "question": m.group(6)})
        return out

    def _gw_label(self, gw):
        """Explicit arg wins, else season-state current_gw, else unknown."""
        if gw is None and self.state_path:
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    gw = json.load(f).get("current_gw")
            except Exception:        # noqa: BLE001 — a broken state file is not fatal
                gw = None
        try:
            return f"{int(gw):02d}"
        except (TypeError, ValueError):
            return "??"

    def append(self, learnings, question, now=None, gw=None):
        """Append vetted learnings; return (appended entries, skipped).

        skipped is [(learning, "duplicate")] for lessons already in the file —
        an ad-hoc question asked twice should not double the diary. The write is
        `open(path, "a")` and nothing else: the daemon has no code path that can
        rewrite or truncate this file."""
        learnings = list(learnings or [])
        if not learnings:
            return [], []
        stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        label = self._gw_label(gw)
        q = _sanitize(question)[:MAX_QUESTION_CHARS]
        seen = {e["lesson"].casefold() for e in self.entries()}

        appended, skipped, lines = [], [], []
        for item in learnings:
            lesson = _sanitize(item.get("lesson"))
            if lesson.casefold() in seen:
                skipped.append((item, "duplicate"))
                continue
            seen.add(lesson.casefold())
            entry = {"date": stamp, "gw": label, "kind": item.get("kind"),
                     "lesson": lesson,
                     "evidence": _sanitize(item.get("evidence")),
                     "question": q}
            appended.append(entry)
            lines.append(f"- [{entry['date']}] [GW{entry['gw']}] "
                         f"[{entry['kind']}] {entry['lesson']} — evidence: "
                         f"{entry['evidence']} — q: {entry['question']}")
        if not lines:
            return [], skipped

        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # A hand-edited file may not end in a newline; the appended entry must
        # start its own line rather than glue itself onto the last one.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(("\n" if self._needs_newline() else "")
                    + "\n".join(lines) + "\n")
            f.flush()
            os.fsync(f.fileno())     # SD card + power cut: the line is on disk or not at all
        return appended, skipped

    def _needs_newline(self):
        try:
            if os.path.getsize(self.path) == 0:
                return False
            with open(self.path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                return f.read(1) != b"\n"
        except Exception:            # noqa: BLE001 — no file (or no readable one)
            return False

    def select(self, question, max_entries=SELECT_MAX_ENTRIES,
               max_chars=SELECT_MAX_CHARS):
        """The bounded, deterministic slice of the diary this question earns.

        score = how many of the question's content words the entry mentions;
        `general` entries get +0.5 so a standing rule stays in play even with
        zero literal overlap, while a zero-overlap *specific* (another squad,
        another week) drops out. Ties break newest-first. The result is then
        capped on both entry count and rendered characters — the prompt budget
        is a hard ceiling, so the diary can grow forever without the section
        growing with it."""
        q = _words(question)
        scored = []
        for i, e in enumerate(self.entries()):
            overlap = len(q & _words(
                f"{e['lesson']} {e['evidence']} {e['question']}"))
            score = overlap + (0.5 if e["kind"] == "general" else 0.0)
            if score > 0:
                scored.append((-score, -i, e))
        scored.sort(key=lambda t: (t[0], t[1]))

        chosen = []
        for _, _, e in scored:
            if len(chosen) >= max_entries:
                break
            if len(render_learnings(chosen + [e])) > max_chars:
                break
            chosen.append(e)
        return chosen


def render_learnings(entries):
    """Entries as markdown bullets for the prompt section — distilled prose,
    never json (repo invariant #9/#10). "" for no entries, so the assembler's
    section drops out entirely rather than shipping an empty heading."""
    return "\n".join(
        f"- [GW{e['gw']}, {e['kind']}] {e['lesson']} — evidence: {e['evidence']}"
        for e in entries or [])


def record_learnings(log, reply_text, question, logger, now=None, record=True,
                     gw=None):
    """parse -> vet -> append, returning the text that may go to Telegram.

    `gw` (optional) labels the diary entry; the #21 review passes the GW it
    graded, since season-state's `current_gw` can lag the settled GW. Chat
    replies leave it None and take the state's GW.

    The convenience seam for the reply loop. A reply with no block comes back
    untouched and logs nothing. A block that will not parse is stripped anyway
    and logged as `learnings_rejected` (reason `malformed_block`) — the human
    gets the prose, never a broken machine block, and nothing half-parsed
    reaches the diary. Anything else logs one `learnings_recorded` (with the
    counts) plus one `learnings_rejected` per dropped item, so the journal shows
    exactly what the vetting gate refused and why.

    `record=False` strips without writing (`learnings_ignored`): the loop passes
    it for every question that did NOT route to the analysis playbook, so a
    tier-4 report cannot coach a squad-review reply into writing memory — only
    the one playbook that asks for the block can fill the diary (#20).

    A failing write is logged as `learnings_write_error` and swallowed: the
    diary is a side effect of answering, and it must never be able to mute the
    answer itself."""
    items, stripped = parse_learnings(reply_text)
    if items is None:
        m = _LEARNINGS_BLOCK.search(reply_text or "")
        if not m:
            return reply_text
        logger.event("learnings_rejected", reason="malformed_block", kind=None,
                     lesson=None)
        return _strip_block(reply_text, m)
    if not record:
        logger.event("learnings_ignored", reason="not_analysis", items=len(items))
        return stripped

    accepted, rejected = vet(items)
    for item, reason in rejected:
        lesson = item.get("lesson") if isinstance(item, dict) else item
        logger.event("learnings_rejected", reason=reason,
                     kind=(item.get("kind") if isinstance(item, dict) else None),
                     lesson=str(lesson)[:80])
    try:
        appended, skipped = log.append(accepted, question, now=now, gw=gw)
    except Exception as e:           # noqa: BLE001 — see docstring
        logger.event("learnings_write_error", path=getattr(log, "path", None),
                     error=type(e).__name__, detail=str(e))
        return stripped
    logger.event("learnings_recorded", accepted=len(appended),
                 skipped=len(skipped), rejected=len(rejected))
    return stripped
