"""Entrypoint. `python3 -m daemon` runs the resident loop; `... selftest` drives
one full message->reply loop offline with every external faked (no network)."""

import io
import json
import sys

from daemon.config import Config, load_config
from daemon.http import FakeTransport, UrllibTransport
from daemon.llm import DEFAULT_BASE_URL
from daemon.loop import poll_once, run
from daemon.runtime import build_stack


def run_daemon(env=None, out=None):
    out = sys.stderr if out is None else out
    cfg = load_config(env)
    telegram, llm, logger = build_stack(cfg, UrllibTransport(), out)
    run(cfg, telegram, llm, logger)
    return 0


def run_selftest(out=None):
    out = sys.stdout if out is None else out
    cfg = Config(allowlist={42}, telegram_token="fake-token",
                 openrouter_key="fake-key", model="moonshotai/kimi-k2.5",
                 base_url=DEFAULT_BASE_URL, system_prompt="selftest")
    update = {
        "update_id": 1,
        "message": {"message_id": 1, "from": {"id": 42},
                    "chat": {"id": 42, "type": "private"},
                    "text": "selftest: are you alive?"},
    }
    transport = FakeTransport(updates_batches=[[update]],
                              llm_reply="Yes — gaffer online.")
    logbuf = io.StringIO()
    telegram, llm, logger = build_stack(cfg, transport, logbuf)

    poll_once(cfg, telegram, llm, logger, offset=0)

    events = [json.loads(l) for l in logbuf.getvalue().splitlines()]
    kinds = {e["event"] for e in events}
    ok = {"wake", "reply"} <= kinds
    for e in events:
        out.write(json.dumps(e) + "\n")
    out.write(f"selftest: {'PASS' if ok else 'FAIL'} (events: {sorted(kinds)})\n")
    return 0 if ok else 1


def main(argv):
    if len(argv) > 1 and argv[1] == "selftest":
        return run_selftest()
    return run_daemon()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
