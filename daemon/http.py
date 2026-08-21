"""The one network seam. Stdlib-only (Pi-friendly, no pip).

Every outbound request in the daemon goes through a Transport. Production uses
UrllibTransport; tests inject a fake (tests/fakes.py) so the whole wake->reply
loop runs offline. Keeping the HTTP edge injectable is the #7-locked
testability guarantee ("you own the HTTP edges").
"""

import urllib.error
import urllib.request


class Response:
    __slots__ = ("status", "body")

    def __init__(self, status, body):
        self.status = status
        self.body = body  # bytes

    def json(self):
        import json
        return json.loads(self.body.decode("utf-8"))


class UrllibTransport:
    """Real transport over urllib. GET/POST only — no other verbs are used."""

    def __init__(self, timeout=30):
        self.timeout = timeout

    def request(self, method, url, headers=None, body=None):
        req = urllib.request.Request(url, data=body, method=method,
                                     headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return Response(status=resp.status, body=resp.read())
        except urllib.error.HTTPError as e:
            return Response(status=e.code, body=e.read())
