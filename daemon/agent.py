"""The shared tool-loop core (spec §1) — one bounded conversation that lets the
model call tools, used by the gaffer's chat (§2) and, sharing these internals,
the helper loop (`helper.run_helper`).

`run_agent` generalises the mechanics `helper.run_helper` pioneered (#54): a
pre-assembled `messages` list (system + user…), then a loop of assistant turns
where each tool call is dispatched at the daemon's boundary and its result fed
back as a `tool` turn. It is a circuit-breaker loop, never a leash:

- `Caps` are three tier-1 ceilings — turns, wall-clock minutes, estimated USD —
  checked BETWEEN turns; a crossed cap ends the loop and the last assistant text
  is the reply (`status` names which cap).
- each `Tool` may carry its own `cap` (max calls per run); a call over that cap
  gets a fixed "cap hit" tool result and is still counted, so the model learns
  the tool is spent without the loop breaking.
- it never raises: a transport/LLM error ends the loop with `status="error"` and
  the last assistant text (or a fixed line) as the reply, so a bad turn degrades
  the wake and never crashes it.

Note (spec §1 escape hatch): the helper's per-tool-type ceilings, its cap→write-up
re-prompt and its coverage-line semantics differ from this loop's, so `run_helper`
keeps its own public contract and shares these internals (the `Tool` abstraction
and the tool-dispatch mechanics) rather than being expressed as a `run_agent` call.
"""

from datetime import datetime, timezone

# The reply when the loop stopped (cap or error) before any visible assistant
# text arrived — never a blank string, so a caller can string-handle it blind.
_NO_REPLY = "(the assistant reached a limit before it produced a reply)"


class Tool:
    """One callable the model may invoke (spec §1). `parameters` is a JSON-schema
    dict; `fn(**kwargs) -> str` runs at the tool boundary; `cap` (int | None) is
    the max calls per run — a call over it returns a fixed result, counted."""

    __slots__ = ("name", "description", "parameters", "fn", "cap")

    def __init__(self, name, description, parameters, fn, cap=None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn
        self.cap = cap

    def schema(self):
        """The OpenAI-compatible function declaration the LLM client sends."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}

    @classmethod
    def from_schema(cls, schema, fn, cap=None):
        """Build a Tool from an existing function-declaration dict (so a schema
        already tuned for the wire, e.g. the helper's FETCH_TOOL, stays the one
        source of truth for name/description/parameters)."""
        f = schema["function"]
        return cls(f["name"], f.get("description", ""), f.get("parameters", {}),
                   fn, cap=cap)


class Caps:
    """The three per-run ceilings (spec §1): assistant turns, wall-clock minutes,
    estimated USD. Any of them crossed ends the loop (circuit breaker)."""

    __slots__ = ("turns", "minutes", "cost_usd")

    def __init__(self, turns, minutes, cost_usd):
        self.turns = turns
        self.minutes = minutes
        self.cost_usd = cost_usd


class AgentResult:
    """The outcome of one `run_agent` (spec §1). `reply` is the final assistant
    text; `tool_calls` maps tool name -> count; `status` is one of ok,
    cap_hit:turns, cap_hit:minutes, cap_hit:cost, error."""

    __slots__ = ("reply", "turns", "tool_calls", "cost_usd", "started",
                 "finished", "status")

    def __init__(self):
        self.reply = ""
        self.turns = 0
        self.tool_calls = {}
        self.cost_usd = 0.0
        self.started = None
        self.finished = None
        self.status = "ok"


def run_agent(messages, llm, model, tools, caps, logger, role, clock=None,
              stop=None):
    """Run one bounded tool-loop conversation (spec §1). Returns an AgentResult;
    never raises. `messages` is a pre-assembled list (system + user…); the loop
    appends assistant/tool turns to it in place. With no tools it is a single
    plain completion — today's chat path, unchanged behaviour.

    `stop()` (optional) is a hard brake checked BEFORE each LLM call: when it
    returns true the loop ends immediately with status `stopped` and the last
    assistant text as the reply — the engineer's spent fix budget uses it to go
    straight to finish instead of spinning to the turns cap (spec §4)."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    res = AgentResult()
    res.started = clock()
    cost0 = llm.cost_usd

    # No tools: exactly today's one-shot chat (byte-identical to llm.complete),
    # so the toolless gaffer path does not change behaviour (spec §1/§4).
    if not tools:
        try:
            res.reply = llm.complete(messages, role=role)
        except Exception as e:               # noqa: BLE001 — degrade, never crash a wake
            res.status = "error"
            res.reply = _NO_REPLY
            logger.event("agent_error", role=role, error=f"{type(e).__name__}: {e}"[:200])
        res.turns = 1
        res.cost_usd = llm.cost_usd - cost0
        res.finished = clock()
        return res

    schemas = [t.schema() for t in tools]
    table = {t.name: t for t in tools}
    last_content = ""

    while True:
        if stop is not None and stop():
            res.status = "stopped"
            break
        if res.turns >= caps.turns:
            res.status = "cap_hit:turns"
            break
        if (clock() - res.started).total_seconds() >= caps.minutes * 60:
            res.status = "cap_hit:minutes"
            break
        if caps.cost_usd is not None and (llm.cost_usd - cost0) >= caps.cost_usd:
            res.status = "cap_hit:cost"
            break
        try:
            reply = llm.chat(messages, tools=schemas, model=model, role=role)
        except Exception as e:               # noqa: BLE001 — an LLM/transport blip ends the run
            res.status = "error"
            logger.event("agent_error", role=role, turns=res.turns,
                         error=f"{type(e).__name__}: {e}"[:200])
            break
        res.turns += 1
        if reply.content.strip():
            last_content = reply.content
        if not reply.tool_calls:
            res.reply = reply.content
            res.status = "ok"
            break
        messages.append(reply.message)
        for call in reply.tool_calls:
            res.tool_calls[call.name] = res.tool_calls.get(call.name, 0) + 1
            tool = table.get(call.name)
            if tool is None:
                result = (f"unknown tool {call.name!r}: available tools are "
                          f"{', '.join(sorted(table))}.")
            elif tool.cap is not None and res.tool_calls[call.name] > tool.cap:
                result = (f"{call.name} cap hit: this tool may be called at most "
                          f"{tool.cap} time(s) per chat; work with what you have.")
            else:
                try:
                    result = tool.fn(**(call.arguments or {}))
                except Exception as e:       # noqa: BLE001 — a tool error is evidence, not a crash
                    result = f"{call.name} failed: {type(e).__name__}: {e}"[:400]
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": result if isinstance(result, str) else str(result)})

    if not (res.reply or "").strip() and res.status != "ok":
        res.reply = last_content.strip() or _NO_REPLY
    res.cost_usd = llm.cost_usd - cost0
    res.finished = clock()
    return res
