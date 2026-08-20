"""FastAPI app factory: config, CORS, routers, the built frontend. Nothing else.

The endpoints themselves live one per concern under `routes/` — see
`routes/__init__.py`. This file owns assembly order, and the only order that
matters is that the SPA catch-all is mounted last.

Re-exported below for callers that predate the 2026-08-20 split
(`tests/test_sync_status.py` imports `_stage_and_progress` from here).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import Config
from .routes import ROUTERS
from .routes.sync import STAGES, SourceIn, SyncIn, _stage_and_progress

__all__ = ["STAGES", "SourceIn", "SyncIn", "_stage_and_progress", "create_app"]


def create_app(config_path: str = "config.yaml") -> FastAPI:
    cfg = Config.load(config_path)
    app = FastAPI(title="Reels Research Platform", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    for build in ROUTERS:
        app.include_router(build(cfg, config_path))

    # serve built frontend if present (prod single-port mode)
    dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if dist.exists():
        # assets served directly; everything else falls back to index.html so the
        # SPA's client-side routes (/reels, /search, …) survive a hard refresh.
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        index = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(404, "not found")
            f = dist / full_path
            if full_path and f.is_file():
                return FileResponse(f)
            return FileResponse(index)

    return app
