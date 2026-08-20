"""Incremental index: only reels newer than the index get re-embedded.

A full rebuild is ~3.5 min at 673 reels and used to run on every sync.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from reels_scrap import search as S
from reels_scrap.config import Config
from reels_scrap.models import Fact, Reel


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


def _reel(cfg, rid, summary, facts=1):
    r = Reel(id=rid, url=f"https://ig/{rid}", title=rid, summary=summary,
             facts=[Fact(text=f"{rid} fact {i}") for i in range(facts)])
    r.save(cfg.data_dir)
    return r


@pytest.fixture
def fake_embed(monkeypatch):
    """Deterministic stand-in for fastembed; counts how many texts get embedded."""
    import numpy as np

    calls = {"texts": 0}

    def _embed(texts):
        calls["texts"] += len(texts)
        return np.array([[float(len(t)), 1.0] for t in texts], dtype="float32")

    monkeypatch.setattr(S, "_embed", _embed)
    return calls


def test_second_run_reuses_untouched_reels(cfg, fake_embed):
    _reel(cfg, "AAA", "first")
    _reel(cfg, "BBB", "second")
    assert S.build_index(cfg) == 4          # 2 reels × (1 doc + 1 fact)
    first_pass = fake_embed["texts"]
    assert first_pass == 4

    # nothing changed → nothing re-embedded, index still complete
    assert S.build_index(cfg) == 4
    assert fake_embed["texts"] == first_pass


def test_only_the_changed_reel_is_re_embedded(cfg, fake_embed):
    _reel(cfg, "AAA", "first")
    _reel(cfg, "BBB", "second")
    S.build_index(cfg)
    before = fake_embed["texts"]

    time.sleep(0.01)
    p = cfg.data_dir / "BBB.json"
    _reel(cfg, "BBB", "second, edited", facts=2)
    os.utime(p, None)

    assert S.build_index(cfg) == 5          # AAA 2 rows + BBB 3 rows
    assert fake_embed["texts"] - before == 3   # only BBB's rows

    meta = json.loads(S.meta_path(cfg).read_text(encoding="utf-8"))
    assert [m["reel_id"] for m in meta] == ["AAA", "AAA", "BBB", "BBB", "BBB"]


def test_full_forces_everything(cfg, fake_embed):
    _reel(cfg, "AAA", "first")
    S.build_index(cfg)
    before = fake_embed["texts"]
    S.build_index(cfg, full=True)
    assert fake_embed["texts"] - before == 2


def test_variant_writes_do_not_force_a_re_embed(cfg, fake_embed):
    """Compare-tab variants and annotations rewrite the json but not the text.

    On an mtime key this was 665 pointless re-embeds after a variant backfill.
    """
    import os
    import time

    r = _reel(cfg, "AAA", "first")
    S.build_index(cfg)
    before = fake_embed["texts"]

    time.sleep(0.01)
    r.variants = {"local": {"summary": "a different summary", "facts": []}}
    r.save(cfg.data_dir)
    os.utime(cfg.data_dir / "AAA.json", None)      # definitely newer than the index

    S.build_index(cfg)
    assert fake_embed["texts"] == before           # nothing re-embedded


def test_changed_summary_still_re_embeds(cfg, fake_embed):
    _reel(cfg, "AAA", "first")
    S.build_index(cfg)
    before = fake_embed["texts"]
    _reel(cfg, "AAA", "genuinely different summary")
    S.build_index(cfg)
    assert fake_embed["texts"] > before
