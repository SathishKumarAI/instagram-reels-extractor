"""Local consolidated-document build: manifest parsing + renderer + doc/index output.

Pure stdlib path (no network, no ML deps): synthesize a couple of reel records in a
temp data dir, build a collection doc + index, assert the important structure lands.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reels_scrap.collections import Manifest, list_manifests, parse_collection_url, slugify
from reels_scrap.config import Config
from reels_scrap import docs
from reels_scrap.render.consolidated import DocMeta, render_doc, render_index, CollectionCard


def _reel(rid: str, genre: str, **extra) -> dict:
    d = {
        "id": rid,
        "url": f"https://www.instagram.com/reel/{rid}/",
        "author": f"creator_{rid}",
        "title": f"Title {rid}",
        "genre": genre,
        "summary": f"Summary for {rid}.",
        "likes": 100,
        "comments": 5,
        "duration": 30,
        "structured": {"name": "Tool", "link": "github.com/x/y", "claims": ["a", "b"]},
        "facts": [{"timestamp": 12, "text": "a grounded fact"}],
    }
    d.update(extra)
    return d


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    (tmp_path / "config.yaml").write_text(
        f"paths:\n  data_dir: {tmp_path/'data'}\n  output_dir: {tmp_path/'out'}\n"
    )
    c = Config.load(tmp_path / "config.yaml")
    for r in (_reel("AAA", "product"), _reel("BBB", "tutorial"), _reel("CCC", "product")):
        (c.data_dir / f"{r['id']}.json").write_text(json.dumps(r))
    return c


def test_parse_collection_url():
    assert parse_collection_url(
        "https://www.instagram.com/u/saved/front-end/18095255279194694/"
    ) == ("front-end", "18095255279194694")
    assert parse_collection_url("18095255279194694") == ("18095255279194694", "18095255279194694")
    with pytest.raises(ValueError):
        parse_collection_url("https://example.com/not-a-collection")


def test_slugify():
    assert slugify("Front End!!") == "front-end"
    assert slugify("  Web / Dev  ") == "web-dev"
    assert slugify("") == "collection"


def test_render_doc_structure():
    reels = [_reel("AAA", "product"), _reel("BBB", "tutorial")]
    html = render_doc(reels, DocMeta(title="Web Dev", slug="web-dev", source_url="https://ig/x"))
    assert "Web Dev — 2 Saved Reels" in html
    assert html.count("<article") == 2
    assert "Products &amp; Tools" in html and "Tutorials &amp; Walkthroughs" in html
    assert "Watch reel on Instagram" in html
    assert "a grounded fact" in html and "0:12" in html  # provenance timestamp formatting
    assert "index.html" in html  # back-link


def test_render_index_lists_collections():
    cards = [CollectionCard(slug="front-end", title="Front End", count=22, updated="2026-07-02")]
    html = render_index(cards)
    assert "front-end.html" in html and "Front End" in html and "22 reels" in html


def test_build_collection_doc_and_index(cfg: Config):
    m = Manifest(slug="front-end", title="Front End", url="https://ig/x",
                 reel_ids=["AAA", "BBB", "CCC"], updated="2026-07-02")
    from reels_scrap.collections import save_manifest

    save_manifest(cfg.output_dir, m)
    doc, n = docs.build_collection_doc(cfg, m)
    assert n == 3 and doc.exists()
    assert doc.read_text().count("<article") == 3

    index = docs.build_master_index(cfg)
    assert index.exists()
    assert "front-end.html" in index.read_text()


def test_build_collection_doc_skips_missing_reels(cfg: Config):
    m = Manifest(slug="c", title="C", reel_ids=["AAA", "GHOST", "BBB"])
    _, n = docs.build_collection_doc(cfg, m)
    assert n == 2  # GHOST has no record on disk -> silently skipped


def test_rebuild_all_falls_back_to_all_saved(cfg: Config):
    # no manifests yet -> synthesize an 'all-saved' doc from the data pool
    built, index = docs.rebuild_all(cfg)
    assert len(built) == 1
    assert any(m.slug == docs.ALL_SLUG for m in list_manifests(cfg.output_dir))
    assert index.exists()
