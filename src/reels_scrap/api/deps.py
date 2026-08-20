"""The few things every route group needs: id guard, reel loading, row shaping.

Owns no routes and no state. If a helper is used by exactly one route module it
belongs in that module, not here — this file stays short on purpose.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

from ..config import Config
from ..models import Reel
from .schemas import ReelSummary, SearchHit

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def safe_id(reel_id: str) -> str:
    """Guard against path traversal — reel ids are shortcodes only."""
    if not _ID_RE.match(reel_id):
        raise HTTPException(400, "invalid reel id")
    return reel_id


def load_reels(cfg: Config) -> list[Reel]:
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


def reel_or_404(cfg: Config, reel_id: str) -> Reel:
    p = cfg.data_dir / f"{safe_id(reel_id)}.json"
    if not p.exists():
        raise HTTPException(404, f"no reel {reel_id}")
    return Reel.load(p)


def hits(cfg: Config, rows: list[dict]) -> list[SearchHit]:
    """Search rows + the collections each hit's reel sits on.

    A hit answers "where did you read this"; the shelf is half that answer, and
    the grid, the reader and the table all already say it.
    """
    from ..collections import reels_by_collection

    by_reel = reels_by_collection(cfg.output_dir)
    return [SearchHit(**h, collections=by_reel.get(h["reel_id"], [])) for h in rows]


def summary(r: Reel) -> ReelSummary:
    return ReelSummary(
        id=r.id, title=r.title or r.id, author=r.author, genre=r.genre, tags=r.tags, url=r.url,
        thumbnail_path=r.thumbnail_path, likes=r.likes, views=r.views,
        comments=r.comments, duration=r.duration, timestamp=r.timestamp, has_pdf=bool(r.pdf_path),
        tokens_in=r.tokens.get("input", 0), tokens_out=r.tokens.get("output", 0),
        backend=str(r.tokens.get("backend", "") or ""),
        model=str(r.tokens.get("model", "") or ""),
    )
