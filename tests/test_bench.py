"""Bench: fixed sample, resumable runs, failures recorded rather than averaged away."""

from __future__ import annotations

import json

import pytest

from reels_scrap import bench, benchreport
from reels_scrap.models import Fact, Reel


@pytest.fixture()
def corpus(cfg, tmp_path):
    """20 reels across three genres, each with a video file so frames are possible."""
    for i in range(20):
        genre = ("educational", "entertainment", "news")[i % 3 if i < 18 else 2]
        vid = tmp_path / "data" / f"R{i:02d}.mp4"
        vid.write_bytes(b"x")
        Reel(id=f"R{i:02d}", url=f"https://insta/reel/R{i:02d}/", title=f"reel {i}",
             genre=genre, video_path=vid.name,
             facts=[Fact(text=f"fact {i}", timestamp=1.0)]).save(tmp_path / "data")
    return cfg


def test_sample_is_deterministic_and_stratified(corpus):
    a = bench.build_sample(corpus, n=9, seed=0)
    b = bench.build_sample(corpus, n=9, seed=0)
    assert a.reel_ids == b.reel_ids
    assert bench.build_sample(corpus, n=9, seed=1).reel_ids != a.reel_ids
    assert len(a.reel_ids) == 9
    assert sum(a.strata.values()) == 9
    assert len(a.strata) >= 3           # every genre represented, not just the big one


def test_sample_round_trips(corpus):
    s = bench.build_sample(corpus, n=6, seed=0)
    bench.save_sample(corpus, s)
    assert bench.load_sample(corpus).reel_ids == s.reel_ids


def test_run_stores_variants_skips_stored_and_records_failures(corpus, monkeypatch, tmp_path):
    bench.save_sample(corpus, bench.build_sample(corpus, n=6, seed=0))
    monkeypatch.setattr(bench, "_release_gpu", lambda cfg: None)
    monkeypatch.setattr(
        "reels_scrap.profiles.resolve_profile",
        lambda name, base_config="config.yaml": corpus,
    )

    calls: list[str] = []

    def fake_variant(reel, cfg, backend):
        calls.append(reel.id)
        if reel.id.endswith("0"):                     # one arm fails on some reels
            raise RuntimeError("model returned no JSON")
        return {"backend": "local", "model": "m", "summary": "s", "tags": ["t"],
                "facts": [{"text": "a fact", "timestamp": 1.0}], "structured": {},
                "tokens": {}, "elapsed_s": 1.0, "frames": 4, "created_at": ""}

    monkeypatch.setattr("reels_scrap.extract.vision.run_variant", fake_variant)

    out = bench.run(["m1"], base_config=str(tmp_path / "config.yaml"))
    first = out["profiles"]["m1"]
    assert first["done"] + first["failed"] == 6
    assert first["failed"] >= 1 and first["skipped"] == 0

    # second run re-attempts only what has no stored variant (the failures)
    calls.clear()
    again = bench.run(["m1"], base_config=str(tmp_path / "config.yaml"))["profiles"]["m1"]
    assert again["skipped"] == first["done"]
    assert len(calls) == first["failed"]

    stats = bench.run_stats(corpus)
    assert stats["m1"]["failed"] >= 1                 # the failure survives in the log
    rows = [json.loads(x) for x in
            (corpus.output_dir / bench.RUNS_FILE).read_text(encoding="utf-8").splitlines()]
    assert any(r["ok"] is False and r["error"] for r in rows)


def test_force_reruns_stored_pairs(corpus, monkeypatch, tmp_path):
    bench.save_sample(corpus, bench.build_sample(corpus, n=4, seed=0))
    monkeypatch.setattr(bench, "_release_gpu", lambda cfg: None)
    monkeypatch.setattr("reels_scrap.profiles.resolve_profile",
                        lambda name, base_config="config.yaml": corpus)
    monkeypatch.setattr("reels_scrap.extract.vision.run_variant",
                        lambda reel, cfg, backend: {"facts": [], "tokens": {}, "elapsed_s": 0.1})
    base = str(tmp_path / "config.yaml")
    bench.run(["m1"], base_config=base)
    forced = bench.run(["m1"], base_config=base, force=True)["profiles"]["m1"]
    assert forced["skipped"] == 0 and forced["done"] == 4


def test_report_renders_without_analysis(corpus, monkeypatch, tmp_path):
    sample = bench.build_sample(corpus, n=6, seed=0)
    bench.save_sample(corpus, sample)
    # the metrics table must describe the sample, not the whole corpus: a
    # corpus-wide backfill and a 30-reel arm are not the same measurement
    outsider = next(i for i in ("R01", "R02", "R03") if i not in sample.reel_ids)
    out = Reel.load(tmp_path / "data" / f"{outsider}.json")
    out.variants = {"stranger": {"facts": [{"text": "not in the sample"}], "tokens": {}}}
    out.save(tmp_path / "data")

    r = Reel.load(tmp_path / "data" / f"{sample.reel_ids[0]}.json")
    r.variants = {
        "claude-cli": {"backend": "claude-cli", "model": "claude", "summary": "ref",
                       "tags": ["a"], "structured": {"x": 1}, "elapsed_s": 20,
                       "facts": [{"text": "five github repos for homelab"},
                                 {"text": "coolify is a heroku alternative"}],
                       "tokens": {"cost_usd": 0.02}},
        "qwen3vl-8b": {"backend": "local", "model": "qwen3-vl:8b", "summary": "cand",
                       "tags": ["a"], "structured": {}, "elapsed_s": 5,
                       "facts": [{"text": "five github repos"},
                                 {"text": "the video shows a laptop"}],
                       "tokens": {}},
    }
    r.save(tmp_path / "data")

    monkeypatch.setattr(benchreport, "analyse", lambda ex, backend="claude-cli": "")
    text = benchreport.build_report(corpus, with_analysis=True)
    assert "## Metrics" in text and "qwen3vl-8b" in text
    assert "stranger" not in text                  # out-of-sample arm stays out
    assert "Analysis unavailable" in text          # degrades, does not crash
    assert "No run log yet" in text                # variants predating the bench are said so


def test_agreement_only_counts_shared_reels(corpus, tmp_path):
    from reels_scrap.compare import agreement, disagreement_examples

    r = Reel.load(tmp_path / "data" / "R02.json")
    r.variants = {
        "claude-cli": {"facts": [{"text": "alpha claim about repos"},
                                 {"text": "beta claim about pricing"}]},
        "small": {"facts": [{"text": "alpha claim about repos"}]},
    }
    r.save(tmp_path / "data")
    # a reel the reference never covered must not enter the denominator
    r2 = Reel.load(tmp_path / "data" / "R03.json")
    r2.variants = {"small": {"facts": [{"text": "lonely claim"}]}}
    r2.save(tmp_path / "data")

    a = agreement(corpus)["small"]
    assert a["reels"] == 1 and a["shared"] == 1 and a["only_reference"] == 1
    assert a["agreement"] == 0.5
    ex = disagreement_examples(corpus, limit=5)
    assert ex and ex[0]["model"] == "small" and ex[0]["only_reference"]
