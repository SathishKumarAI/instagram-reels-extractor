"""Text-source adapters (RSS/arXiv/GitHub) + text-vs-vision extraction routing."""
from __future__ import annotations

from dataclasses import dataclass

from reels_scrap.config import Config


@dataclass
class Src:
    name: str
    url: str
    type: str
    limit: int = 5


RSS_XML = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Blog</title>
  <item><title>Post One</title><link>https://ex.com/1</link>
    <description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description>
    <pubDate>Mon, 01 Jul 2026 10:00:00 +0000</pubDate></item>
  <item><title>Post Two</title><link>https://ex.com/2</link>
    <description>Second body</description></item>
</channel></rss>"""


class _Resp:
    def __init__(self, content): self.content, self.status_code = content, 200
    def raise_for_status(self): pass


def test_rss_parses_records(monkeypatch):
    from reels_scrap.ingest import feeds
    monkeypatch.setattr(feeds.requests, "get", lambda *a, **k: _Resp(RSS_XML))
    recs = feeds.fetch_feed_records(Src("blog", "https://ex.com/feed", "rss"))
    assert len(recs) == 2
    r = recs[0]
    assert r.title == "Post One"
    assert r.url == "https://ex.com/1"
    assert "Hello world" in r.caption and "<" not in r.caption   # HTML stripped
    assert r.video_path is None                                   # → routes to text
    assert r.timestamp is not None


def test_ids_are_stable_and_safe():
    from reels_scrap.ingest import feeds
    a = feeds._id_for("rss", "https://ex.com/1")
    b = feeds._id_for("rss", "https://ex.com/1")
    assert a == b and a.replace("_", "").isalnum()


def test_extract_routes_text_record_to_text_summary(monkeypatch, tmp_path):
    """A record with text + no video must hit text_summary, not vision."""
    import reels_scrap.extract as extract_pkg
    from reels_scrap.models import Reel

    called = {"text": 0, "vision": 0}
    import reels_scrap.extract.text_summary as ts
    import reels_scrap.extract.vision as vis
    monkeypatch.setattr(ts, "add_text_summary", lambda r, c: called.__setitem__("text", called["text"] + 1))
    monkeypatch.setattr(vis, "add_summary", lambda r, c: called.__setitem__("vision", called["vision"] + 1))

    cfg = Config.load("config-claude.yaml")
    cfg.extract.transcript = cfg.extract.ocr = False
    cfg.extract.vision = True
    cfg.paths.data_dir = str(tmp_path)

    reel = Reel(id="ar_x", url="https://arxiv.org/abs/x", caption="Some paper text.")
    extract_pkg.extract_all(reel, cfg)
    assert called["text"] == 1 and called["vision"] == 0
