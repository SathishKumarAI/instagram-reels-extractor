"""A named collection is now the saved feed filtered on `saved_collection_ids`.

Catches the two ways that can break: returning a foreign collection's posts, and
paging the same feed once per collection (Instagram 429s at that rate).
"""

from __future__ import annotations

import reels_scrap.ingest.collection as C


def _item(code, collections, media_type=2):
    return {"media": {"code": code, "media_type": media_type,
                      "saved_collection_ids": collections,
                      "user": {"username": "someone"}}}


FEED = [
    _item("AAA", [111, 222]),
    _item("BBB", [222]),
    _item("CCC", []),
    _item("DDD", [111]),
    _item("PIC", [111], media_type=1),   # photo — nothing to download
]


def _stub(monkeypatch, tmp_path, calls):
    monkeypatch.setattr(C, "_SAVED_SCAN", {})
    monkeypatch.setattr(C, "record_handles", lambda *a, **k: tmp_path / "handles.json")

    def fake(feed_url, label, browser, limit, sleep_between):
        calls.append(feed_url)
        return FEED[:limit]

    monkeypatch.setattr(C, "_fetch_items", fake)


def test_only_that_collections_reels(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub(monkeypatch, tmp_path, calls)
    urls = C.fetch_collection("https://www.instagram.com/u/saved/name/111/", browser="x")
    assert urls == ["https://www.instagram.com/reel/AAA/",
                    "https://www.instagram.com/reel/DDD/"]      # not BBB, not the photo


def test_one_feed_scan_serves_every_collection(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub(monkeypatch, tmp_path, calls)
    C.fetch_collection("111", browser="x")
    C.fetch_collection("222", browser="x")
    C.fetch_saved_feed(browser="x")
    assert len(calls) == 1 and calls[0] == C.SAVED_FEED_URL


def test_saved_feed_still_returns_everything_downloadable(monkeypatch, tmp_path):
    calls: list[str] = []
    _stub(monkeypatch, tmp_path, calls)
    assert C.fetch_saved_feed(browser="x") == [
        "https://www.instagram.com/reel/AAA/",
        "https://www.instagram.com/reel/BBB/",
        "https://www.instagram.com/reel/CCC/",
        "https://www.instagram.com/reel/DDD/",
    ]
