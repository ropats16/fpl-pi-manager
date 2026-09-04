"""Season-state auto-sync — the daemon rolls `season-state.json` forward on
its own, so no wake ever drafts from a stale squad.

Why: after GW2 the squad pull + gameweek roll were a manual post-deadline
step (`season_state.py pull-squad` / `advance-gw`) that never ran; every brief
until 2026-09-04 was written from the GW1 squad. `SeasonSync.ensure(N)` brings
the state to gameweek N — squad = the 15 the entry actually fielded in N-1
(public picks endpoint), bank from the entry history, free transfers derived
from the entry's transfer history, current_gw = N — and is a no-op when the
state is already at or past N. Two callers: the post-GW review wake right
after a gameweek settles (target = settled + 1) and the draft wake before it
drafts (target = the deadline's GW, the guard). Never raises: a failure is a
`sync_error` event and the caller carries on with what it has.

Selling prices: the public picks endpoint carries no purchase price, so a
synced squad banks the current price as `bought_for` (same as pull-squad).
"""

import json

import fpl_api
import season_state

FT_CAP = season_state.FT_CAP
_NO_SPEND_CHIPS = ("wildcard", "freehit")


def free_transfers_entering(history, target_gw):
    """Free transfers available in `target_gw`, replayed from the entry's
    `/history/` payload: 1 after GW1, then each GW `min(5, max(ft - used, 0)
    + 1)`; a wildcard/free-hit GW spends nothing. GWs missing from the
    history count as no transfers made (a roll)."""
    used = {int(e.get("event", 0)): int(e.get("event_transfers") or 0)
            for e in (history or {}).get("current") or []}
    chip_gws = {int(c.get("event", 0)): str(c.get("name", "")).lower()
                for c in (history or {}).get("chips") or []}
    ft = 1
    for gw in range(2, max(int(target_gw), 2)):
        if chip_gws.get(gw) in _NO_SPEND_CHIPS:
            ft = min(FT_CAP, ft + 1)
        else:
            ft = min(FT_CAP, max(ft - used.get(gw, 0), 0) + 1)
    return ft


class SeasonSync:
    """`fetch_picks(gw)` -> raw `/entry/{id}/event/{gw}/picks/` payload;
    `fetch_history()` -> raw `/entry/{id}/history/`; `fetch_bootstrap()` ->
    a distilled bootstrap (players + teams). All injectable; the cmd layer
    wires fpl_api."""

    def __init__(self, state_path, entry_id, fetch_picks, fetch_history,
                 fetch_bootstrap, logger, clock=None):
        self.state_path = state_path
        self.entry_id = entry_id
        self.fetch_picks = fetch_picks
        self.fetch_history = fetch_history
        self.fetch_bootstrap = fetch_bootstrap
        self.logger = logger
        self.clock = clock

    def _load(self):
        with open(self.state_path, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            raise ValueError("season state is not an object")
        return state

    def ensure(self, target_gw):
        """Bring the state to `target_gw`. Returns a summary dict with
        `status` ∈ current | synced | skipped | error (+ from_gw, to_gw,
        free_transfers, squad, reason)."""
        target_gw = int(target_gw)
        res = {"status": "error", "from_gw": None, "to_gw": target_gw}
        try:
            state = self._load()
            cur = state.get("current_gw")
            res["from_gw"] = cur
            if cur is not None and int(cur) >= target_gw:
                res["status"] = "current"
                self.logger.event("season_sync", **res)
                return res
            if self.entry_id is None:
                res["status"], res["reason"] = "skipped", "no entry id"
                self.logger.event("season_sync", **res)
                return res
            settled = target_gw - 1
            picks = self.fetch_picks(settled)
            boot = self.fetch_bootstrap()
            history = self.fetch_history()
            decision = fpl_api.build_squad_decision(picks, boot, settled)
            season_state.set_squad(state, decision)
            state["current_gw"] = target_gw
            state["free_transfers"] = free_transfers_entering(history, target_gw)
            state["active_chip"] = "none"
            state["entry_id"] = int(self.entry_id)
            season_state.log_decision(state, "auto-sync", {
                "from_gw": cur, "picks_of_gw": settled,
                "free_transfers": state["free_transfers"], "bank": state.get("bank")})
            season_state.save_state(state, self.state_path)
            res.update(status="synced", free_transfers=state["free_transfers"],
                       squad=len(decision["picks"]), bank=state.get("bank"))
            self.logger.event("season_sync", **res)
            return res
        except Exception as e:            # noqa: BLE001 — a sync must never take a wake down
            res["status"], res["reason"] = "error", f"{type(e).__name__}: {e}"
            self.logger.event("sync_error", target_gw=target_gw, error=type(e).__name__,
                              detail=str(e))
            return res
