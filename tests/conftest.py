"""Shared fixtures: an isolated config + a tiny fake reel corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reels_scrap.config import Config
from reels_scrap.models import Fact, Reel


@pytest.fixture()
def cfg(tmp_path: Path) -> Config:
    data = tmp_path / "data"
    out = tmp_path / "output"
    data.mkdir()
    out.mkdir()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        json.dumps(
            {
                "extract": {"vision": True, "vision_backend": "claude-cli"},
                "paths": {"data_dir": str(data), "output_dir": str(out)},
            }
        )
    )
    c = Config.load(cfg_path)
    # two reels across two genres, with provenance facts
    Reel(
        id="AAA", url="https://insta/reel/AAA/", title="Homelab repos",
        author="carter", genre="educational", summary="Self-hosting GitHub repos.",
        hashtags=["homelab", "selfhosting"],
        facts=[Fact(text="coolify is a self-hostable Heroku alternative", timestamp=10.0)],
    ).save(data)
    Reel(
        id="BBB", url="https://insta/reel/BBB/", title="A gadget",
        author="shop", genre="product", summary="A new gadget.",
        facts=[Fact(text="the gadget costs $20", timestamp=3.0)],
    ).save(data)
    return c
