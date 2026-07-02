"""Build local consolidated documents from extracted reels.

Ties three pieces together: the flat `data/` pool of reel JSON records, the
per-collection membership manifests (`collections.py`), and the stdlib HTML
renderer (`render/consolidated.py`). Produces, under `output/collections/`:

    <slug>.html   one self-contained document per collection
    index.html    master index linking them all

Stdlib + local files only — no network, no ML deps — so a doc rebuild is fast and
works even when the extraction environment isn't installed.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .collections import (
    Manifest,
    collections_dir,
    list_manifests,
    save_manifest,
)
from .config import Config
from .render.consolidated import CollectionCard, DocMeta, data_uri, render_doc, render_index

ALL_SLUG = "all-saved"


def _load_record(data_dir: Path, reel_id: str) -> dict | None:
    p = data_dir / f"{reel_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def load_records(data_dir: Path, ids: list[str] | None = None) -> list[dict]:
    """Load reel JSON dicts. With `ids`, keep that order and skip any missing."""
    if ids is not None:
        return [r for r in (_load_record(data_dir, i) for i in ids) if r]
    return [json.loads(p.read_text()) for p in sorted(data_dir.glob("*.json"))]


def build_collection_doc(cfg: Config, m: Manifest) -> tuple[Path, int]:
    """Render one collection's HTML from its manifest. Returns (path, reels_rendered)."""
    reels = load_records(cfg.data_dir, m.reel_ids)
    html = render_doc(
        reels,
        DocMeta(title=m.title, slug=m.slug, source_url=m.url),
        data_dir=cfg.data_dir,
    )
    out = collections_dir(cfg.output_dir) / f"{m.slug}.html"
    out.write_text(html)
    return out, len(reels)


def build_master_index(cfg: Config) -> Path:
    """Render index.html across every manifest (with up to 3 thumbnails each)."""
    cards = []
    for m in list_manifests(cfg.output_dir):
        thumbs = []
        for rec in load_records(cfg.data_dir, m.reel_ids)[:3]:
            uri = data_uri(cfg.data_dir / (rec.get("thumbnail_path") or "")) if rec.get("thumbnail_path") else None
            if uri:
                thumbs.append(uri)
        cards.append(
            CollectionCard(
                slug=m.slug, title=m.title, count=len(m.reel_ids),
                updated=m.updated, source_url=m.url, thumbs=thumbs,
            )
        )
    out = collections_dir(cfg.output_dir) / "index.html"
    out.write_text(render_index(cards))
    return out


def ensure_all_manifest(cfg: Config) -> Manifest | None:
    """Synthesize an 'all-saved' manifest from everything in data/ when no real
    collection manifests exist yet — so `consolidate` is useful on first run."""
    ids = [p.stem for p in sorted(cfg.data_dir.glob("*.json")) if p.stem != "DEMO123"]
    if not ids:
        return None
    m = Manifest(slug=ALL_SLUG, title="All Saved Reels", reel_ids=ids, updated=date.today().isoformat())
    save_manifest(cfg.output_dir, m)
    return m


def rebuild_all(cfg: Config) -> tuple[list[Path], Path]:
    """Re-render every collection doc + the index from existing manifests + data.

    No network, no re-extraction. If there are no manifests, fall back to one
    'all-saved' doc built from the whole data pool.
    """
    manifests = list_manifests(cfg.output_dir)
    if not manifests:
        m = ensure_all_manifest(cfg)
        manifests = [m] if m else []
    docs = [build_collection_doc(cfg, m)[0] for m in manifests]
    index = build_master_index(cfg)
    return docs, index
