"""Manifest inversion: which shelves a reel sits on."""

from __future__ import annotations

from reels_scrap.collections import Manifest, collections_dir, reels_by_collection, save_manifest


def test_reels_by_collection(tmp_path):
    out = tmp_path / "output"
    save_manifest(out, Manifest(slug="ai", title="Ai", reel_ids=["AAA", "BBB"]))
    save_manifest(out, Manifest(slug="books", title="Books", reel_ids=["BBB"]))
    # a corrupt manifest must not take the whole mapping down
    (collections_dir(out) / "broken.json").write_text("{not json", encoding="utf-8")

    by_reel = reels_by_collection(out)
    assert by_reel["AAA"] == ["ai"]
    assert by_reel["BBB"] == ["ai", "books"]   # sorted, so the UI order is stable
    assert "CCC" not in by_reel


def test_reels_by_collection_dedupes(tmp_path):
    out = tmp_path / "output"
    save_manifest(out, Manifest(slug="ai", title="Ai", reel_ids=["AAA", "AAA"]))
    assert reels_by_collection(out)["AAA"] == ["ai"]
