"""Claim diffing + scoreboard aggregation. No models are run here."""

from __future__ import annotations

import pytest

from reels_scrap.compare import diff_facts, scoreboard
from reels_scrap.config import Config
from reels_scrap.models import Reel


def _f(text):
    return {"text": text, "timestamp": None, "frame": None}


def test_same_claim_phrased_differently_counts_as_shared():
    a = [_f("The video shows five GitHub repositories for engineers")]
    b = [_f("Five GitHub repositories are shown for software engineers")]
    d = diff_facts(a, b)
    assert len(d["shared"]) == 1
    assert not d["only_a"] and not d["only_b"]


def test_detailed_and_terse_versions_of_one_claim_match():
    """The real failure case: Claude adds the URL, the local model does not."""
    a = [_f('No. 1 is "Project Based Learning" at github.com/practical-tutorials/project-based-learning')]
    b = [_f("no. 1 PROJECT BASED LEARNING")]
    d = diff_facts(a, b)
    assert len(d["shared"]) == 1, d


def test_one_shared_word_is_not_a_match():
    a = [_f("python tutorial for beginners")]
    b = [_f("python")]
    d = diff_facts(a, b)
    assert d["shared"] == []
    assert len(d["only_a"]) == 1 and len(d["only_b"]) == 1


def test_unique_claims_land_on_the_right_side():
    a = [_f("project-based-learning is the first repo"), _f("shared claim about python")]
    b = [_f("shared claim about python"), _f("the creator recommends a resume tool")]
    d = diff_facts(a, b)
    assert len(d["shared"]) == 1
    assert d["only_a"] == ["project-based-learning is the first repo"]
    assert d["only_b"] == ["the creator recommends a resume tool"]


def test_each_claim_matches_at_most_one_partner():
    a = [_f("python tutorial for beginners"), _f("python tutorial for beginners")]
    b = [_f("python tutorial for beginners")]
    d = diff_facts(a, b)
    assert len(d["shared"]) == 1 and len(d["only_a"]) == 1


def test_empty_sides():
    assert diff_facts([], []) == {"shared": [], "only_a": [], "only_b": []}
    assert diff_facts([_f("x claim here")], []) == {
        "shared": [], "only_a": ["x claim here"], "only_b": []}


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "config.yaml").write_text(
        f"paths:\n  data_dir: {tmp_path/'data'}\n  output_dir: {tmp_path/'out'}\n",
        encoding="utf-8",
    )
    c = Config.load(tmp_path / "config.yaml")
    c.data_dir.mkdir(parents=True, exist_ok=True)
    return c


def test_scoreboard_averages_per_backend(cfg):
    r = Reel(id="AAA", url="https://ig/AAA")
    r.variants = {
        "claude-cli": {"backend": "claude-cli", "model": "sonnet", "summary": "x" * 300,
                       "tags": ["a", "b", "c"], "structured": {"k": 1},
                       "facts": [_f("alpha claim one"), _f("beta claim two")],
                       "tokens": {"cost_usd": 0.02}, "elapsed_s": 30.0},
        "local": {"backend": "local", "model": "reels-vision", "summary": "y" * 150,
                  "tags": ["a"], "structured": {},
                  "facts": [_f("alpha claim one")],
                  "tokens": {"cost_usd": 0.0}, "elapsed_s": 4.0},
    }
    r.save(cfg.data_dir)

    sb = scoreboard(cfg)
    assert sb["reels_compared"] == 1
    by = {b["backend"]: b for b in sb["backends"]}
    assert by["claude-cli"]["avg_facts"] == 2.0
    assert by["local"]["avg_facts"] == 1.0
    assert by["claude-cli"]["avg_seconds"] == 30.0
    assert by["local"]["cost_usd"] == 0.0
    # one of two claims is unique → 50% disagreement
    assert sb["avg_disagreement"] == 0.5


def test_scoreboard_ignores_reels_without_variants(cfg):
    Reel(id="BBB", url="https://ig/BBB").save(cfg.data_dir)
    assert scoreboard(cfg)["reels_compared"] == 0
