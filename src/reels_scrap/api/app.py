"""FastAPI app factory. All logic lives in the modules this calls.

Endpoints:
  GET  /api/health
  GET  /api/reels                 list reel summaries
  GET  /api/reels/{id}            full reel record
  GET  /api/knowledge             aggregated topics (cached)
  GET  /api/search?q=&k=          semantic search
  POST /api/chat                  RAG answer + citations
  GET  /api/media/{id}/{kind}     serve thumbnail|video|pdf
A built frontend at web/dist (if present) is served at /.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import Config
from ..models import Reel
from .schemas import Answer, ChatRequest, Knowledge, ReelSummary, SearchHit


def _reels(cfg: Config) -> list[Reel]:
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


def _summary(r: Reel) -> ReelSummary:
    return ReelSummary(
        id=r.id, title=r.title or r.id, author=r.author, genre=r.genre, url=r.url,
        thumbnail_path=r.thumbnail_path, likes=r.likes, views=r.views,
        comments=r.comments, duration=r.duration, has_pdf=bool(r.pdf_path),
    )


def create_app(config_path: str = "config.yaml") -> FastAPI:
    cfg = Config.load(config_path)
    app = FastAPI(title="Reels Research Platform", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "reels": len(list(cfg.data_dir.glob("*.json")))}

    @app.get("/api/reels", response_model=list[ReelSummary])
    def list_reels() -> list[ReelSummary]:
        return [_summary(r) for r in _reels(cfg)]

    @app.get("/api/reels/{reel_id}")
    def get_reel(reel_id: str) -> dict:
        p = cfg.data_dir / f"{reel_id}.json"
        if not p.exists():
            raise HTTPException(404, f"no reel {reel_id}")
        return Reel.load(p).model_dump(mode="json")

    @app.get("/api/knowledge", response_model=Knowledge)
    def knowledge(rebuild: bool = False) -> Knowledge:
        from ..knowledge import load_knowledge

        return load_knowledge(cfg, rebuild=rebuild)

    @app.get("/api/search", response_model=list[SearchHit])
    def search(q: str, k: int = 8) -> list[SearchHit]:
        from ..search import search as do_search

        try:
            hits = do_search(cfg, q, k)
        except FileNotFoundError:
            raise HTTPException(409, "no search index — run extraction first")
        return [SearchHit(**h) for h in hits]

    @app.post("/api/chat", response_model=Answer)
    def chat(req: ChatRequest) -> Answer:
        from ..chat import answer_question

        try:
            return answer_question(cfg, req.question, k=req.k, history=req.history)
        except FileNotFoundError:
            raise HTTPException(409, "no search index — run extraction first")

    @app.get("/api/media/{reel_id}/{kind}")
    def media(reel_id: str, kind: str) -> FileResponse:
        p = cfg.data_dir / f"{reel_id}.json"
        if not p.exists():
            raise HTTPException(404, f"no reel {reel_id}")
        r = Reel.load(p)
        if kind == "video" and r.video_path:
            f = cfg.data_dir / r.video_path
        elif kind == "thumbnail" and r.thumbnail_path:
            f = cfg.data_dir / r.thumbnail_path
        elif kind == "pdf" and r.pdf_path:
            f = Path(r.pdf_path)
        else:
            raise HTTPException(404, f"no {kind} for {reel_id}")
        if not f.exists():
            raise HTTPException(404, f"{kind} file missing for {reel_id}")
        return FileResponse(f)

    # serve built frontend if present (prod single-port mode)
    dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")

    return app
