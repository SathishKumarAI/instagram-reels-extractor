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

import json as _json
import re
import threading
import time
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
# …and for the single background batch comparison
_BATCH: dict = {"running": False, "done": 0, "total": 0, "current": "",
                "backends": [], "errors": []}
# …and for the single background discovery run
_DISCOVER: dict = {"running": False, "summary": {}, "error": ""}


_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# pipeline stages in run order, as they appear in run.log progress lines
STAGES = ["enumerate", "ingest", "process", "site", "index"]
_STAGE_RE = re.compile(r"\[(ingest|process|site|index)\]")
_COUNT_RE = re.compile(r"\((\d+)/(\d+)\)")


def _log_tail(cfg: Config, lines: int) -> tuple[list[str], float | None]:
    """Last N lines of run.log + seconds since it was last written.

    Every sync writes it — CLI runs included — so the UI can follow a sync it
    did not start itself.
    """
    p = cfg.output_dir / "run.log"
    if not p.exists():
        return [], None
    tail = p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    return tail, time.time() - p.stat().st_mtime


def _stage_and_progress(tail: list[str]) -> tuple[str, dict]:
    """Newest stage marker in the log wins; `(i/n)` on that line is its progress."""
    for line in reversed(tail):
        m = _STAGE_RE.search(line)
        if m:
            c = _COUNT_RE.search(line)
            return m.group(1), ({"done": int(c.group(1)), "total": int(c.group(2))} if c else {})
        if "collection " in line and " page " in line:
            return "enumerate", {}
    return "", {}


def _sync_sources(cfg: Config) -> list[dict]:
    """Per-source outcome of the last sync, from output/sources_state.json."""
    from ..sources import load_state

    return [
        {
            "name": name,
            "last_run": s.get("last_run"),
            "runs": s.get("runs", 0),
            "current": s.get("last_current", 0),
            "new": s.get("last_new", 0),
            "ingested": s.get("last_ingested", 0),
            "failed": len(s.get("failed_ids", [])),
            "error": s.get("error") or "",
        }
        for name, s in sorted(load_state(cfg.output_dir).items())
    ]


def _run_report(cfg: Config) -> dict:
    """Per-stage ok/error tallies from the last pipeline run."""
    p = cfg.output_dir / "run_report.json"
    if not p.exists():
        return {}
    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    stages: dict[str, dict[str, int]] = {}
    for o in data.get("reels", {}).values():
        for stage, status in o.get("stages", {}).items():
            stages.setdefault(stage, {}).setdefault(status, 0)
            stages[stage][status] += 1
    return {
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "summary": data.get("summary", {}),
        "stages": stages,
    }


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
        model=str(r.tokens.get("model", "") or ""),
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
    def health(deep: bool = False) -> dict:
        """One call that answers "is this thing actually fine?".

        `deep=true` adds an Instagram session probe — a network round-trip, so it
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
            from ..ingest.collection import session_ok

            ok, why = session_ok(str(ck) if ck.exists() else (cfg.auth.cookies_from_browser or "chrome"))
            checks["instagram_session"] = {"ok": ok, "detail": why}

        return {"ok": all(c.get("ok") for c in checks.values()), "reels": reels, "checks": checks}

    @app.get("/api/reels", response_model=list[ReelSummary])
    def list_reels() -> list[ReelSummary]:
        from ..collections import reels_by_collection
        from ..userstate import load_annotations

        ann = load_annotations(cfg.output_dir)
        by_reel = reels_by_collection(cfg.output_dir)
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

    @app.get("/api/tags")
    def list_tags() -> list[dict]:
        """Every tag with the collections it appears in.

        A tag alone says what a reel is about; the collection says which shelf of
        yours it belongs on. The UI colours chips by collection, so it needs both.
        """
        from ..collections import reels_by_collection

        by_reel = reels_by_collection(cfg.output_dir)

        tags: dict[str, dict] = {}
        for r in _reels(cfg):
            cols = by_reel.get(r.id, [])
            for t in r.tags:
                e = tags.setdefault(t, {"tag": t, "count": 0, "collections": {}})
                e["count"] += 1
                for c in cols:
                    e["collections"][c] = e["collections"].get(c, 0) + 1
        out = []
        for e in tags.values():
            cols = sorted(e["collections"].items(), key=lambda kv: -kv[1])
            out.append({"tag": e["tag"], "count": e["count"],
                        "collections": [{"name": n, "count": c} for n, c in cols]})
        out.sort(key=lambda e: (-e["count"], e["tag"]))
        return out

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

        return _json.loads(p.read_text(encoding="utf-8"))

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
            f.write_text(u + "\n", encoding="utf-8")
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
        except ImportError as e:
            raise HTTPException(501, "xlsx export needs openpyxl — `pip install openpyxl` (or use export.csv)") from e
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
        from ..collections import reels_by_collection
        from ..userstate import load_annotations

        d = Reel.load(p).model_dump(mode="json")
        # membership lives in the manifests, not on the record — the reader shows
        # the shelf a reel came from, so the detail response needs it too
        d["collections"] = reels_by_collection(cfg.output_dir).get(reel_id, [])
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
        except Exception as e:
            raise HTTPException(400, f"invalid source: {e}") from e
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
    def sync_status(lines: int = 150) -> dict:
        """Everything the Sync tab draws: pipeline stage, per-source outcome,
        last run report and a live log tail.

        `live` is true for a sync started here OR one started from the CLI — the
        log file is the shared signal, so the UI follows either.
        """
        tail, age = _log_tail(cfg, max(1, min(lines, 1000)))
        stage, progress = _stage_and_progress(tail)
        return {
            **_SYNC,
            "live": bool(_SYNC["running"] or (age is not None and age < 60)),
            "log_age_sec": age,
            "stages": STAGES,
            "stage": stage,
            "progress": progress,
            "log": tail,
            "source_state": _sync_sources(cfg),
            "report": _run_report(cfg),
        }

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
            except Exception as ex:
                _SYNC.update(running=False, error=str(ex)[:300])

        if backend == "local":
            c0 = Config.load(config_path)
            if not c0.extract.vision_local.base_url:
                raise HTTPException(400, "backend=local needs extract.vision_local.base_url in config")

        _SYNC.update(running=True, backend=backend, ingested=0, sources=0, error="")
        threading.Thread(target=_job, daemon=True).start()
        return dict(_SYNC)

    @app.post("/api/reels/{reel_id}/compare")
    def compare_reel_ep(reel_id: str, body: dict | None = None) -> dict:
        """Run the named backends over one reel, store both variants, return the diff.

        Synchronous: claude-cli is ~30s and local ~5s, so the UI waits with a spinner
        rather than growing a second job system for a single-reel action.
        """
        from ..compare import compare_reel

        backends = (body or {}).get("backends") or ["claude-cli", "local"]
        if not 1 <= len(backends) <= 2:
            raise HTTPException(400, "pass 1 or 2 backends")
        try:
            return compare_reel(_safe_id(reel_id), backends, base_config=config_path)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/compare/scoreboard")
    def compare_scoreboard() -> dict:
        from ..compare import scoreboard

        return scoreboard(cfg)

    @app.get("/api/compare/status")
    def compare_status() -> dict:
        return dict(_BATCH)

    @app.post("/api/compare/batch")
    def compare_batch(body: dict | None = None) -> dict:
        """Compare N reels in the background. The scoreboard is only meaningful over
        a sample, not the one reel you happened to open."""
        import random

        if _BATCH["running"]:
            raise HTTPException(409, "a batch comparison is already running")
        n = int((body or {}).get("n") or 10)
        backends = (body or {}).get("backends") or ["claude-cli", "local"]
        only_missing = bool((body or {}).get("only_missing", True))

        ids = [p.stem for p in cfg.data_dir.glob("*.json")]
        if only_missing:
            ids = [i for i in ids
                   if set(backends) - set(Reel.load(cfg.data_dir / f"{i}.json").variants or {})]
        random.shuffle(ids)
        ids = ids[:max(1, min(n, 200))]
        if not ids:
            raise HTTPException(409, "nothing left to compare with those backends")

        def _job():
            from ..compare import compare_reel

            for done, rid in enumerate(ids, 1):
                if not _BATCH["running"]:      # cancelled
                    break
                try:
                    compare_reel(rid, backends, base_config=config_path)
                except Exception as ex:
                    _BATCH["errors"].append(f"{rid}: {str(ex)[:150]}")
                _BATCH.update(done=done, current=rid)
            _BATCH.update(running=False, current="")

        _BATCH.update(running=True, done=0, total=len(ids), current="", errors=[],
                      backends=backends)
        threading.Thread(target=_job, daemon=True).start()
        return dict(_BATCH)

    @app.post("/api/compare/cancel")
    def compare_cancel() -> dict:
        _BATCH["running"] = False
        return dict(_BATCH)

    @app.get("/api/discover")
    def discover_list(state: str = "new") -> list[dict]:
        from ..discover import load_candidates

        rows = [c.__dict__ for c in load_candidates(cfg).values()]
        if state != "all":
            rows = [r for r in rows if r["state"] == state]
        rows.sort(key=lambda r: -r["score"])
        return rows

    @app.post("/api/discover/run")
    def discover_run(body: dict | None = None) -> dict:
        """Harvest candidates in the background — one run touches Instagram up to
        `max_requests` times and stops dead on the first 429."""
        if _DISCOVER["running"]:
            raise HTTPException(409, "a discovery run is already going")
        b = body or {}

        def _job():
            from ..discover import discover as run_discover

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

    @app.get("/api/discover/status")
    def discover_status() -> dict:
        return dict(_DISCOVER)

    @app.post("/api/discover/{cand_id}/{action}")
    def discover_action(cand_id: str, action: str) -> dict:
        from ..discover import REJECTED, SNOOZED, accept, set_state

        if action not in {"accept", "reject", "snooze"}:
            raise HTTPException(400, "action must be accept | reject | snooze")
        try:
            if action == "accept":
                return accept(cfg, _safe_id(cand_id))
            state = REJECTED if action == "reject" else SNOOZED
            c = set_state(cfg, _safe_id(cand_id), state)
            return {"id": c.id, "state": c.state}
        except KeyError as e:
            raise HTTPException(404, f"no candidate {cand_id}") from e

    @app.get("/api/knowledge", response_model=Knowledge)
    def knowledge(rebuild: bool = False) -> Knowledge:
        from ..knowledge import load_knowledge

        return load_knowledge(cfg, rebuild=rebuild)

    @app.get("/api/search", response_model=list[SearchHit])
    def search(q: str, k: int = 8) -> list[SearchHit]:
        from ..search import search as do_search

        try:
            hits = do_search(cfg, q, k)
        except FileNotFoundError as e:
            raise HTTPException(409, "no search index — run extraction first") from e
        return [SearchHit(**h) for h in hits]

    @app.post("/api/chat", response_model=Answer)
    def chat(req: ChatRequest) -> Answer:
        from ..chat import answer_question

        try:
            return answer_question(cfg, req.question, k=req.k, history=req.history)
        except FileNotFoundError as e:
            raise HTTPException(409, "no search index — run extraction first") from e

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
