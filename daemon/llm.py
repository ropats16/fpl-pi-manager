"""LLM client — OpenRouter, one OpenAI-compatible chat-completion per call (#8).

Endpoint locked to OpenRouter (one base_url + one key) so per-call model
selection is trivial; the caller names `model=` (Kimi K2.5 default, GPT-5.4
escalation) — no runtime self-upgrade magic. The API key is injected into the
process, never into model context.
"""

import json

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "moonshotai/kimi-k2.5"


class LLM:
    def __init__(self, api_key, model=DEFAULT_MODEL, transport=None,
                 base_url=DEFAULT_BASE_URL, max_tokens=1024):
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens

    def complete(self, messages):
        body = json.dumps({
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
        }).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = self._transport.request(
            "POST", f"{self._base_url}/chat/completions", headers, body)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
