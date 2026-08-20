"""Candidate reels the corpus suggests, and the Save / No / Later decision on each.

One discovery run at a time: it touches Instagram up to `max_requests` times and
stops dead on the first 429, so a second concurrent run is a 409, not a queue.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException

from ...config import Config
from ..deps import safe_id

# module-level status for the single background discovery run
_DISCOVER: dict = {"running": False, "summary": {}, "error": ""}


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/discover")
    def discover_list(state: str = "new") -> list[dict]:
        from ...discover import load_candidates

        rows = [c.__dict__ for c in load_candidates(cfg).values()]
        if state != "all":
            rows = [r for r in rows if r["state"] == state]
        rows.sort(key=lambda r: -r["score"])
        return rows

    @router.post("/api/discover/run")
    def discover_run(body: dict | None = None) -> dict:
        """Harvest candidates in the background — one run touches Instagram up to
        `max_requests` times and stops dead on the first 429."""
        if _DISCOVER["running"]:
            raise HTTPException(409, "a discovery run is already going")
        b = body or {}

        def _job():
            from ...discover import discover as run_discover

            try:
                _DISCOVER.update(summary=run_discover(
                    cfg,
                    browser=b.get("browser") or "cookies.txt",
                    max_requests=int(b.get("max_requests") or 40),
                    authors=int(b.get("authors") or 6),
                    hashtags=int(b.get("hashtags") or 4),
                ), error="")
            except Exception as ex:
                _DISCOVER.update(error=str(ex)[:300])
            _DISCOVER["running"] = False

        _DISCOVER.update(running=True, error="", summary={})
        threading.Thread(target=_job, daemon=True).start()
        return dict(_DISCOVER)

    @router.get("/api/discover/status")
    def discover_status() -> dict:
        return dict(_DISCOVER)

    @router.post("/api/discover/{cand_id}/{action}")
    def discover_action(cand_id: str, action: str) -> dict:
        from ...discover import REJECTED, SNOOZED, accept, set_state

        if action not in {"accept", "reject", "snooze"}:
            raise HTTPException(400, "action must be accept | reject | snooze")
        try:
            if action == "accept":
                return accept(cfg, safe_id(cand_id))
            state = REJECTED if action == "reject" else SNOOZED
            c = set_state(cfg, safe_id(cand_id), state)
            return {"id": c.id, "state": c.state}
        except KeyError as e:
            raise HTTPException(404, f"no candidate {cand_id}") from e

    return router
