# Pi inventory + recovery — 2026-08-16

Recovery run for [issue #2](https://github.com/ropats16/fpl-pi-manager/issues/2). SSH'd into `saf@fplpi.local` (host resolves via mDNS `.local`, not bare `fplpi`), inventoried `~/fpl/`, recovered the stranded code + latest data. Corrects several claims in [mac-folder-audit-2026-08-16.md](mac-folder-audit-2026-08-16.md).

## Pi runtime facts (for the runtime decision)

- **Model**: Raspberry Pi 4 Model B Rev 1.5
- **Arch**: aarch64 (ARM64)
- **OS**: Debian 13 (trixie) 13.5 — NOT "OS Lite" as the spec claimed; full Debian 13
- **Kernel**: 6.18.34+rpt-rpi-v8
- **Python**: 3.13.5 (`/usr/bin/python3`)
- **RAM**: 1.8 GiB total (the "2GB" model) — 973 MiB free, 1.5 GiB available, 1.8 GiB swap (unused)
- **Disk**: 29 G root, 6.6 G used, **21 G free** (24%)
- **Access**: key auth now installed (Mac `id_ed25519` in Pi `authorized_keys` via `ssh-copy-id`)

## Cron — CLAIMED NIGHTLY 03:30 DOES NOT EXIST

Checked every location; **no fpl cron/timer anywhere**:
- `crontab -l` (saf) → "no crontab for saf"
- root crontab → "no crontab for root"
- `/etc/cron.d/` → only `e2scrub_all` + `.placeholder`
- `/etc/crontab`, `/etc/cron.*` → no fpl refs
- `systemctl list-timers` → no fpl timers

Corroborating: **`~/fpl/logs/` is empty** — no fetch logs ever written. The nightly collector has never run on a schedule. Automated collection must be set up from scratch (issue #17).

## `~/fpl/` inventory (as of 2026-08-16; files dated 08-02 / 08-05)

```
~/fpl/
  fpl_api.py          7861 B   collector — HAS csv mode (fetch/distill/csv)
  fpl_optimizer.py   12365 B   ILP squad/XI optimizer (PuLP/CBC) — RECOVERED
  fpl_projections.py  8933 B   projections (identical to repo copy)
  draft_board.py      1646 B   fixture ticker + last-season draft board — RECOVERED
  data/               528 K    distilled csv + raw json (see below)
  logs/               empty
```

`data/` contents (newest 2026-08-05):
- `projections.csv` (132 K, GW1–6), `players.csv` (40 K), `fixtures.csv` (17 K), `events.csv`, `teams.csv`
- `entry-2928517.json` (current squad)
- raw snapshots: `bootstrap-20260802-0735.json` (245 K), `fixtures-20260802-0735.json` (77 K)

## Found vs lost

| Artifact | Prior audit said | Reality on Pi | Action |
|---|---|---|---|
| `fpl_optimizer.py` | "exists nowhere / lost" | **Present, 12 K, complete** | Recovered to repo root |
| csv-mode `fpl_api.py` | repo copy lacks `csv` mode | **Pi copy has it** (additive superset: `write_csv` + `cmd_csv` + `csv` command) | Overwrote repo `fpl_api.py` |
| `draft_board.py` | "fabricated, never existed" | **Present, real, 1.6 K** | Recovered to repo root; **audit was wrong** |
| `fpl_projections.py` | in repo | byte-identical on Pi | No change |
| Nightly 03:30 cron | "claimed" | **Does not exist; logs empty** | Must build (issue #17) |

**Nothing lost.** Everything the audit flagged as missing/fabricated is present on the Pi. The optimizer's `selftest` mode is intact (shape/budget/club-cap/k-sweep/XI/captain assertions).

## Recovery actions taken

- `fpl_optimizer.py`, `draft_board.py` → new files at repo root
- `fpl_api.py` → repo copy replaced with Pi csv-mode version (purely additive vs prior)
- `data/*` → pulled into repo `data/` (gitignored — verified via `git check-ignore`)
- All three recovered `.py` files pass `python3 -m py_compile`

## Caveats / follow-ups

- **Data is 11 days stale** (2026-08-05); projections GW1–6. A fresh fetch is needed before the GW1 pre-deadline run (issue #5), deadline **Fri 2026-08-21 17:30 UTC**.
- Optimizer needs `pulp` + CBC (`sudo apt install python3-pulp coinor-cbc`) — not yet verified installed on Pi (out of scope this run; not run per inventory-only decision).
- Optimizer `CURRENT_SQUAD` / `KEEP_NAMES` are hardcoded (Haaland, B.Fernandes kept) — matches the audit's listed squad.
- PII in recovered code/data (entry 2928517, squad names): keep repo private or scrub before any public push.
