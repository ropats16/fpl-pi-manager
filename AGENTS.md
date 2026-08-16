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

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues via the gh CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: root CONTEXT.md + docs/adr/, read lazily. See `docs/agents/domain.md`.
