"""The act-on-team boundary (#18). Until the real FPL write path is proven
(#13/#14), this is DRY-RUN / MANUAL-APPLY ONLY: it emits the exact steps for
Rohit to tap into the FPL app and records that it was called, but it never
touches the network and never mutates an FPL team.

`ManualApplyActuator` is the seam the real actuator (#19) drops into. The
approval gate above it (daemon/brief.py, daemon/loop.py) is what the harness
asserts: no `apply` call ever happens without an explicit `yes` in daemon code.

Contingency auto-exec (weekly-cycle.md §3⑤) is deliberately deferred: with a
manual-apply actuator there is no autonomous write to make at the deadline, so a
no-approval timeout is a loud no-write, not a silent contingency execution. That
autonomous path lands with the real write actuator (#19).
"""

from daemon.plan import record_decision  # noqa: F401  (re-exported for callers)


class ManualApplyActuator:
    """Produces manual-apply instructions and records every call in `applied`
    so the harness can assert the gate held. No network, no FPL mutation."""

    def __init__(self):
        self.applied = []      # [{gw, plan}] — one entry per apply() call

    def apply(self, plan, gw):
        self.applied.append({"gw": gw, "plan": plan})

        lines = ["Apply in the FPL app before the deadline:"]
        n = 1
        ti = plan.get("transfers_in") or []
        to = plan.get("transfers_out") or []
        if ti or to:
            pairs = [f"OUT {to[i] if i < len(to) else '—'} → IN {ti[i] if i < len(ti) else '—'}"
                     for i in range(max(len(ti), len(to)))]
            hits = plan.get("hits") or 0
            hit_str = f" (−{hits} hit)" if hits else ""
            lines.append(f"{n}. Transfer " + "; ".join(pairs) + hit_str)
        else:
            lines.append(f"{n}. no transfers — confirm XI/(C) unchanged")
        n += 1
        cap = plan.get("captain") or "?"
        vice = plan.get("vice") or "?"
        lines.append(f"{n}. Captain: {cap}, Vice: {vice}")
        n += 1
        xi = plan.get("starting_xi") or []
        lines.append(f"{n}. XI: " + ", ".join(xi))
        n += 1
        if plan.get("chip"):
            lines.append(f"{n}. Chip: {plan['chip']}")
        return "\n".join(lines)
