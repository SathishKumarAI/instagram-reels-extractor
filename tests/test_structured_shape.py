"""Local models nest `structured` under the genre; Claude returns it flat.

Left alone, a local record reads as 1 field when it carries 4 — which made the
Compare scoreboard show a quality gap that was really a formatting difference.
"""

from __future__ import annotations

from reels_scrap.extract.vision import _unwrap_structured

NESTED = {"educational": {"topic": "git", "key_concepts": ["a", "b"], "resources": []}}
FLAT = {"topic": "git", "key_concepts": ["a", "b"], "resources": []}


def test_unwraps_genre_wrapper():
    assert _unwrap_structured(NESTED, "educational") == FLAT


def test_unwraps_even_when_the_genre_disagrees():
    # the model labelled the reel `tutorial` but wrapped under `educational`
    assert _unwrap_structured(NESTED, "tutorial") == FLAT


def test_flat_is_left_alone():
    assert _unwrap_structured(FLAT, "educational") == FLAT


def test_single_real_field_is_not_unwrapped():
    """A genuine one-field payload must survive — the key is not a genre."""
    d = {"tools": ["ffmpeg"]}
    assert _unwrap_structured(d, "tutorial") == d


def test_non_dict_becomes_empty():
    assert _unwrap_structured(["nope"], "tutorial") == {}
    assert _unwrap_structured(None, "") == {}
