"""LLM client — OpenRouter, one OpenAI-compatible chat-completion per call (#8).

Endpoint locked to OpenRouter (one base_url + one key) so per-call model
selection is trivial; the caller names `model=` (Kimi K2.5 default, the role
map in config for helpers) — no runtime self-upgrade magic. The API key is
injected into the process, never into model context.

#54: the one request shape also carries `tools` (function declarations) and
`plugins` (the web-search sub-call), the reply exposes the tool calls the model
made, and every call logs the `usage` block plus an estimated cost from the
configured price table — the raw material for the per-wake rails and the
month-to-date ledger (#56).
"""

import json
import uuid

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "moonshotai/kimi-k2.5"


def estimate_cost(model, usage, prices):
    """USD for one call from its usage block and a {model: {prompt, completion}}
    price table in USD per 1M tokens. None when the model is not priced — an
    unknown model is logged as unknown, never silently as free."""
    row = (prices or {}).get(model)
    if not row:
        return None
    p = (usage or {}).get("prompt_tokens") or 0
    c = (usage or {}).get("completion_tokens") or 0
    return p * row.get("prompt", 0) / 1e6 + c * row.get("completion", 0) / 1e6


class ToolCall:
    __slots__ = ("id", "name", "arguments")

    def __init__(self, id, name, arguments):
        self.id = id
        self.name = name
        self.arguments = arguments   # dict ({} when the model sent bad JSON)


class Reply:
    """One assistant turn. `message` is the raw assistant message to echo back
    into the conversation before a tool-result turn; `content` is "" (never
    None) so callers can string-handle it blind."""
    __slots__ = ("content", "tool_calls", "usage", "message", "finish_reason", "cost_usd")

    def __init__(self, content, tool_calls, usage, message, finish_reason, cost_usd):
        self.content = content
        self.tool_calls = tool_calls
        self.usage = usage
        self.message = message
        self.finish_reason = finish_reason
        self.cost_usd = cost_usd


def _parse_tool_calls(message):
    out = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        raw = fn.get("arguments")
        if isinstance(raw, dict):
            args = raw
        else:
            try:
                args = json.loads(raw or "{}")
            except (TypeError, ValueError):
                args = {}
            if not isinstance(args, dict):
                args = {}
        out.append(ToolCall(tc.get("id") or "", fn.get("name") or "", args))
    return out


class LLM:
    def __init__(self, api_key, model=DEFAULT_MODEL, transport=None,
                 base_url=DEFAULT_BASE_URL, max_tokens=1024, logger=None,
                 prices=None, wake_id=None):
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._logger = logger
        self._prices = prices or {}
        # One id per process so every llm_call event of a wake shares it.
        self.wake_id = wake_id or uuid.uuid4().hex[:8]
        # Running totals across the process — the wake rails (#56) read these.
        self.calls = 0
        self.tokens = 0
        self.cost_usd = 0.0
        self.unpriced_calls = 0

    @property
    def model(self):
        return self._model

    def chat(self, messages, tools=None, plugins=None, model=None,
             max_tokens=None, role="gaffer", tool_choice=None):
        """One chat completion. Returns a Reply; raises on transport or
        malformed-reply errors (callers choose retry vs stub)."""
        model = model or self._model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        if plugins:
            payload["plugins"] = plugins
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = self._transport.request(
            "POST", f"{self._base_url}/chat/completions", headers, body)
        data = resp.json()
        if "choices" not in data:
            err = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
            raise RuntimeError(f"llm reply without choices (status {resp.status}): "
                               f"{err or 'no error message'}")
        choice = data["choices"][0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        cost = estimate_cost(model, usage, self._prices)
        self._account(model, usage, cost, role, choice.get("finish_reason"))
        return Reply(content=message.get("content") or "",
                     tool_calls=_parse_tool_calls(message), usage=usage,
                     message=message, finish_reason=choice.get("finish_reason"),
                     cost_usd=cost)

    def _account(self, model, usage, cost, role, finish_reason=None):
        p = usage.get("prompt_tokens") or 0
        c = usage.get("completion_tokens") or 0
        self.calls += 1
        self.tokens += p + c
        if cost is None:
            self.unpriced_calls += 1
        else:
            self.cost_usd += cost
        if self._logger is not None:
            # OpenRouter also reports what it actually charged (`usage.cost`);
            # logged beside the table estimate so the #21 review can compare.
            reported = usage.get("cost")
            self._logger.event("llm_call", role=role, wake_id=self.wake_id,
                               model=model, prompt_tokens=p, completion_tokens=c,
                               cost_usd=None if cost is None else round(cost, 6),
                               reported_cost_usd=(reported if isinstance(reported, (int, float))
                                                  else None),
                               # "length" = the output budget ran out (a reasoning
                               # model may then return NO visible text).
                               finish_reason=finish_reason)

    def add_cost(self, usd):
        """Fold a non-token charge (the web-plugin search fee) into the running
        total so the wake rails see the real spend."""
        self.cost_usd += usd

    def complete(self, messages, role="gaffer"):
        """The pre-#54 one-shot: reply text only."""
        return self.chat(messages, role=role).content
