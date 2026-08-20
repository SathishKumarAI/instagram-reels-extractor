"""`tokens.model` records the model that RAN, not the one config asked for.

The claude-cli backend runs whatever the Claude Code session is on. Config said
`claude-sonnet-4-6`, so 719 stored records claim a model that may never have
touched them — and the Compare scoreboard, the model filter and the cost rollup
all read that field.
"""
from __future__ import annotations

import json

from reels_scrap.config import Config
from reels_scrap.extract import vision
from reels_scrap.models import Reel

ENVELOPE = {
    "result": json.dumps({"genre": "tutorial", "summary": "x", "facts": []}),
    "usage": {"input_tokens": 5, "output_tokens": 7},
    "total_cost_usd": 0.3,
    "modelUsage": {
        "claude-opus-5[1m]": {"outputTokens": 900, "canonicalModel": "claude-opus-5"},
        "claude-haiku-4-5": {"outputTokens": 12, "canonicalModel": "claude-haiku-4-5"},
    },
}


def _cli_returns(payload: dict, monkeypatch):
    class _Proc:
        returncode = 0
        stdout = json.dumps(payload)
        stderr = ""

    monkeypatch.setattr(vision.shutil, "which", lambda _: "claude")
    monkeypatch.setattr(vision.subprocess, "run", lambda *a, **k: _Proc())


def _items(tmp_path):
    f = tmp_path / "f0.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    return [(0, 0.0, f)]


def test_the_model_that_ran_wins_over_the_configured_one(tmp_path, monkeypatch):
    _cli_returns(ENVELOPE, monkeypatch)
    cfg = Config.load("config-claude.yaml")
    cfg.extract.vision_model = "claude-sonnet-4-6"      # what config wishes for
    monkeypatch.setattr(vision, "_frames_with_time", lambda r, c: _items(tmp_path))

    reel = Reel(id="X", url="u")
    vision.add_summary(reel, cfg)
    # the busiest arm, by its canonical name — not the wire id, not the config
    assert reel.tokens["model"] == "claude-opus-5"
    assert reel.tokens["backend"] == "claude-cli"


def test_an_older_cli_without_modelusage_keeps_the_configured_name(tmp_path, monkeypatch):
    env = {k: v for k, v in ENVELOPE.items() if k != "modelUsage"}
    _cli_returns(env, monkeypatch)
    cfg = Config.load("config-claude.yaml")
    cfg.extract.vision_model = "claude-sonnet-4-6"
    monkeypatch.setattr(vision, "_frames_with_time", lambda r, c: _items(tmp_path))

    reel = Reel(id="X", url="u")
    vision.add_summary(reel, cfg)
    assert reel.tokens["model"] == "claude-sonnet-4-6"   # a guess beats nothing


def test_cli_model_reads_the_wire_id_when_canonical_is_absent():
    assert vision._cli_model({"modelUsage": {"claude-opus-5[1m]": {"outputTokens": 1}}}) == \
        "claude-opus-5[1m]"
    assert vision._cli_model({}) == ""
