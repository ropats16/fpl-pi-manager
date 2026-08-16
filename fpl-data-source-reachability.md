# FPL Data Source Reachability
**Project:** fpl-agent-system · **Probed:** 2026-08-01 (updated after livefpl/reddit sweep)

Two network paths in this runtime:
- **run_code sandbox:** SSL-inspecting proxy, strict allowlist → most hosts fail with `SSLError: UNEXPECTED_EOF_WHILE_READING`
- **web_fetch tool:** wider access, returns readable text (no JS render unless renderer configured)
- Reddit: reachable at network level but **403 datacenter-IP block** — use `web_search` for Reddit sweeps instead

## Confirmed WORKING (this runtime)
| Source | Path | Notes |
|---|---|---|
| FPL API (bootstrap-static etc.) | web_fetch | 200, valid JSON. Event 1 deadline 2026-08-15T17:30:00Z **STALE — verify** (season actually starts Aug 21). |
| vaastav/Fantasy-Premier-League (GitHub) | sandbox + web_fetch | Cleaned historical data. 2026-27 folder doesn't exist yet (pre-season). |
| The Odds API | web_fetch | 401 without key = reachable. User has requested a free key. |
| Telegram Bot API | web_fetch | 401 without token = reachable. Push notifications viable. |
| Understat | web_fetch | 200. Primary xG/xA source. |
| premierinjuries.com | web_fetch | 200. Structured injury table + RSS. |
| BBC Sport | sandbox | News fallback. |
| livefpl.net/prices | web_fetch | 200 but **React SPA shell** — data loads via XHR API; sniff endpoint on Pi via dev tools. **Now the community standard** (FFScout's price page is "powered by LiveFPL"). |
| fantasyfootballpundit.com/fpl-points-predictor | web_fetch | 200 WordPress page; table loads via JS — usable as benchmark only. |

## DEAD / dropped
| Source | Status |
|---|---|
| fplstatistics.co.uk | **Shut down** (Reddit: "RIP FPLstatistics" threads, 2025). Not just blocked — gone. Removed from plan. |

## BLOCKED here — re-probe on Raspberry Pi
| Source | Notes |
|---|---|
| FBref | 403 via web_fetch (Cloudflare); SSL-blocked in sandbox — **browser-header test impossible here** (network block precedes Cloudflare). On Pi: try browser headers / cloudscraper / playwright. Aggressive rate limits; optional source only. |
| fplreview.com | SSL-blocked in sandbox; **community top-2 projections** (with Fantasy Football Fix). Free tier caveat: projections taken down ~1h before deadline → snapshot early in the week. |
| Reddit (direct) | 403 datacenter IPs. Search via web_search works. |

## New leads from Reddit sweep (2026-08-01)
- **whatthef.pl** — meta-tracker scoring price-change predictors (Fix / Hub / LiveFPL) and points predictors. Use to pick the best feed each season.
- **fpl.solioanalytics.com** — projections site, unprobed.
- Mikkel Tokvam's Transfer Algorithm — mentioned as xPts source, unprobed.

## Probing notes
- GitHub raw + API allowed from sandbox. BBC allowed.
- Everything else from sandbox = SSL EOF at proxy. On the Pi there is no allowlist — only target-side blocks matter.
