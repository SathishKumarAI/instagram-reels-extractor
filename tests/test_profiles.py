"""Profile resolution: many named models, no corpus migration."""

from __future__ import annotations

import json

import pytest

from reels_scrap.profiles import list_profiles, profile_model, resolve_profile


def _write_cfg(tmp_path, extract: dict) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(
        json.dumps({"extract": extract, "paths": {"data_dir": str(tmp_path / "data"),
                                                  "output_dir": str(tmp_path / "output")}}),
        encoding="utf-8",
    )
    return str(p)


def test_implicit_names_resolve_without_being_declared(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # away from the repo's own models.yaml
    cfg_path = _write_cfg(tmp_path, {"vision": True, "vision_model": "claude-sonnet-4-6"})
    cfg = resolve_profile("claude-cli", cfg_path)
    assert cfg.extract.vision_backend == "claude-cli"
    assert profile_model("claude-cli", cfg_path) == "claude-sonnet-4-6"
    assert set(list_profiles(cfg_path)) == {"claude-cli", "api", "local"}


def test_declared_local_profile(tmp_path):
    cfg_path = _write_cfg(tmp_path, {
        "vision": True,
        "vision_local": {"base_url": "http://gpu:11434/v1", "model": "base"},
        "vision_profiles": {
            "qwen3vl-8b": {"kind": "local", "model": "qwen3-vl:8b", "max_tokens": 1200},
        },
    })
    cfg = resolve_profile("qwen3vl-8b", cfg_path)
    assert cfg.extract.vision_backend == "local"
    assert cfg.extract.vision_local.model == "qwen3-vl:8b"
    assert cfg.extract.vision_local.base_url == "http://gpu:11434/v1"   # inherited
    assert cfg.extract.vision_local.max_tokens == 1200
    # a Claude fallback would silently fake this arm's result
    assert cfg.extract.vision_local_fallback is False
    assert profile_model("qwen3vl-8b", cfg_path) == "qwen3-vl:8b"
    assert list_profiles(cfg_path)[0] == "qwen3vl-8b"


def test_declared_profile_wins_over_implicit(tmp_path):
    cfg_path = _write_cfg(tmp_path, {
        "vision": True,
        "vision_local": {"base_url": "http://gpu:11434/v1", "model": "old"},
        "vision_profiles": {
            "local": {"kind": "local", "model": "redefined", "base_url": "http://other/v1"},
        },
    })
    cfg = resolve_profile("local", cfg_path)
    assert (cfg.extract.vision_local.model, cfg.extract.vision_local.base_url) == (
        "redefined", "http://other/v1")


def test_unknown_profile_names_the_known_ones(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # no models.yaml here, so nothing else resolves
    cfg_path = _write_cfg(tmp_path, {"vision": True})
    with pytest.raises(KeyError, match="claude-cli"):
        resolve_profile("nope", cfg_path)


def test_registry_model_runs_by_name_without_a_config_edit(tmp_path, monkeypatch):
    """A pulled model must be runnable from models.yaml alone — config-local.yaml
    is hand-written and commented, and rewriting it would strip that."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models.yaml").write_text(
        "models:\n  qwen3vl-8b:\n    tag: qwen3-vl:8b\n    num_ctx: 32768\n", encoding="utf-8")
    cfg_path = _write_cfg(tmp_path, {
        "vision": True,
        "vision_local": {"base_url": "http://127.0.0.1:11434/v1", "model": "other"},
    })
    cfg = resolve_profile("qwen3vl-8b", cfg_path)
    assert cfg.extract.vision_local.model == "qwen3vl-8b"      # the built model name
    assert cfg.extract.vision_backend == "local"
    assert "qwen3vl-8b" in list_profiles(cfg_path)


def test_local_without_endpoint_fails_at_resolution(tmp_path, monkeypatch):
    # cwd matters: a real config-local.yaml would otherwise be found and used
    monkeypatch.chdir(tmp_path)
    cfg_path = _write_cfg(tmp_path, {
        "vision": True,
        "vision_profiles": {"headless": {"kind": "local", "model": "x"}},
    })
    with pytest.raises(ValueError, match="base_url"):
        resolve_profile("headless", cfg_path)
