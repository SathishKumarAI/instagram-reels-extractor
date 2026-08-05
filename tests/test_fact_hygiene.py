"""Subtitle fragments must never become facts.

Reproducer: sampling 16 frames of a 62s reel yielded "years now and", "clutch",
"aspiring", "you'll ever" — a moving caption sliced at arbitrary points.
"""

from __future__ import annotations

from reels_scrap.extract.vision import _apply, _dedupe_facts, _is_fragment
from reels_scrap.models import Fact, Reel


def test_real_fragments_are_rejected():
    for bad in ["years now and", "clutch", "aspiring", "you'll ever", "recommend",
                "so here are", "the only way you"]:
        assert _is_fragment(bad), bad


def test_real_claims_survive():
    for good in [
        "The Microsoft Web-Dev-For-Beginners curriculum runs 12 weeks over 24 lessons",
        "no. 2 WEBDEV FOR BEGINNERS",
        "Project Based Learning is the first recommended repository",
        "2026 pricing starts at $20 per month",
    ]:
        assert not _is_fragment(good), good


def test_same_claim_from_several_frames_collapses():
    facts = [
        Fact(text="WebDev for Beginners is a 12 week Microsoft curriculum"),
        Fact(text="WebDev for Beginners is a twelve week curriculum from Microsoft"),
        Fact(text="Coding Interview University covers algorithms and data structures"),
    ]
    assert len(_dedupe_facts(facts)) == 2


def test_apply_populates_the_new_fields():
    r = Reel(id="X", url="https://ig/X")
    _apply(r, {
        "genre": "educational",
        "summary": "A four sentence summary that actually says something.",
        "key_points": ["build projects", "  ", "read the curriculum"],
        "on_screen_text": ["TOP 5 GITHUB REPOSITORIES", "no. 1 PROJECT BASED LEARNING"],
        "tags": ["GitHub", "career"],
        "structured": {"topic": "github repos"},
        "facts": [
            {"text": "years now and", "frame": 1, "timestamp": 8},
            {"text": "The curriculum from Microsoft runs for 12 weeks", "frame": 2, "timestamp": 16},
        ],
    })
    assert r.key_points == ["build projects", "read the curriculum"]
    assert len(r.on_screen_text) == 2
    assert [f.text for f in r.facts] == ["The curriculum from Microsoft runs for 12 weeks"]


def test_subtitle_lines_are_stripped_from_on_screen_text():
    """With the transcript in hand, "is this a subtitle?" is decidable."""
    from reels_scrap.extract.vision import _strip_subtitles

    transcript = ("I've been coding for 8 years now, and one thing I wish I knew "
                  "earlier was just how clutch GitHub can be for getting you hired.")
    lines = [
        "top 5 GITHUB REPOSITORIES",       # overlay — keep
        "years now and",                   # subtitle — drop
        "no. 1 PROJECT BASED LEARNING",    # short overlay — keep
        "how clutch GitHub can be",        # subtitle — drop
    ]
    kept = _strip_subtitles(lines, transcript)
    assert kept == ["top 5 GITHUB REPOSITORIES", "no. 1 PROJECT BASED LEARNING"]


def test_without_a_transcript_nothing_is_stripped():
    from reels_scrap.extract.vision import _strip_subtitles

    lines = ["anything at all", "second line"]
    assert _strip_subtitles(lines, "") == lines
