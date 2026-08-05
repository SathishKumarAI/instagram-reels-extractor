"""Collection membership manifests.

`data/` is a flat pool of reels shared across collections (media is deduped — a
reel saved in two collections is downloaded once). The flat folder can't tell you
which reel belongs to which named collection, so membership is recorded here: one
small JSON manifest per collection under `output/collections/`.

    front-end.json  ->  {slug, title, id, url, reel_ids, updated}

The renderer reads a manifest's `reel_ids`, loads those records from `data/`, and
builds `front-end.html`. `list_manifests()` powers the master index.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

COLLECTIONS_DIRNAME = "collections"


def slugify(name: str) -> str:
    """URL/collection name -> filesystem-safe slug (e.g. 'Front End!' -> 'front-end')."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "collection"


def parse_collection_url(url_or_id: str) -> tuple[str, str]:
    """Return (slug, numeric_id) from a saved-collection URL or bare id.

    .../saved/front-end/10000000000000004/  ->  ("front-end", "10000000000000004")
    A bare numeric id yields (that id, that id) — no readable name available.
    """
    if url_or_id.isdigit():
        return url_or_id, url_or_id
    m = re.search(r"/saved/([^/]+)/(\d+)", url_or_id)
    if not m:
        raise ValueError(f"could not parse a collection name/id from: {url_or_id!r}")
    return slugify(m.group(1)), m.group(2)


@dataclass
class Manifest:
    slug: str
    title: str
    id: str = ""
    url: str = ""
    reel_ids: list[str] = field(default_factory=list)
    updated: str = ""  # ISO date; caller stamps it (scripts can't call Date.now)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_path(cls, path: Path) -> Manifest:
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def collections_dir(output_dir: Path) -> Path:
    p = Path(output_dir) / COLLECTIONS_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def manifest_path(output_dir: Path, slug: str) -> Path:
    return collections_dir(output_dir) / f"{slug}.json"


def save_manifest(output_dir: Path, m: Manifest) -> Path:
    p = manifest_path(output_dir, m.slug)
    p.write_text(m.to_json(), encoding="utf-8")
    return p


def load_manifest(output_dir: Path, slug: str) -> Manifest | None:
    p = manifest_path(output_dir, slug)
    return Manifest.from_path(p) if p.exists() else None


def list_manifests(output_dir: Path) -> list[Manifest]:
    """All collection manifests, for building the index."""
    out = []
    for p in sorted(collections_dir(output_dir).glob("*.json")):
        try:
            out.append(Manifest.from_path(p))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def reels_by_collection(output_dir: Path) -> dict[str, list[str]]:
    """`reel_id -> [collection slug, …]`, inverted from the manifests.

    A reel's collections are never stored on its record — the manifest is the
    only place membership lives, so re-filing a reel needs no record rewrite.
    Slugs come back sorted so the UI order does not depend on file order.
    """
    by_reel: dict[str, list[str]] = {}
    for m in list_manifests(output_dir):
        for rid in m.reel_ids:
            by_reel.setdefault(rid, []).append(m.slug)
    return {rid: sorted(set(slugs)) for rid, slugs in by_reel.items()}
