# fpl-pi-manager

Autonomous FPL manager ("gaffer") for a Raspberry Pi 4B 2GB. Wayfinder map + research in `plans/`; the spec is [issue #1](https://github.com/ropats16/fpl-pi-manager/issues/1); tickets are its sub-issues.

## Run the pipeline

One command runs the whole math pipeline (fetch → distilled CSVs → projections → optimizer):

```sh
./run_pipeline.sh offline    # no network — runs from committed fixtures/ (file-contract seam)
./run_pipeline.sh fetch      # live pull of public FPL data (Pi / direct net), then run
./run_pipeline.sh selftest   # every tool's offline selftest
```

Working CSVs + `projections.csv` land in `data/` (gitignored); the optimizer prints the squad/XI.
The `csv` step enforces the collector health checks (player-count 550–900, exactly 38 events)
and aborts on a bad snapshot.

The optimizer needs an ILP solver (PuLP + CBC). One-time dev setup on the Mac:

```sh
python3 -m venv .venv && ./.venv/bin/pip install pulp   # bundles CBC; .venv is gitignored
```

`run_pipeline.sh` prefers `./.venv/bin/python`, else falls back to `python3` (the Pi, where
pulp is a system package: `sudo apt install -y python3-pulp coinor-cbc`).

## Gaffer daemon (walking skeleton — #15)

The resident agent: long-polls Telegram, answers only the numeric-ID allowlist
(unknown sender = silent drop + log), makes one OpenRouter LLM round-trip
(Kimi K2.5), replies. Stdlib-only (Pi-friendly, no pip). Every external is
faked at the HTTP edge (`daemon/http.py` transport seam), so the whole
wake→reply loop runs offline.

```sh
python3 -m daemon selftest                    # offline full message→reply loop, no network/secrets
python3 -m unittest discover -s tests -v       # HTTP-edge harness (all seams faked)
python3 -m daemon                              # run the daemon (needs config — see below)
```

### Workspace + prompt assembly (#16)

The gaffer's persona and know-how live as markdown under `agent/` — `GAFFER.md`
(persona + standing orders), `roles/*.md` (Scout, four analysts, AM), `playbooks/*.md`
(per-task how-tos), `memory/MEMORY.md` (capped learnings index) — read fresh each
wake so a pull applies next message. `daemon/prompt.py` assembles the system prompt
lean index-then-fetch: persona + memory index + report index + today's playbook +
a **distilled season snapshot** (squad/bank/FT/chips from `season-state.json`
joined to `data/projections.csv` by normalized name — projected pts per player and
for the XI). Raw snapshot JSON and raw API payloads **never** enter a prompt (#9/#10),
and the assembled prompt is held under a hard ~25k-token cap, critical facts at the
edges — both asserted at the HTTP-edge harness (`tests/test_assembly_loop.py`).
`python3 -m daemon selftest` demonstrates the whole path offline: "how's my team
looking?" → grounded, bounded prompt → reply.

Config on the Pi comes from systemd (encrypted creds + root-owned
`/etc/fpl-gaffer/gaffer.env`), never the workspace — see `deploy/README.md` for
the one-time bootstrap and supervision (systemd `Restart=always`, boot-start,
15-min pull timer). For local dev the daemon falls back to env vars
(`GAFFER_ALLOWLIST_USER_IDS`, `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`; see
`.env.example`). Locked decisions: runtime #7, LLM endpoint #8, security #10,
deploy #11.

## Season state (single source of truth)

`season-state.json` is the live record of "my season" — squad, bank, free transfers, chips.
`season_state.py` initializes it from the real FPL entry and **writes it back whenever a
decision is acted on** (the invariant the prior effort lacked). Money is kept in integer
tenths internally to avoid float drift.

```sh
python3 season_state.py init                                # entry_id from $FPL_ENTRY_ID (see .env.example)
python3 season_state.py set-squad fixtures/squad-decision.json  # act on: initial 15-man build
python3 season_state.py transfer OUT_ID IN_PLAYER.json      # sell/buy, spend an FT (or -4 hit)
python3 season_state.py chip wildcard                       # play a chip (mark used)
python3 season_state.py advance-gw                          # roll FT +1 (cap 5); unlock set 2 at GW20
python3 season_state.py show                                # print current squad/bank/FT
python3 season_state.py selftest                            # fixture-based read→act→write-back
```

Free transfers roll +1 per GW up to 5; chips are two sets (GW1–19, GW20–38) tracked as
available/used. `season_state.py` reads and rewrites `season-state.json` in place, so it is
the live source of truth. Your **entry id is never committed**: it is read from `$FPL_ENTRY_ID`
(per-machine `.env`, gitignored — same var on Mac and Pi) so the committed state carries
`entry_id: null` and the repo can go public. `init` optionally takes `--entry data/entry-*.json`
(gitignored) for the post-GW1 deadline bank, and refuses to clobber a populated squad without
`--force`.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues via the gh CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: root CONTEXT.md + docs/adr/, read lazily. See `docs/agents/domain.md`.
