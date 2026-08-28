"""Deterministic plan + approval primitives — the write gate lives here, in code,
never in model judgment (#18, spec plans/weekly-cycle.md §3).

Nothing in this module touches the network or the LLM. It parses the machine
`plan` block the gaffer appends to a brief, decides whether two plans differ by a
struct diff (never the model's opinion of "materiality"), and persists the
approval state machine to a small json file — the same machine-state posture as
the #17 watch baseline (atomic temp+rename, corrupt/missing degrades to a clean
idle state rather than crashing the daemon).

The approval token is matched on the *whole* trimmed message (§3①): `yes but…`
is debate, not approval. Keeping the matcher exact and in daemon code is what
stops a stray `yes` in scrollback — or an injected model — from ever flipping a
write gate it was not meant to.
"""

import json
import os
import re
from datetime import datetime, timezone

# §3① — approval is the whole message equal to one of these, case-folded.
APPROVE_TOKENS = {"yes", "y", "lock", "approve"}

# The gaffer ends a brief with a fenced ```plan { … } ``` JSON block; the daemon
# freezes it as the approval snapshot and strips it before Telegram (§3②).
_PLAN_BLOCK = re.compile(r"```plan\b[ \t]*\r?\n(.*?)```", re.DOTALL)

# The plan snapshot keys and their defaults (§3② structured snapshot).
_LIST_FIELDS = ("transfers_in", "transfers_out", "starting_xi", "contingencies")
_STR_FIELDS = ("captain", "vice", "chip")


def is_approval(text):
    """True iff the whole trimmed message case-folds to an approval token. An
    exact match, never a substring — `yes but…` / `ok yes` are NOT approval."""
    return (text or "").strip().casefold() in APPROVE_TOKENS


def is_stop(text):
    """True iff the whole trimmed message is `stop` (case-insensitive) — the
    opt-out that holds a locked plan (§3⑤ / final unchanged form)."""
    return (text or "").strip().casefold() == "stop"


def _as_list(v):
    return [str(x) for x in v] if isinstance(v, list) else []


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _as_opt_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _normalize(raw):
    """A parsed json object -> the canonical plan dict, missing keys defaulted
    ([] / 0 / None). A non-dict payload yields an all-default plan so a truthy
    but malformed block never propagates half a plan."""
    raw = raw if isinstance(raw, dict) else {}
    plan = {f: _as_list(raw.get(f)) for f in _LIST_FIELDS}
    plan["hits"] = _as_int(raw.get("hits"))
    for f in _STR_FIELDS:
        plan[f] = _as_opt_str(raw.get(f))
    return plan


def parse_plan(reply_text):
    """(plan dict, text_without_block) when the reply carries a well-formed
    ```plan``` block; (None, reply_text) otherwise.

    The machine block never reaches Telegram, so on success the fenced region is
    stripped and the surrounding prose returned. Malformed JSON inside the fence
    is treated as "no usable plan": return the *original* text untouched so the
    human still sees the brief and nothing half-parsed becomes a snapshot."""
    text = reply_text or ""
    m = _PLAN_BLOCK.search(text)
    if not m:
        return None, reply_text
    try:
        raw = json.loads(m.group(1))
    except (ValueError, TypeError):
        return None, reply_text
    stripped = (text[:m.start()] + text[m.end():]).strip()
    return _normalize(raw), stripped


def _cf_set(v):
    return {str(x).casefold() for x in (v or [])}


def _cf(v):
    return v.casefold() if isinstance(v, str) else v


def plans_differ(a, b):
    """Field-by-field struct diff (§3③). Lists compare order-insensitively as
    sets of case-folded strings; captain/vice/chip case-fold; hits are numeric.
    Any difference in the snapshot fields -> True. A None on exactly one side is
    a difference; two Nones are equal."""
    if a is None or b is None:
        return a is not b
    for f in _LIST_FIELDS:
        if _cf_set(a.get(f)) != _cf_set(b.get(f)):
            return True
    if _as_int(a.get("hits")) != _as_int(b.get("hits")):
        return True
    for f in _STR_FIELDS:
        if _cf(a.get(f)) != _cf(b.get(f)):
            return True
    return False


def transfer_pairs(plan, out_label="OUT ", arrow=" → ", in_label="IN "):
    """The plan's transfers as paired 'out → in' strings, '—' padding the short
    side. One shared shape for the prose section, the summary line, and the
    actuator's manual-apply steps."""
    ti = plan.get("transfers_in") or []
    to = plan.get("transfers_out") or []
    return [f"{out_label}{to[i] if i < len(to) else '—'}{arrow}"
            f"{in_label}{ti[i] if i < len(ti) else '—'}"
            for i in range(max(len(ti), len(to)))]


def plan_prose(plan):
    """Render a plan as human/model-readable markdown lines — NEVER json.dumps
    (repo invariant #9/#10: model context is distilled prose, never raw json).
    Used for the debate-grounding section and the approval receipts."""
    if not plan:
        return "- (no structured plan)"
    lines = []
    pairs = transfer_pairs(plan)
    if pairs:
        lines.append("- Transfers: " + "; ".join(pairs))
    else:
        lines.append("- Transfers: none")
    if plan.get("hits"):
        lines.append(f"- Hit: −{plan['hits']}")
    xi = plan.get("starting_xi") or []
    if xi:
        lines.append("- XI: " + ", ".join(xi))
    if plan.get("captain"):
        lines.append(f"- Captain: {plan['captain']}")
    if plan.get("vice"):
        lines.append(f"- Vice: {plan['vice']}")
    if plan.get("chip"):
        lines.append(f"- Chip: {plan['chip']}")
    cont = plan.get("contingencies") or []
    if cont:
        lines.append("- Contingencies: " + "; ".join(cont))
    return "\n".join(lines)


def plan_summary(plan):
    """A one-line plan summary for the approval/lock receipts."""
    if not plan:
        return "no changes"
    parts = []
    pairs = transfer_pairs(plan, out_label="", arrow="→", in_label="")
    parts.append(", ".join(pairs) if pairs else "no transfers")
    if plan.get("captain"):
        parts.append(f"(C) {plan['captain']}")
    if plan.get("vice"):
        parts.append(f"(VC) {plan['vice']}")
    if plan.get("chip"):
        parts.append(f"chip {plan['chip']}")
    return ", ".join(parts)


_IDLE = {"gw": None, "phase": "idle", "pending_plan": None,
         "approved_plan": None, "draft_sent": False, "final_sent": False}


class ApprovalStore:
    """The AWAITING_APPROVAL state machine, persisted to a small json file so the
    brief wake (a fresh process each systemd tick) and the resident reply loop
    share one source of truth. Machine state, like the watch baseline — it lives
    under the gitignored data/ dir, writes atomically, and a corrupt or missing
    file loads as clean idle rather than crashing the daemon.

    phase ∈ {idle, awaiting_approval, approved, locked, acted, no_write}."""

    def __init__(self, path):
        self.path = path
        self._set(_IDLE)

    def _set(self, d):
        self.gw = d["gw"]
        self.phase = d["phase"]
        self.pending_plan = d["pending_plan"]
        self.approved_plan = d["approved_plan"]
        self.draft_sent = d["draft_sent"]
        self.final_sent = d["final_sent"]

    def _dict(self):
        return {"gw": self.gw, "phase": self.phase,
                "pending_plan": self.pending_plan,
                "approved_plan": self.approved_plan,
                "draft_sent": self.draft_sent, "final_sent": self.final_sent}

    def load(self):
        """Read the file into this instance and return self. Missing or corrupt
        -> clean idle (a broken state file must never crash a wake)."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            merged = dict(_IDLE)
            merged.update({k: d[k] for k in _IDLE if k in d})
            self._set(merged)
        except Exception:            # noqa: BLE001 — corrupt state degrades to idle
            self._set(_IDLE)
        return self

    def save(self):
        _atomic_write_json(self.path, self._dict())
        return self

    def reset_for(self, gw):
        """Clean idle state bound to a new gameweek — a fresh deadline cycle."""
        self._set(_IDLE)
        self.gw = gw
        return self.save()

    def set_pending(self, gw, plan):
        """Freeze the draft plan as the pending snapshot (phase AWAITING).
        `plan` may be None (a brief whose block never parsed) — a later `yes`
        then finds no pending plan and must NOT approve."""
        self.gw = gw
        self.pending_plan = plan
        self.phase = "awaiting_approval"
        return self.save()

    def approve(self):
        """Flip the gate: the pending snapshot becomes approved (phase APPROVED)."""
        self.approved_plan = self.pending_plan
        self.phase = "approved"
        return self.save()

    def void_carry(self, new_plan):
        """Carry-void (§3③/§3⑥): a changed final or an iterate replaces the
        pending snapshot and clears any prior approval, so a stale scrollback
        `yes` cannot fire — a fresh `yes` approves the NEW pending only."""
        self.pending_plan = new_plan
        self.approved_plan = None
        self.phase = "awaiting_approval"
        return self.save()


class ApprovalGate:
    """The handle the reply loop is wired with — holds the store so
    process_message can load fresh state and flip the gate in daemon code, and
    (when set) the reports dir so an iterate's full reply — the gaffer's dissent
    included — lands in the repo decision log (§3④, scored post-GW by #21)."""

    def __init__(self, store, reports_dir=None):
        self.store = store
        self.reports_dir = reports_dir


def _atomic_write_json(path, obj, indent=None):
    """temp+rename in the target dir — never a half-written state file."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent)
    os.replace(tmp, path)


def append_decision_log(reports_dir, gw, title, body, now=None):
    """Append one titled entry to the repo record `reports/gwNN/decision-log.md`
    (weekly-cycle.md §2): drafts, finals, and iterate replies (dissent included)
    all land here — the durable reasoning behind what Telegram carried lean."""
    d = os.path.join(reports_dir, f"gw{gw:02d}")
    os.makedirs(d, exist_ok=True)
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(d, "decision-log.md"), "a", encoding="utf-8") as f:
        f.write(f"\n\n## {title} — {ts}\n\n{body}\n")


def record_decision(state_path, gw, plan, status, now=None):
    """Write the locked/no-write decision back to season-state.json under
    decisions.gw<NN> (§ "acted decisions write back to season state"). Everything
    else in the state file is preserved; the write is atomic. A missing or
    corrupt state file raises — the caller logs it (the squad picks resync via
    the existing pull-squad flow; this never mutates picks)."""
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    decisions = state.setdefault("decisions", {})
    decisions[f"gw{gw:02d}"] = {"plan": plan, "status": status, "recorded_at": ts}
    _atomic_write_json(state_path, state, indent=2)
