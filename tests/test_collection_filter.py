"""Enumerate must drop posts with no video — they dead-letter otherwise."""

from __future__ import annotations

from reels_scrap.ingest.collection import _shortcode


def _item(media_type, code="ABC", carousel=None):
    m = {"media_type": media_type, "code": code}
    if carousel is not None:
        m["carousel_media"] = carousel
    return {"media": m}


def test_video_kept():
    assert _shortcode(_item(2)) == "ABC"


def test_photo_dropped():
    assert _shortcode(_item(1)) is None


def test_all_photo_carousel_dropped():
    assert _shortcode(_item(8, carousel=[{"media_type": 1}, {"media_type": 1}])) is None


def test_carousel_with_a_video_kept():
    assert _shortcode(_item(8, carousel=[{"media_type": 1}, {"media_type": 2}])) == "ABC"


def test_unknown_media_type_kept():
    """Missing media_type (older payloads) must not silently drop everything."""
    assert _shortcode({"media": {"code": "ABC"}}) == "ABC"
