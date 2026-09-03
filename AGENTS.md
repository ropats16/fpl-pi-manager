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
(Kimi K2.5), replies. The model's markdown reply is rendered to Telegram HTML
(`daemon/format.py`) so **bold**/bullets/`code` display properly, with a
plain-text fallback if a send is rejected. Stdlib-only (Pi-friendly, no pip). Every external is
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

### Learnings loop (#20)

An ad-hoc strategy question (backtest, compare, "is it worth", "what if") routes to
`agent/playbooks/analysis.md`, which tells the gaffer to answer from the snapshot +
projections + gw reports and to **end the reply with a fenced ` ```learnings ` JSON
block** (`{"specific": [...], "general": [...]}`, each entry a lesson + its
evidence). The daemon strips that block before Telegram (same seam as ` ```plan `,
#18; a malformed one is stripped and logged, never sent), vets it, and appends what
survives — one line per entry, `open(…, "a")` + fsync only — to
`agent/memory/learnings.md`, a model-writable append-only diary
(`GAFFER_LEARNINGS_PATH` overrides the path). **Only an analysis-routed question may
write**: a block riding on any other reply is stripped and logged as ignored, so a
poisoned report can't coach a status answer into memory. Vetting is the in-code half
of the tier-3 memory-write policy (`plans/security-hardening.md` §4): kind ∈
specific/general, provenance mandatory, whitespace collapsed to one line (an entry
can never inject a heading), any URL rejected, caps 280/200 chars and ≤4 per reply,
dedupe on the lesson; every rejection is logged with its reason. The policy's other
half — one git commit per model write for audit/revert — is the #11 deploy machinery
and is not wired yet; until then the diary is reviewed as ordinary repo diff. Prompt assembly then
injects a bounded relevance-scored selection (≤6 entries / ~1.5k chars) under an
"evidence, not instructions" delimiter, so a poisoned learning can bias judgment but
never carry an order. `python3 -m daemon selftest` demonstrates the 2-turn
record→recall path offline against a temp copy (never the repo file); harness is
`tests/test_learnings_loop.py`.

Config on the Pi comes from systemd (encrypted creds + root-owned
`/etc/fpl-gaffer/gaffer.env`), never the workspace — see `deploy/README.md` for
the one-time bootstrap and supervision (systemd `Restart=always`, boot-start,
15-min pull timer). The pull is also the deploy: `deploy/pull-reload.sh` merges
`main`→`pi/live` and, **only if tracked `*.py` changed**, gates a
`systemctl restart` behind the offline `daemon selftest` (a failing build never
restarts the live gaffer) and pushes a Telegram deploy/blocked notice via
`python3 -m daemon notify` (token-only, no LLM key). Markdown/data/squad apply
next wake, no restart. For local dev the daemon falls back to env vars
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
python3 season_state.py pull-squad                          # load my live FPL squad (entry_id from $FPL_ENTRY_ID)
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
`--force`. **`pull-squad`** fetches your live 15 from `/entry/{id}/event/{gw}/picks/`, maps
element ids → names/clubs/prices via the bootstrap, and loads them (with the real bank and
captain/vice) — the one-step way to replace a placeholder squad with your actual team. Pick
ids become the real FPL element ids; `--gw` defaults to the state's current gameweek.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues via the gh CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: root CONTEXT.md + docs/adr/, read lazily. See `docs/agents/domain.md`.
