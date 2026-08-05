"""Discovery: the request budget, the 429 kill-switch, and candidate bookkeeping.

No network — the budget and the store are the parts that can hurt you.
"""

from __future__ import annotations

import pytest

from reels_scrap import discover as D
from reels_scrap.config import Config
from reels_scrap.sources import RateLimited


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "config.yaml").write_text(
        f"paths:\n  data_dir: {tmp_path/'data'}\n  output_dir: {tmp_path/'out'}\n",
        encoding="utf-8",
    )
    c = Config.load(tmp_path / "config.yaml")
    c.data_dir.mkdir(parents=True, exist_ok=True)
    c.output_dir.mkdir(parents=True, exist_ok=True)
    return c


def test_budget_caps_total_requests():
    b = D.Budget(max_requests=3, min_interval=0)
    for _ in range(3):
        b.take()
    with pytest.raises(RateLimited):
        b.take()
    assert b.used == 3


def test_budget_enforces_a_gap_between_calls(monkeypatch):
    slept = []
    monkeypatch.setattr(D.time, "sleep", lambda s: slept.append(s))
    now = [1000.0]
    monkeypatch.setattr(D.time, "time", lambda: now[0])

    b = D.Budget(max_requests=5, min_interval=3.0)
    b.take()
    now[0] += 0.5          # caller comes back immediately
    b.take()
    assert slept and 2.4 < slept[0] <= 3.0


def test_kill_switch_stops_every_later_request():
    b = D.Budget(max_requests=100, min_interval=0)
    b.take()
    b.kill("429 on author feed")
    with pytest.raises(RateLimited, match="429"):
        b.take()


def test_candidates_round_trip(cfg):
    rows = {"AAA": D.Candidate(id="AAA", url="https://ig/AAA", caption="hi", score=0.9)}
    D.save_candidates(cfg, rows)
    back = D.load_candidates(cfg)
    assert back["AAA"].score == 0.9 and back["AAA"].state == D.NEW


def test_state_transitions_persist(cfg):
    D.save_candidates(cfg, {"AAA": D.Candidate(id="AAA", url="https://ig/AAA")})
    D.set_state(cfg, "AAA", D.REJECTED)
    assert D.load_candidates(cfg)["AAA"].state == D.REJECTED
    with pytest.raises(KeyError):
        D.set_state(cfg, "NOPE", D.REJECTED)


def test_only_videos_become_candidates():
    items = [
        {"media": {"media_type": 2, "code": "VID", "user": {"username": "a"}}},
        {"media": {"media_type": 1, "code": "PHOTO", "user": {"username": "a"}}},
        {"media": {"media_type": 8, "code": "CAROUSEL", "user": {"username": "a"}}},
    ]
    out = D._items_to_candidates(items, "author:a", "2026-08-04")
    assert [c.id for c in out] == ["VID"]


def test_top_authors_needs_repeat_saves(cfg):
    from reels_scrap.models import Reel

    for i in range(3):
        Reel(id=f"A{i}", url=f"https://ig/A{i}", author="Repeat Creator",
             author_handle="repeat_creator").save(cfg.data_dir)
    Reel(id="B0", url="https://ig/B0", author="One Off",
         author_handle="one_off").save(cfg.data_dir)

    assert D.top_authors(cfg, min_saves=2) == [("repeat_creator", 3)]


def test_display_names_are_never_used_as_handles(cfg):
    """A display name sent to IG's profile endpoint is a wasted request."""
    from reels_scrap.models import Reel

    for i in range(4):
        Reel(id=f"C{i}", url=f"https://ig/C{i}",
             author="Alan Salgado Espino - Knee Specialist").save(cfg.data_dir)

    assert D.top_authors(cfg, min_saves=2) == []


def test_top_tags_uses_caption_hashtags_not_our_slugs(cfg):
    """Our tags are slugs (`open-source`); IG hashtags have no hyphens."""
    from reels_scrap.models import Reel

    for i in range(3):
        Reel(id=f"H{i}", url=f"https://ig/H{i}",
             tags=["open-source", "claude-code"],
             hashtags=["#opensource", "#ClaudeCode", "#fyp"]).save(cfg.data_dir)

    tags = D.top_tags(cfg, limit=5)
    assert "opensource" in tags and "claudecode" in tags   # lowercased, from captions
    assert "open-source" not in tags                       # the slug never goes to IG
    assert "fyp" not in tags                               # reach spam, not a subject
