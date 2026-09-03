"""The helper's two tools (#54): `fetch(url)` behind the domain allowlist and
`search(query)` behind one swappable provider. Asserted at the transport's
request log — what left the box, never loop internals."""

import io
import json
import unittest

from daemon.llm import LLM
from daemon.logging_setup import StructuredLogger
from daemon.tools import ODDS_HOST, ExaSearch, Fetcher, html_to_text
from tests.fakes import FakeTransport

ALLOW = {"fantasy.premierleague.com", "api.the-odds-api.com", "understat.com"}
FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def _fetcher(transport, **kw):
    logbuf = io.StringIO()
    kw.setdefault("logger", StructuredLogger(stream=logbuf, secrets=[kw.get("odds_api_key")]))
    return Fetcher(transport, ALLOW, **kw), logbuf


class FetchAllowlistTest(unittest.TestCase):
    def test_allowlisted_get_returns_body_text(self):
        t = FakeTransport(pages={FPL: '{"events": []}'})
        f, _ = _fetcher(t)
        self.assertEqual(f.fetch(FPL), '{"events": []}')
        self.assertEqual(t.requests, [("GET", FPL)])

    def test_subdomain_of_allowlisted_domain_is_allowed(self):
        url = "https://www.understat.com/league/EPL"
        t = FakeTransport(pages={url: "<p>xG</p>"})
        f, _ = _fetcher(t)
        self.assertEqual(f.fetch(url), "xG")

    def test_off_allowlist_never_issues_a_request_and_names_the_propose_path(self):
        t = FakeTransport()
        f, logbuf = _fetcher(t)
        out = f.fetch("https://evil.example/news")
        self.assertEqual(t.requests, [])
        self.assertTrue(out.startswith("fetch refused"))
        self.assertIn("evil.example", out)
        self.assertIn("wanted source:", out)
        ev = [json.loads(l) for l in logbuf.getvalue().splitlines()]
        self.assertEqual(ev[0]["event"], "fetch_refused")

    def test_lookalike_domain_is_refused(self):
        t = FakeTransport()
        f, _ = _fetcher(t)
        for url in ("https://fantasy.premierleague.com.evil.example/x",
                    "https://notunderstat.com/x", "ftp://understat.com/x",
                    "not a url"):
            self.assertTrue(f.fetch(url).startswith("fetch refused"), url)
        self.assertEqual(t.requests, [])

    def test_same_url_twice_costs_one_request(self):
        t = FakeTransport(pages={FPL: "body"})
        f, logbuf = _fetcher(t)
        self.assertEqual(f.fetch(FPL), "body")
        self.assertEqual(f.fetch(FPL), "body")
        self.assertEqual(len(t.requests), 1)
        self.assertEqual((f.calls, f.requests_made), (2, 1))
        ev = [json.loads(l) for l in logbuf.getvalue().splitlines()]
        self.assertEqual([e["cached"] for e in ev if e["event"] == "fetch"], [False, True])

    def test_http_error_and_transport_error_return_error_text(self):
        class Boom:
            def request(self, *a):
                raise OSError("connection reset")
        f, _ = _fetcher(Boom())
        self.assertIn("fetch failed", f.fetch(FPL))
        t = FakeTransport()
        t.pages[FPL] = None    # unknown page -> the fake raises -> error text
        f, _ = _fetcher(t)
        self.assertIn("fetch failed", f.fetch(FPL))


class FetchBodyTest(unittest.TestCase):
    def test_html_is_reduced_to_text(self):
        html = ("<html><head><title>T</title><style>p{}</style><script>x()</script>"
                "</head><body><h1>News</h1><p>Isak &amp; Gordon <b>fit</b>.</p>"
                "<div>Next</div></body></html>")
        text = html_to_text(html)
        self.assertNotIn("x()", text)
        self.assertNotIn("p{}", text)
        self.assertIn("News", text)
        self.assertIn("Isak & Gordon fit.", text)
        self.assertLess(text.index("News"), text.index("Next"))

    def test_body_is_truncated_to_the_token_budget(self):
        t = FakeTransport(pages={FPL: "x" * 100_000})
        f, _ = _fetcher(t, max_tokens=1000)
        out = f.fetch(FPL)
        self.assertLess(len(out), 4_000)
        self.assertIn("truncated", out)


class OddsKeyTest(unittest.TestCase):
    ODDS = f"https://{ODDS_HOST}/v4/sports/soccer_epl/odds/?regions=uk&markets=h2h"

    def test_key_rides_on_the_request_but_never_in_the_result_or_log(self):
        t = FakeTransport(pages={self.ODDS.split("?")[0]: '[{"h2h": 1}]'})
        f, logbuf = _fetcher(t, odds_api_key="SECRET-ODDS")
        out = f.fetch(self.ODDS)
        (_, url), = t.requests
        self.assertIn("apiKey=SECRET-ODDS", url)
        self.assertIn("regions=uk", url)
        self.assertNotIn("SECRET-ODDS", out)
        self.assertNotIn("SECRET-ODDS", logbuf.getvalue())
        self.assertIn(self.ODDS, logbuf.getvalue())   # the logged url is the key-free one

    def test_key_is_not_appended_for_other_hosts(self):
        t = FakeTransport(pages={FPL: "b"})
        f, _ = _fetcher(t, odds_api_key="SECRET-ODDS")
        f.fetch(FPL)
        self.assertNotIn("SECRET-ODDS", t.requests[0][1])

    def test_missing_key_degrades_to_error_text_without_a_request(self):
        t = FakeTransport()
        f, _ = _fetcher(t, odds_api_key=None)
        self.assertIn("fetch failed", f.fetch(self.ODDS))
        self.assertEqual(t.requests, [])

    def test_transport_error_text_is_scrubbed_of_the_key(self):
        class Boom:
            def request(self, method, url, headers=None, body=None):
                raise OSError(f"failed {url}")
        f, _ = _fetcher(Boom(), odds_api_key="SECRET-ODDS")
        self.assertNotIn("SECRET-ODDS", f.fetch(self.ODDS))


class ExaSearchTest(unittest.TestCase):
    def _search(self, reply):
        t = FakeTransport(search_reply=reply)
        logbuf = io.StringIO()
        logger = StructuredLogger(stream=logbuf)
        llm = LLM(api_key="K", transport=t, logger=logger,
                  prices={"z-ai/glm-5.3-flash": {"prompt": 0.075, "completion": 0.25}})
        s = ExaSearch(llm, model="z-ai/glm-5.3-flash", logger=logger, cost_usd=0.007)
        return s, t, llm, logbuf

    def test_one_dedicated_plugin_sub_call_on_the_cheap_model(self):
        s, t, llm, logbuf = self._search("1. Isak fit — bbc.co.uk")
        out = s.search("isak fit newcastle", role="availability")
        self.assertIn("Isak fit", out)
        req = t.search_requests[0]
        self.assertEqual(req["model"], "z-ai/glm-5.3-flash")
        self.assertEqual(req["plugins"], [{"id": "web", "engine": "exa", "max_results": 10}])
        self.assertIn("isak fit newcastle", req["messages"][-1]["content"])
        self.assertEqual(t.llm_requests, [])           # not on the helper's queue
        ev = [json.loads(l) for l in logbuf.getvalue().splitlines()]
        search = [e for e in ev if e["event"] == "search"][0]
        self.assertEqual(search["role"], "availability")
        self.assertAlmostEqual(search["cost_usd"], 0.007)
        self.assertEqual(s.calls, 1)
        # The plugin fee is billed on top of the sub-call's tokens.
        self.assertGreater(llm.cost_usd, 0.007)

    def test_citations_are_appended_as_sources(self):
        s, t, llm, _ = self._search({
            "content": "Isak trained fully.",
            "annotations": [{"type": "url_citation", "url_citation": {
                "url": "https://bbc.co.uk/sport/1", "title": "Isak back"}}]})
        out = s.search("isak")
        self.assertIn("Isak trained fully.", out)
        self.assertIn("https://bbc.co.uk/sport/1", out)

    def test_provider_failure_returns_error_text(self):
        class Boom:
            def request(self, *a):
                raise OSError("down")
        llm = LLM(api_key="K", transport=Boom())
        s = ExaSearch(llm, model="m")
        self.assertIn("search failed", s.search("q"))


if __name__ == "__main__":
    unittest.main()
