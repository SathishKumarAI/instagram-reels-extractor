"""User annotations + saved views — the layer that turns the archive into a workflow.

Kept SEPARATE from the reel records in `data/` (which are extracted facts): user
state is subjective and shouldn't pollute or get overwritten by re-extraction.
Two small JSON stores under output/:

    annotations.json  ->  {reel_id: {starred, read, archived, note}}
    views.json        ->  [{name, filters:{genre,account,tag,sort,status}}]
"""
from __future__ import annotations

import json
from pathlib import Path

ANNOTATIONS = "annotations.json"
VIEWS = "views.json"

_FLAGS = ("starred", "read", "archived")


def _path(output_dir: Path, name: str) -> Path:
    return Path(output_dir) / name


def load_annotations(output_dir: Path) -> dict:
    p = _path(output_dir, ANNOTATIONS)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def annotate(output_dir: Path, reel_id: str, patch: dict) -> dict:
    """Merge a patch ({starred?/read?/archived?/note?}) into a reel's annotation."""
    data = load_annotations(output_dir)
    cur = data.get(reel_id, {})
    for k in _FLAGS:
        if k in patch:
            cur[k] = bool(patch[k])
    if "note" in patch:
        cur["note"] = str(patch["note"])[:2000]
    data[reel_id] = cur
    _path(output_dir, ANNOTATIONS).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return cur


def load_views(output_dir: Path) -> list[dict]:
    p = _path(output_dir, VIEWS)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_view(output_dir: Path, name: str, filters: dict) -> list[dict]:
    """Add or replace a saved view by name. Returns the full list."""
    views = [v for v in load_views(output_dir) if v.get("name") != name]
    views.append({"name": name, "filters": filters})
    _path(output_dir, VIEWS).write_text(json.dumps(views, indent=2) + "\n", encoding="utf-8")
    return views


def delete_view(output_dir: Path, name: str) -> list[dict]:
    views = [v for v in load_views(output_dir) if v.get("name") != name]
    _path(output_dir, VIEWS).write_text(json.dumps(views, indent=2) + "\n", encoding="utf-8")
    return views
