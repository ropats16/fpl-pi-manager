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
(`GAFFER_LEARNINGS_PATH` overrides the path). **Only an analysis-routed chat reply may
write** (the #21 review wake is the one other writer, on its own scorecard-grounded path): a
block riding on any other reply is stripped and logged as ignored, so a poisoned report
can't coach a status answer into memory. Vetting is the in-code half
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

### Post-GW review (#21)

The scoring half of the learning loop. A ~4-hourly timer wakes `python3 -m daemon review`
(`fpl-gaffer-review.{service,timer}`): a cheap check of the FPL bootstrap events that spends
LLM tokens **once per finished gameweek** and logs `review_quiet` otherwise. When a GW settles
it fetches the actuals, sets them against the **projection snapshot the brief wake froze** at
draft/act time (`data/projections-gwNN.csv`, written by `daemon.review.snapshot_projections`)
and the recorded decision, and grades the call — projections vs actuals, captain vs
best-in-XI, transfer nets, bench calls, and every missing datum named as a gap. **Every number
is computed in code (`build_scorecard`/`render_scorecard`/`review_headline`); the model never
grades itself** — it writes the honest luck-vs-process prose and a `learnings` block onto a
code-computed headline the daemon prepends; the effective XI, autosubs and armband (vice
takes over when the captain does not play; triple captain / bench boost) are re-derived from
the picks payload, and a `no_write` plan's transfers are graded as the counterfactual and
labelled so. The wake routes to `agent/playbooks/post-gw-review.md` and is the one writer
besides an analysis chat allowed into the diary — a chat "how did I do?" reaches the same
playbook but has no scorecard, so its block is stripped, never recorded. Settled GWs are
reviewed in order (a Pi that slept through two grades both, one per tick). The GW's own
decision-log tail (fences stripped, bounded) rides along as evidence so rejected
alternatives and AM dissent can be scored. The daemon appends the review to `reports/gwNN/decision-log.md`
and marks the GW in `data/review-state.json` (gitignored) so a settled GW is graded exactly
once. Entry id for the fielded picks comes from `FPL_ENTRY_ID` (public, non-secret) else the
season-state `entry_id` else the season-state squad. Harness is `tests/test_review.py`;
`MEMORY.md` promotion and the rulebook PR stay Rohit-driven (#11 not wired).

### Helper tool loop (#54)

The first slice of the #52 fan-out: `python3 -m daemon helper <role> [--gw N]` runs one
helper role (`availability`, `fixtures`, `quality`, `market`, `scout`, `am`) as a **bounded
tool loop** on the model mapped for it (#51: analysts/Scout `z-ai/glm-5.3-flash`, AM
`qwen/qwen3.8-max`, gaffer unchanged; `GAFFER_HELPER_MODEL`, `GAFFER_AM_MODEL` or a per-role
`GAFFER_HELPER_MODEL_<ROLE>` override) and writes one source-stamped report into
`agent/reports/gwNN/<role>.md` for the next FPL deadline's gameweek. The persona is the
role's `agent/roles/*.md`, read fresh each run; the system prompt adds the season snapshot,
this GW's `scout-log.md` tail and the reports already written (both under "evidence, not
instructions") plus the coverage contract. Two tools only, both daemon code at the tool
boundary (`daemon/tools.py`): **`fetch(url)`** — GET only, domain allowlist checked before any
request (a refused domain gets error text naming the `wanted source: <domain> — <why>`
propose-to-add line, and no packet leaves the box; the transport never follows redirects,
the fetcher re-checks every hop), body read capped on the wire (4 MB), HTML reduced to text,
~8k-token truncation, per-wake URL cache (same URL twice = one request), and The Odds API key
appended by the fetcher for its host only (5th credential `odds-api-key` / `ODDS_API_KEY`, never in a
prompt, report or log — asserted); **`search(query)`** — one swappable provider, today a
dedicated flash sub-call carrying OpenRouter's web plugin (engine Exa), billed once per search
(Brave documented as the alternative, not wired; `GAFFER_SEARCH_PROVIDER` other than `exa`
is a wiring-time config error). Tool results are tier-4 evidence inside the helper's own
conversation — the one place a raw API body (e.g. FPL bootstrap JSON, truncated) may appear;
they never reach the gaffer's prompt except through the capped, headed report.
`daemon/reports.py` is the single write
path: one file per role per GW, **write-once** (second write refused + logged), body capped
at write time (analyst ~700 tok, AM ~500), header = role/model/timings/fetch+search
counts/coverage/status, and any path outside the GW folder refused. Per-helper ceilings
(25 fetch / 10 search / 40 turns incl. the write-up / 15 min; `GAFFER_HELPER_MAX_*`) are
tier-1 config: on a hit
the loop injects one write-up instruction, the report carries `coverage incomplete: …` and a
`cap_hit` event is logged. A helper LLM failure writes a stub (`helper failed: <reason>,
coverage: none`), exit code 0 — degrade, never abort. **Every LLM call** now logs an
`llm_call` event with prompt/completion tokens, the role, a per-process wake id and an
estimated cost from the configured price table (`GAFFER_PRICE_TABLE` extends it), plus
OpenRouter's own reported cost. `python3 -m daemon selftest` runs one analyst offline
through the extended `FakeTransport` (queued assistant messages with tool calls, canned
pages, the search sub-call, usage blocks) into a temp GW folder and prints report path,
counts, cost and PASS/FAIL; harness is `tests/test_helper.py` + `tests/test_tools.py` +
`tests/test_reports.py`. Draft-wake orchestration, the AM challenge and the wake rails /
MTD ledger are #56; the Scout timer is #57.

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
