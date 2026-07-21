"""Incremental source poller: dedup diff, dead-letter exclusion, run state.

No network, no real pipeline — enumerate + run_pipeline + doc build are stubbed so
the test exercises the *data-engineering logic*: what counts as new, what gets
deduped, what lands in the dead-letter set, and how state carries forward.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reels_scrap import sources
from reels_scrap.config import Config
from reels_scrap.sources import Source, add_source, load_sources, poll_all


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    (tmp_path / "config.yaml").write_text(
        f"paths:\n  data_dir: {tmp_path/'data'}\n  output_dir: {tmp_path/'out'}\n"
    )
    return Config.load(tmp_path / "config.yaml")


def _url(rid: str) -> str:
    return f"https://www.instagram.com/reel/{rid}/"


def _wire(monkeypatch, cfg, enumerate_ids, lands):
    """Stub enumerate → given ids; stub pipeline → only `lands` ids hit the pool."""
    monkeypatch.setattr(sources, "enumerate_source",
                        lambda src, browser="chrome": [_url(i) for i in enumerate_ids])

    def fake_pipeline(c, cfg_path, progress=None):
        urls = Path(c.source.urls_file).read_text().split()
        for u in urls:
            rid = u.rstrip("/").rsplit("/", 1)[-1]
            if rid in lands:
                (c.data_dir / f"{rid}.json").write_text(json.dumps({"id": rid, "url": u}))
        return [], None

    import reels_scrap.pipeline as pipe
    monkeypatch.setattr(pipe, "run_pipeline", fake_pipeline)
    # doc/index build is orthogonal here — no-op it
    import reels_scrap.docs as docs
    monkeypatch.setattr(docs, "build_collection_doc", lambda c, m: (c.output_dir / f"{m.slug}.html", 0))
    monkeypatch.setattr(docs, "build_master_index", lambda c: c.output_dir / "index.html")


def test_add_source_is_idempotent(tmp_path):
    reg = tmp_path / "sources.json"
    url = "https://www.instagram.com/u/saved/phd-opportunities/18354529171213909/"
    add_source(url, path=reg)
    add_source(url, path=reg)  # same url again
    rows = load_sources(reg)
    assert len(rows) == 1
    assert rows[0].name == "phd-opportunities"  # slug derived from url
    assert rows[0].type == "collection"


def test_same_named_collections_disambiguated(tmp_path):
    reg = tmp_path / "sources.json"
    a = add_source("https://www.instagram.com/u/saved/ai/18050573570734007/", path=reg)
    b = add_source("https://www.instagram.com/u/saved/ai/17949637341189585/", path=reg)
    assert a.name == "ai" and b.name == "ai-2"      # unique names
    assert a.slug != b.slug                          # → distinct docs/manifests
    rows = load_sources(reg)
    assert len(rows) == 2
    # re-adding the first URL is still idempotent (no third entry)
    assert add_source("https://www.instagram.com/u/saved/ai/18050573570734007/", path=reg).name == "ai"
    assert len(load_sources(reg)) == 2


def test_dedup_and_dead_letter(cfg, tmp_path, monkeypatch):
    reg = tmp_path / "sources.json"
    add_source("https://www.instagram.com/u/saved/phd/18354529171213909/", path=reg)

    # AAA already downloaded; source currently has AAA, BBB, CCC
    (cfg.data_dir / "AAA.json").write_text(json.dumps({"id": "AAA"}))
    # of the two new (BBB, CCC), only BBB downloads — CCC is a photo post → fails
    _wire(monkeypatch, cfg, enumerate_ids=["AAA", "BBB", "CCC"], lands={"BBB"})

    r1 = poll_all(cfg, "config.yaml", sources_file=reg, run_date="2026-07-02")[0]
    assert r1.current == 3
    assert r1.new == 2            # BBB + CCC (AAA deduped by pool)
    assert r1.skipped == 1        # AAA
    assert r1.ingested == 1       # only BBB landed
    assert r1.failed_ids == ["CCC"]  # CCC dead-lettered

    # state persisted the dead-letter set
    state = json.loads((cfg.output_dir / "sources_state.json").read_text())
    assert set(state["phd"]["failed_ids"]) == {"CCC"}

    # second run: nothing changed upstream → CCC is excluded, truly idempotent
    r2 = poll_all(cfg, "config.yaml", sources_file=reg, run_date="2026-07-03")[0]
    assert r2.new == 0
    assert r2.skipped == 3        # AAA+BBB (pool) + CCC (dead)
    assert r2.ingested == 0


def test_retry_failed_reattempts_dead(cfg, tmp_path, monkeypatch):
    reg = tmp_path / "sources.json"
    add_source("https://www.instagram.com/u/saved/phd/18354529171213909/", path=reg)
    _wire(monkeypatch, cfg, enumerate_ids=["CCC"], lands=set())

    poll_all(cfg, "config.yaml", sources_file=reg, run_date="2026-07-02")  # CCC → dead
    # now CCC becomes downloadable and we retry
    _wire(monkeypatch, cfg, enumerate_ids=["CCC"], lands={"CCC"})
    r = poll_all(cfg, "config.yaml", sources_file=reg, run_date="2026-07-03",
                 retry_failed=True)[0]
    assert r.new == 1 and r.ingested == 1
    state = json.loads((cfg.output_dir / "sources_state.json").read_text())
    assert state["phd"]["failed_ids"] == []  # cleared
