"""The corpus as the UI reads it: reels, annotations, saved views, tags, media.

Read-mostly. Anything that starts a job lives in `sync.py`, `compare.py` or
`discover.py`; anything that produces a file to download lives in `exports.py`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...config import Config
from ...models import Reel
from ..deps import hits, load_reels, reel_or_404, safe_id, summary
from ..schemas import ReelSummary, SearchHit


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/reels", response_model=list[ReelSummary])
    def list_reels() -> list[ReelSummary]:
        from ...collections import reels_by_collection
        from ...userstate import load_annotations

        ann = load_annotations(cfg.output_dir)
        by_reel = reels_by_collection(cfg.output_dir)
        out = []
        for r in load_reels(cfg):
            s = summary(r)
            s.collections = by_reel.get(r.id, [])
            a = ann.get(r.id, {})
            s.starred, s.read, s.archived = (
                bool(a.get("starred")), bool(a.get("read")), bool(a.get("archived")),
            )
            out.append(s)
        return out

    @router.get("/api/annotations")
    def get_annotations() -> dict:
        from ...userstate import load_annotations

        return load_annotations(cfg.output_dir)

    @router.post("/api/reels/{reel_id}/annotate")
    def annotate_reel(reel_id: str, body: dict) -> dict:
        from ...userstate import annotate

        return annotate(cfg.output_dir, safe_id(reel_id), body or {})

    @router.get("/api/views")
    def get_views() -> list[dict]:
        from ...userstate import load_views

        return load_views(cfg.output_dir)

    @router.post("/api/views")
    def post_view(body: dict) -> list[dict]:
        from ...userstate import save_view

        name = (body or {}).get("name", "").strip()
        if not name:
            raise HTTPException(400, "view name required")
        return save_view(cfg.output_dir, name, (body or {}).get("filters", {}))

    @router.post("/api/views/{name}/delete")
    def remove_view(name: str) -> list[dict]:
        from ...userstate import delete_view

        return delete_view(cfg.output_dir, name)

    @router.get("/api/tags")
    def list_tags() -> list[dict]:
        """Every tag with the collections it appears in.

        A tag alone says what a reel is about; the collection says which shelf of
        yours it belongs on. The UI colours chips by collection, so it needs both.
        """
        from ...collections import reels_by_collection

        by_reel = reels_by_collection(cfg.output_dir)

        tags: dict[str, dict] = {}
        for r in load_reels(cfg):
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

    @router.post("/api/tags/rename")
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

    @router.get("/api/reels/{reel_id}")
    def get_reel(reel_id: str) -> dict:
        from ...collections import reels_by_collection
        from ...userstate import load_annotations

        d = reel_or_404(cfg, reel_id).model_dump(mode="json")
        # membership lives in the manifests, not on the record — the reader shows
        # the shelf a reel came from, so the detail response needs it too
        d["collections"] = reels_by_collection(cfg.output_dir).get(reel_id, [])
        d["annotation"] = load_annotations(cfg.output_dir).get(reel_id, {})
        return d

    @router.get("/api/reels/{reel_id}/similar")
    def similar(reel_id: str, k: int = 6) -> list[SearchHit]:
        """'More like this' — semantic neighbours via the existing embedding index."""
        r = reel_or_404(cfg, reel_id)
        query = " ".join(filter(None, [r.title, r.summary, " ".join(r.tags)]))[:500]
        from ...search import search as do_search

        try:
            rows = [h for h in do_search(cfg, query, k + 3) if h["reel_id"] != reel_id]
        except FileNotFoundError:
            return []
        return hits(cfg, rows[:k])

    @router.get("/api/media/{reel_id}/{kind}")
    def media(reel_id: str, kind: str) -> FileResponse:
        if kind not in {"video", "thumbnail", "pdf"}:
            raise HTTPException(404, f"no {kind}")
        r = reel_or_404(cfg, reel_id)
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

    return router
