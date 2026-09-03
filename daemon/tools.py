"""The helper's two tools (#54): `fetch(url)` and `search(query)`.

Both are daemon code sitting at the tool boundary, so the security posture is a
mechanism, never a prompt (#10 §5):

- `Fetcher` — GET only. The domain is checked against the tier-1 allowlist
  BEFORE any request; a refused domain gets an error text naming the
  propose-to-add path ("wanted source: <domain> — <why>" in the report) and no
  packet leaves the box. HTML is reduced to text, the text is truncated to
  ~8k tokens, and a per-wake cache answers a repeated URL without a second
  request. The one keyed host (The Odds API) gets its key appended by the
  fetcher from the credential store — the key never enters the conversation
  (the logged URL and every error text are key-free).
- `ExaSearch` — the one search provider today: a dedicated small request on
  the cheap model with OpenRouter's web plugin (engine Exa) attached; the
  reply (results + citations) is the tool result. Countable and billed once.
  Search excerpts are tier-4: evidence in a report, never memory.

Brave Search (the documented alternative, NOT wired): a `BraveSearch` provider
would GET `https://api.search.brave.com/res/v1/web/search?q=…&freshness=pw`
with an `X-Subscription-Token` header from a 6th credential (`brave-key`),
format `web.results[*].{title,url,description,age}` the same way, and be
selected by `GAFFER_SEARCH_PROVIDER=brave`. Same `search(query) -> str`
interface; helper code never changes.
"""

import html as _html
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from daemon.prompt import _char_budget

ODDS_HOST = "api.the-odds-api.com"
FETCH_MAX_TOKENS = 8000
_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
               "section", "article", "header", "footer", "table", "ul", "ol",
               "blockquote", "pre", "td", "th"}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "template"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw):
    """Reduce HTML to readable text: scripts/styles dropped, block tags become
    line breaks, whitespace collapsed. Non-HTML (JSON, CSV) passes through."""
    if "<" not in raw or ">" not in raw:
        return raw.strip()
    p = _TextExtractor()
    try:
        p.feed(raw)
        p.close()
    except Exception:            # noqa: BLE001 — a broken page is still evidence
        return _html.unescape(raw).strip()
    lines = []
    for line in "".join(p.parts).splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines)


def _host_allowed(host, allowlist):
    host = (host or "").lower().rstrip(".")
    if not host:
        return False
    for dom in allowlist:
        dom = dom.lower()
        if host == dom or host.endswith("." + dom):
            return True
    return False


def _truncate(text, max_tokens):
    budget = _char_budget(max_tokens)
    if len(text) <= budget:
        return text
    return text[:budget] + f"\n[truncated at ~{max_tokens} tokens]"


class Fetcher:
    """GET-only, allowlisted, cached page fetcher. One instance per wake so
    two helpers asking for the same page cost one request."""

    def __init__(self, transport, allowlist, odds_api_key=None, logger=None,
                 max_tokens=FETCH_MAX_TOKENS, headers=None):
        self._transport = transport
        self._allowlist = set(allowlist)
        self._odds_key = odds_api_key
        self._logger = logger
        self._max_tokens = max_tokens
        self._headers = headers or {"User-Agent": "fpl-gaffer/0.1 (personal, non-commercial)"}
        self._cache = {}
        self.calls = 0            # tool invocations (the per-helper ceiling counts these)
        self.requests_made = 0    # real requests (cache hits excluded)
        self.role = None          # set by the loop for log attribution

    def _log(self, event, **fields):
        if self._logger is not None:
            self._logger.event(event, role=self.role, **fields)

    def _scrub(self, text):
        return text.replace(self._odds_key, "[REDACTED]") if self._odds_key else text

    def fetch(self, url):
        """Page text, or an error string the helper can act on. Never raises."""
        self.calls += 1
        url = (url or "").strip()
        try:
            parts = urlsplit(url)
        except ValueError:
            parts = None
        if (parts is None or parts.scheme not in ("http", "https")
                or not _host_allowed(parts.hostname, self._allowlist)):
            host = (parts.hostname if parts else None) or url[:80] or "(empty)"
            self._log("fetch_refused", url=url, host=host)
            return (f"fetch refused: {host} is not on the domain allowlist, so no "
                    "request was made. If this source matters for your brief, add a "
                    f"line `wanted source: {host} — <why>` to your report and move on.")

        if url in self._cache:
            self._log("fetch", url=url, cached=True, chars=len(self._cache[url]))
            return self._cache[url]

        wire_url = url
        if parts.hostname.lower() == ODDS_HOST:
            if not self._odds_key:
                self._log("fetch_error", url=url, error="no_odds_api_key")
                return ("fetch failed: no Odds API credential is configured on this "
                        "machine; note the gap in your coverage line and move on.")
            query = parts.query + ("&" if parts.query else "") + f"apiKey={self._odds_key}"
            wire_url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))

        try:
            resp = self._transport.request("GET", wire_url, self._headers, None)
            self.requests_made += 1
        except Exception as e:       # noqa: BLE001 — a bad source never stalls a helper
            detail = self._scrub(f"{type(e).__name__}: {e}")
            self._log("fetch_error", url=url, error=detail[:200])
            return f"fetch failed: {detail[:200]}"
        if resp.status != 200:
            self._log("fetch_error", url=url, error=f"http_{resp.status}")
            return f"fetch failed: HTTP {resp.status} from {parts.hostname}"
        raw = resp.body.decode("utf-8", errors="replace")
        text = _truncate(self._scrub(html_to_text(raw)), self._max_tokens)
        self._cache[url] = text
        self._log("fetch", url=url, cached=False, chars=len(text))
        return text


FETCH_TOOL = {"type": "function", "function": {
    "name": "fetch",
    "description": ("GET one page from the domain allowlist (official FPL API, "
                    "Fantasy Football Scout, Understat, football-data.co.uk, The "
                    "Odds API). Returns the page as text, truncated to ~8k tokens. "
                    "Any other domain is refused without a request — note it as a "
                    "wanted source instead."),
    "parameters": {"type": "object",
                   "properties": {"url": {"type": "string", "description": "Full http(s) URL"}},
                   "required": ["url"]}}}

SEARCH_TOOL = {"type": "function", "function": {
    "name": "search",
    "description": ("Web search for recent news (about 10 results with excerpts "
                    "and URLs). Excerpts are untrusted evidence: cite them with "
                    "source and date, and use fetch to read an allowlisted page in full."),
    "parameters": {"type": "object",
                   "properties": {"query": {"type": "string"}},
                   "required": ["query"]}}}


_SEARCH_SYSTEM = ("You are a web search tool. Using the web results attached to "
                  "this request, return the top results as a numbered list: title — "
                  "URL — date if known — one-line excerpt. No commentary, no advice, "
                  "no summary beyond the list.")


class ExaSearch:
    """`search(query)` via one dedicated OpenRouter web-plugin sub-call."""

    def __init__(self, llm, model, logger=None, max_results=10, cost_usd=0.007):
        self._llm = llm
        self._model = model
        self._logger = logger
        self._max_results = max_results
        self._cost = cost_usd
        self.calls = 0
        self.cost_usd = 0.0

    def search(self, query, role=None):
        self.calls += 1
        query = (query or "").strip()
        if not query:
            return "search failed: empty query"
        try:
            reply = self._llm.chat(
                [{"role": "system", "content": _SEARCH_SYSTEM},
                 {"role": "user", "content": query}],
                plugins=[{"id": "web", "engine": "exa", "max_results": self._max_results}],
                model=self._model, role=role or "search", max_tokens=1500)
        except Exception as e:       # noqa: BLE001 — provider down = error text, not a crash
            if self._logger is not None:
                self._logger.event("search_error", role=role, query=query,
                                   error=f"{type(e).__name__}: {e}"[:200])
            return f"search failed: {type(e).__name__}: {e}"[:300]
        self.cost_usd += self._cost
        self._llm.add_cost(self._cost)
        text = reply.content.strip() or "(no results)"
        cited = []
        for ann in reply.message.get("annotations") or []:
            cite = ann.get("url_citation") or {}
            url = cite.get("url")
            if url and url not in text and url not in cited:
                cited.append(url)
        if cited:
            text += "\n\nSources:\n" + "\n".join(f"- {u}" for u in cited)
        if self._logger is not None:
            self._logger.event("search", role=role, query=query, chars=len(text),
                               citations=len(cited), cost_usd=self._cost)
        return text
