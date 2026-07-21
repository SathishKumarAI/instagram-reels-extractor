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

import re
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import Config
from ..models import Reel
from .schemas import (
    Answer,
    CategoryStat,
    ChatRequest,
    Knowledge,
    ReelSummary,
    SearchHit,
    Stats,
)


class SourceIn(BaseModel):
    url: str
    name: str = ""
    type: str = "collection"


class SyncIn(BaseModel):
    backend: str = "claude-cli"       # claude-cli | api | local
    browser: str = "chrome"
    only: list[str] | None = None


# module-level status for the single background sync (polled by the UI)
_SYNC: dict = {"running": False, "backend": "", "ingested": 0, "sources": 0, "error": ""}


_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_id(reel_id: str) -> str:
    """Guard against path traversal — reel ids are shortcodes only."""
    if not _ID_RE.match(reel_id):
        raise HTTPException(400, "invalid reel id")
    return reel_id


def _reels(cfg: Config) -> list[Reel]:
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


def _summary(r: Reel) -> ReelSummary:
    return ReelSummary(
        id=r.id, title=r.title or r.id, author=r.author, genre=r.genre, tags=r.tags, url=r.url,
        thumbnail_path=r.thumbnail_path, likes=r.likes, views=r.views,
        comments=r.comments, duration=r.duration, timestamp=r.timestamp, has_pdf=bool(r.pdf_path),
        tokens_in=r.tokens.get("input", 0), tokens_out=r.tokens.get("output", 0),
        backend=str(r.tokens.get("backend", "") or ""),
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
        from ..collections import list_manifests
        from ..userstate import load_annotations

        ann = load_annotations(cfg.output_dir)
        # reel_id -> [collection slug, …] from the saved-collection manifests
        by_reel: dict[str, list[str]] = {}
        for m in list_manifests(cfg.output_dir):
            for rid in m.reel_ids:
                by_reel.setdefault(rid, []).append(m.slug)
        out = []
        for r in _reels(cfg):
            s = _summary(r)
            s.collections = by_reel.get(r.id, [])
            a = ann.get(r.id, {})
            s.starred, s.read, s.archived = (
                bool(a.get("starred")), bool(a.get("read")), bool(a.get("archived")),
            )
            out.append(s)
        return out

    @app.get("/api/annotations")
    def get_annotations() -> dict:
        from ..userstate import load_annotations

        return load_annotations(cfg.output_dir)

    @app.post("/api/reels/{reel_id}/annotate")
    def annotate_reel(reel_id: str, body: dict) -> dict:
        from ..userstate import annotate

        return annotate(cfg.output_dir, _safe_id(reel_id), body or {})

    @app.get("/api/views")
    def get_views() -> list[dict]:
        from ..userstate import load_views

        return load_views(cfg.output_dir)

    @app.post("/api/views")
    def post_view(body: dict) -> list[dict]:
        from ..userstate import save_view

        name = (body or {}).get("name", "").strip()
        if not name:
            raise HTTPException(400, "view name required")
        return save_view(cfg.output_dir, name, (body or {}).get("filters", {}))

    @app.post("/api/views/{name}/delete")
    def remove_view(name: str) -> list[dict]:
        from ..userstate import delete_view

        return delete_view(cfg.output_dir, name)

    # rough USD per 1M tokens by model family (Claude). Used for an estimate only.
    _PRICES = {"opus": (15.0, 75.0), "sonnet": (3.0, 15.0), "haiku": (0.8, 4.0)}

    def _price(model: str) -> tuple[float, float]:
        m = (model or "").lower()
        for k, v in _PRICES.items():
            if k in m:
                return v
        return _PRICES["sonnet"]

    @app.post("/api/tags/rename")
    def rename_tag(body: dict) -> dict:
        """Rename/merge a tag across all reels. Empty `to` deletes the tag."""
        src = (body or {}).get("from", "").strip().lower()
        dst = (body or {}).get("to", "").strip().lower()
        if not src:
            raise HTTPException(400, "'from' tag required")
        changed = 0
        for p in cfg.data_dir.glob("*.json"):
            r = Reel.load(p)
            if src not in r.tags:
                continue
            new = [t for t in r.tags if t != src]
            if dst and dst not in new:
                new.insert(r.tags.index(src), dst)
            if new != r.tags:
                r.tags = new
                r.save(cfg.data_dir)
                changed += 1
        return {"from": src, "to": dst or None, "reels_updated": changed}

    @app.get("/api/report")
    def report() -> dict:
        """Last run's per-reel stage report (ingest/transcript/vision ok/error)."""
        p = cfg.output_dir / "run_report.json"
        if not p.exists():
            return {"reels": {}, "note": "no run yet"}
        import json as _json

        return _json.loads(p.read_text())

    @app.post("/api/ingest")
    def ingest_url(body: dict, bg: BackgroundTasks) -> dict:
        """Quick-add a single reel URL — downloads + caption in the background (no vision)."""
        url = (body or {}).get("url", "").strip()
        if not re.match(r"^https?://(www\.)?instagram\.com/(reel|reels|p|tv)/[\w-]+", url):
            raise HTTPException(400, "not an Instagram reel URL")

        def _job(u: str):
            import tempfile
            from ..config import Config as _C
            from ..pipeline import run_pipeline
            c = _C.load(config_path)
            c.extract.transcript = c.extract.ocr = c.extract.vision = False  # fast caption-only
            c.output.pdf = c.output.docs_site = False
            f = Path(tempfile.mkstemp(suffix=".txt", dir=c.data_dir)[1])
            f.write_text(u + "\n")
            c.source.type = "urls"
            c.source.urls_file = str(f)
            c.source.resume = True
            try:
                run_pipeline(c, config_path)
            finally:
                f.unlink(missing_ok=True)

        bg.add_task(_job, url)
        return {"accepted": url, "note": "downloading in background; refresh in a moment. Run sync/backfill for AI extraction."}

    @app.get("/api/stats", response_model=Stats)
    def stats() -> Stats:
        from collections import Counter, defaultdict

        pin, pout = _price(cfg.extract.vision_model)
        reels = _reels(cfg)
        cats: dict[str, dict] = defaultdict(lambda: {"reels": 0, "in": 0, "out": 0, "cost": 0.0})
        tags: Counter = Counter()
        tin = tout = 0
        tcost = 0.0
        for r in reels:
            g = r.genre or "uncategorized"
            i, o = int(r.tokens.get("input", 0)), int(r.tokens.get("output", 0))
            # real cost from the CLI envelope when present, else estimate from tokens
            c = r.tokens.get("cost_usd")
            c = float(c) if c else round(i / 1e6 * pin + o / 1e6 * pout, 4)
            cats[g]["reels"] += 1
            cats[g]["in"] += i
            cats[g]["out"] += o
            cats[g]["cost"] += c
            tin += i
            tout += o
            tcost += c
            tags.update(r.tags)

        categories = [
            CategoryStat(genre=g, reels=v["reels"], tokens_in=v["in"], tokens_out=v["out"],
                         cost_usd=round(v["cost"], 2))
            for g, v in sorted(cats.items(), key=lambda kv: -kv[1]["reels"])
        ]
        return Stats(
            total_reels=len(reels), tokens_in=tin, tokens_out=tout,
            cost_usd=round(tcost, 2),
            cost_note=("real cost from claude-cli when available (mostly cached CLI "
                       "system-prompt/tools, not reel content); $0 on subscription. "
                       "Set ANTHROPIC_API_KEY for the ~15x-cheaper API backend."),
            categories=categories, top_tags=[[t, n] for t, n in tags.most_common(30)],
        )

    def _export_reels(ids: str | None) -> list[Reel]:
        """All reels, or just the given comma-separated ids (order preserved)."""
        reels = _reels(cfg)
        if not ids:
            return reels
        want = [i for i in (x.strip() for x in ids.split(",")) if i]
        by_id = {r.id: r for r in reels}
        return [by_id[i] for i in want if i in by_id]

    @app.get("/api/export.csv")
    def export_csv(ids: str | None = None):
        import csv
        import io

        from fastapi.responses import Response

        cols = ["id", "title", "author", "genre", "tags", "likes", "comments",
                "views", "duration", "tokens_in", "tokens_out", "summary",
                "transcript", "url"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in _export_reels(ids):
            w.writerow([
                r.id, r.title, r.author, r.genre, ", ".join(r.tags),
                r.likes or "", r.comments or "", r.views or "",
                r.duration or "", r.tokens.get("input", 0), r.tokens.get("output", 0),
                (r.summary or "").replace("\n", " "),
                (r.transcript_text or "").replace("\n", " "), r.url,
            ])
        return Response(
            content=buf.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=reels.csv"},
        )

    @app.get("/api/export.md")
    def export_md(ids: str | None = None):
        from fastapi.responses import Response

        lines = ["# Reels export\n"]
        by_genre: dict[str, list] = {}
        for r in _export_reels(ids):
            by_genre.setdefault(r.genre or "uncategorized", []).append(r)
        for g in sorted(by_genre):
            lines.append(f"\n## {g}\n")
            for r in by_genre[g]:
                tags = " ".join(f"#{t}" for t in r.tags)
                lines.append(f"- **[{r.title or r.id}]({r.url})** — {r.author}  {tags}")
                if r.summary:
                    lines.append(f"  - {r.summary}")
        return Response("\n".join(lines), media_type="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=reels.md"})

    @app.get("/api/export.xlsx")
    def export_xlsx(ids: str | None = None):
        try:
            from openpyxl import Workbook
        except ImportError:
            raise HTTPException(501, "xlsx export needs openpyxl — `pip install openpyxl` (or use export.csv)")
        import io

        from fastapi.responses import Response

        wb = Workbook()
        ws = wb.active
        ws.title = "reels"
        ws.append(["id", "title", "author", "genre", "tags", "likes", "comments",
                   "tokens_in", "tokens_out", "summary", "url"])
        for r in _export_reels(ids):
            ws.append([r.id, r.title, r.author, r.genre, ", ".join(r.tags),
                       r.likes or 0, r.comments or 0, r.tokens.get("input", 0),
                       r.tokens.get("output", 0), (r.summary or "")[:1000], r.url])
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=reels.xlsx"},
        )

    @app.get("/api/reels/{reel_id}")
    def get_reel(reel_id: str) -> dict:
        p = cfg.data_dir / f"{_safe_id(reel_id)}.json"
        if not p.exists():
            raise HTTPException(404, f"no reel {reel_id}")
        from ..userstate import load_annotations

        d = Reel.load(p).model_dump(mode="json")
        d["annotation"] = load_annotations(cfg.output_dir).get(reel_id, {})
        return d

    @app.get("/api/reels/{reel_id}/similar")
    def similar(reel_id: str, k: int = 6) -> list[SearchHit]:
        """'More like this' — semantic neighbours via the existing embedding index."""
        p = cfg.data_dir / f"{_safe_id(reel_id)}.json"
        if not p.exists():
            raise HTTPException(404, f"no reel {reel_id}")
        r = Reel.load(p)
        query = " ".join(filter(None, [r.title, r.summary, " ".join(r.tags)]))[:500]
        from ..search import search as do_search

        try:
            hits = [h for h in do_search(cfg, query, k + 3) if h["reel_id"] != reel_id]
        except FileNotFoundError:
            return []
        return [SearchHit(**h) for h in hits[:k]]

    @app.get("/api/sources")
    def list_sources_ep() -> list[dict]:
        from dataclasses import asdict

        from ..sources import load_sources, load_state

        state = load_state(cfg.output_dir)
        out = []
        for s in load_sources():
            d = asdict(s)
            st = state.get(s.name, {})
            d["last_run"] = st.get("last_run")
            d["reels"] = st.get("last_current")
            out.append(d)
        return out

    @app.post("/api/sources")
    def add_source_ep(body: SourceIn) -> dict:
        from dataclasses import asdict

        from ..sources import add_source

        try:
            s = add_source(body.url, name=body.name or None, type=body.type)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"invalid source: {e}")
        return asdict(s)

    @app.post("/api/sources/{name}/toggle")
    def toggle_source_ep(name: str) -> dict:
        from dataclasses import asdict

        from ..sources import load_sources, save_sources

        rows = load_sources()
        hit = next((s for s in rows if s.name == name), None)
        if not hit:
            raise HTTPException(404, f"no source {name}")
        hit.enabled = not hit.enabled
        save_sources(rows)
        return asdict(hit)

    @app.get("/api/sync/status")
    def sync_status() -> dict:
        return dict(_SYNC)

    @app.post("/api/sync")
    def sync_ep(body: SyncIn) -> dict:
        """Kick off an incremental sync in the background with a chosen vision backend.
        The UI picks Claude-code vs the local GPU box here."""
        if _SYNC["running"]:
            raise HTTPException(409, "a sync is already running")
        backend = body.backend
        if backend not in {"claude-cli", "api", "local"}:
            raise HTTPException(400, "backend must be claude-cli | api | local")

        def _job():
            from ..config import Config as _C
            from ..sources import poll_all
            c = _C.load(config_path)
            c.extract.transcript = c.extract.ocr = False   # claude-only style (fast)
            c.extract.vision = True
            c.extract.vision_backend = backend
            try:
                results = poll_all(c, config_path, browser=body.browser or "chrome",
                                   only=body.only or None)
                _SYNC.update(
                    running=False,
                    ingested=sum(r.ingested for r in results),
                    sources=len(results),
                    error="",
                )
            except Exception as ex:  # noqa: BLE001
                _SYNC.update(running=False, error=str(ex)[:300])

        if backend == "local":
            c0 = Config.load(config_path)
            if not c0.extract.vision_local.base_url:
                raise HTTPException(400, "backend=local needs extract.vision_local.base_url in config")

        _SYNC.update(running=True, backend=backend, ingested=0, sources=0, error="")
        threading.Thread(target=_job, daemon=True).start()
        return dict(_SYNC)

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
        if kind not in {"video", "thumbnail", "pdf"}:
            raise HTTPException(404, f"no {kind}")
        p = cfg.data_dir / f"{_safe_id(reel_id)}.json"
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
