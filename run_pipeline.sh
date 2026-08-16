#!/usr/bin/env sh
# run_pipeline.sh -- the whole FPL math pipeline in one command.
#
#   fetch -> distilled snapshot JSON -> distilled CSVs -> projections -> optimizer
#
# Modes:
#   ./run_pipeline.sh offline   # NO network: run from committed fixtures/ (file-contract seam)
#   ./run_pipeline.sh fetch     # live: pull FPL API (Pi / direct network), then run
#   ./run_pipeline.sh selftest  # run every tool's offline selftest (no data needed)
#
# Working CSVs + projections land in data/ (gitignored); the optimizer prints the squad/XI.
# The optimizer needs PuLP+CBC: this script prefers ./.venv/bin/python (Mac dev), else falls
# back to `python3` (Pi, where pulp is a system package). Override with PY=... if needed.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here"

# Pick the interpreter: project venv first (has pulp), then bare python3.
PY="${PY:-$here/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

DATA=data

run_math() {
  # distilled snapshot JSONs -> CSVs -> projections -> optimizer.
  # $1 = bootstrap snapshot json, $2 = fixtures snapshot json.
  # The bootstrap csv step enforces the collector health checks (aborts on bad data).
  echo "==> distill CSVs from $1 and $2"
  "$PY" fpl_api.py csv "$1" --out "$DATA"
  "$PY" fpl_api.py csv "$2" --out "$DATA"
  echo "==> projections"
  "$PY" fpl_projections.py
  echo "==> optimizer (scratch)"
  "$PY" fpl_optimizer.py scratch
}

newest() {
  # newest file matching a glob, or empty if none.
  ls -t $1 2>/dev/null | head -1
}

mode="${1:-}"
case "$mode" in
  offline)
    [ -f fixtures/bootstrap.json ] || { echo "missing fixtures/bootstrap.json" >&2; exit 1; }
    [ -f fixtures/fixtures.json ]  || { echo "missing fixtures/fixtures.json" >&2; exit 1; }
    run_math fixtures/bootstrap.json fixtures/fixtures.json
    ;;
  fetch)
    echo "==> fetch live FPL API -> $DATA"
    "$PY" fpl_api.py fetch --out "$DATA"
    boot=$(newest "$DATA/bootstrap-*.json")
    fix=$(newest "$DATA/fixtures-*.json")
    [ -n "$boot" ] && [ -n "$fix" ] || { echo "fetch produced no snapshots" >&2; exit 1; }
    run_math "$boot" "$fix"
    ;;
  selftest)
    echo "==> fpl_api";         "$PY" fpl_api.py selftest
    echo "==> fpl_projections"; "$PY" fpl_projections.py selftest
    echo "==> fpl_optimizer";   "$PY" fpl_optimizer.py selftest
    echo "ALL SELFTESTS PASS"
    ;;
  *)
    sed -n '2,/^[[:space:]]*$/p' "$0"   # print the leading comment block as usage
    exit 1
    ;;
esac
