"""GET /api/health — one call that answers "is this thing actually fine?"."""

from __future__ import annotations

import json as _json
import time
from pathlib import Path

from fastapi import APIRouter

from ...config import Config


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    def health(deep: bool = False) -> dict:
        """`deep=true` adds an Instagram session probe — a network round-trip, so it
        is opt-in and not what a liveness check should poll.
        """
        import shutil

        reels = len(list(cfg.data_dir.glob("*.json")))
        checks: dict[str, dict] = {}

        # disk — the corpus grows by ~5MB/reel and nothing warns you
        du = shutil.disk_usage(cfg.data_dir if cfg.data_dir.exists() else ".")
        free_gb = round(du.free / 1e9, 1)
        checks["disk"] = {"ok": free_gb > 5, "free_gb": free_gb}

        # search index freshness — "which reels are missing from it", NOT mtime.
        # Reel json is rewritten by things that do not change indexed text (a
        # Compare variant, an annotation, an author_handle backfill), so an mtime
        # comparison reported the index stale permanently — red light, nothing wrong.
        ip = cfg.output_dir / "search_index.npz"
        mp = cfg.output_dir / "search_index.json"
        if ip.exists() and mp.exists():
            try:
                indexed = {m["reel_id"] for m in _json.loads(mp.read_text(encoding="utf-8"))}
            except ValueError:
                indexed = set()
            have = {p.stem for p in cfg.data_dir.glob("*.json")}
            missing = have - indexed
            checks["search_index"] = {
                "ok": not missing,
                "age_hours": round((time.time() - ip.stat().st_mtime) / 3600, 1),
                "indexed": len(indexed & have),
                "not_indexed": len(missing),
            }
        else:
            checks["search_index"] = {"ok": False, "missing": True}

        # cookie file — presence and age; expiry is the #1 cause of a dead sync
        ck = Path(cfg.auth.cookies_file or "cookies.txt")
        if ck.exists():
            age_d = round((time.time() - ck.stat().st_mtime) / 86400, 1)
            checks["cookies"] = {"ok": age_d < 30, "age_days": age_d, "path": str(ck)}
        else:
            checks["cookies"] = {"ok": False, "missing": True, "path": str(ck)}

        # local vision endpoint — only meaningful if one is configured
        base = cfg.extract.vision_local.base_url
        if base:
            try:
                import requests

                r = requests.get(base.rstrip("/") + "/models", timeout=3)
                checks["local_vision"] = {"ok": r.status_code == 200, "url": base}
            except Exception as e:
                checks["local_vision"] = {"ok": False, "url": base, "error": str(e)[:120]}

        if deep:
            from ...ingest.collection import session_ok

            ok, why = session_ok(
                str(ck) if ck.exists() else (cfg.auth.cookies_from_browser or "chrome")
            )
            checks["instagram_session"] = {"ok": ok, "detail": why}

        return {"ok": all(c.get("ok") for c in checks.values()), "reels": reels, "checks": checks}

    return router
