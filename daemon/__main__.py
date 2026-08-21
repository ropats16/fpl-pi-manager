"""Entrypoint. `python3 -m daemon` runs the resident loop; `... selftest` drives
one full message->reply loop offline with every external faked (no network)."""

import io
import json
import sys

from daemon.config import Config, load_config
from daemon.http import Response, UrllibTransport
from daemon.llm import LLM, DEFAULT_BASE_URL
from daemon.logging_setup import StructuredLogger
from daemon.loop import poll_once, run
from daemon.telegram import Telegram


def run_daemon(env=None, out=None):
    out = sys.stderr if out is None else out
    cfg = load_config(env)
    logger = StructuredLogger(stream=out, secrets=cfg.secrets())
    transport = UrllibTransport()
    telegram = Telegram(token=cfg.telegram_token, transport=transport)
    llm = LLM(api_key=cfg.openrouter_key, model=cfg.model, transport=transport,
              base_url=cfg.base_url)
    run(cfg, telegram, llm, logger)
    return 0


class _SelftestTransport:
    """Fake HTTP edge for the offline selftest: one message in, canned reply out."""

    def __init__(self):
        self._served = False

    def request(self, method, url, headers=None, body=None):
        if "/getUpdates" in url:
            if self._served:
                return _json({"ok": True, "result": []})
            self._served = True
            return _json({"ok": True, "result": [{
                "update_id": 1,
                "message": {"message_id": 1, "from": {"id": 42},
                            "chat": {"id": 42, "type": "private"},
                            "text": "selftest: are you alive?"},
            }]})
        if "/sendMessage" in url:
            return _json({"ok": True, "result": {"message_id": 2}})
        if "chat/completions" in url:
            return _json({"choices": [{"message": {
                "content": "Yes — gaffer online."}}]})
        raise AssertionError(f"unexpected url {url}")


def _json(obj):
    return Response(status=200, body=json.dumps(obj).encode("utf-8"))


def run_selftest(out=None):
    out = sys.stdout if out is None else out
    cfg = Config(allowlist={42}, telegram_token="fake-token",
                 openrouter_key="fake-key", model="moonshotai/kimi-k2.5",
                 base_url=DEFAULT_BASE_URL, system_prompt="selftest")
    logbuf = io.StringIO()
    logger = StructuredLogger(stream=logbuf, secrets=cfg.secrets())
    transport = _SelftestTransport()
    telegram = Telegram(token=cfg.telegram_token, transport=transport)
    llm = LLM(api_key=cfg.openrouter_key, model=cfg.model, transport=transport,
              base_url=cfg.base_url)

    poll_once(cfg, telegram, llm, logger, offset=0)

    events = [json.loads(l) for l in logbuf.getvalue().splitlines()]
    kinds = {e["event"] for e in events}
    ok = {"wake", "reply"} <= kinds
    for e in events:
        out.write(json.dumps(e) + "\n")
    out.write(f"selftest: {'PASS' if ok else 'FAIL'} "
              f"(events: {sorted(kinds)})\n")
    return 0 if ok else 1


def main(argv):
    if len(argv) > 1 and argv[1] == "selftest":
        return run_selftest()
    return run_daemon()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
