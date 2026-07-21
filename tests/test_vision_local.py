"""Local (OpenAI-compatible) vision backend: parsing, tokens, fallback, provenance.

All HTTP is mocked — no GPU box or network needed (build-ahead verification).
"""
from __future__ import annotations

import json

import pytest

from reels_scrap.config import Config, ExtractCfg, VisionLocalCfg
from reels_scrap.extract import vision
from reels_scrap.models import Reel

VALID = {
    "genre": "tutorial",
    "summary": "A short demo.",
    "tags": ["Python", "testing"],
    "structured": {"tools": ["pytest"]},
    "facts": [{"text": "uses pytest", "frame": 0, "timestamp": 1.0}],
}


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, json.dumps(payload)

    def json(self):
        return self._p


def _openai_payload(content: str, pin=120, pout=40):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": pin, "completion_tokens": pout},
    }


def _items(tmp_path):
    f = tmp_path / "f0.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0jpegbytes")  # not a real jpeg; only read_bytes matters
    return [(0, 0.0, f)]


def _cfg(base_url="http://gpu-box:8000/v1", fallback=True):
    c = Config.load("config-claude.yaml")
    c.extract.vision_backend = "local"
    c.extract.vision_local = VisionLocalCfg(base_url=base_url)
    c.extract.vision_local_fallback = fallback
    c.extract.vision_max_retries = 2
    c.extract.vision_retry_backoff = 0  # no sleeping in tests
    return c


def test_via_local_parses_and_counts_tokens(tmp_path, monkeypatch):
    cfg = _cfg()
    # _via_local does `import requests` lazily → patch the module's post()
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(_openai_payload(json.dumps(VALID))))

    reel = Reel(id="X", url="https://instagram.com/reel/X/")
    data, tokens = vision._via_local(reel, cfg, _items(tmp_path))
    assert data["genre"] == "tutorial"
    assert tokens["input"] == 120 and tokens["output"] == 40
    assert tokens["cost_usd"] == 0.0  # own hardware


def test_local_falls_back_to_claude_on_bad_json(tmp_path, monkeypatch):
    cfg = _cfg(fallback=True)
    import requests
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: _Resp(_openai_payload("this is not json at all")))
    # claude fallback returns a known-good result
    monkeypatch.setattr(vision, "_via_cli",
                        lambda r, c, it: (VALID, {"input": 9, "output": 9, "cost_usd": 0.02}))

    data, tokens, used = vision._run_local(Reel(id="X", url="https://instagram.com/reel/X/"), cfg, _items(tmp_path))
    assert used == "local->claude-cli"
    assert data["genre"] == "tutorial"


def test_local_no_fallback_raises(tmp_path, monkeypatch):
    cfg = _cfg(fallback=False)
    import requests
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: _Resp({"error": "boom"}, status=500))
    with pytest.raises(RuntimeError):
        vision._run_local(Reel(id="X", url="https://instagram.com/reel/X/"), cfg, _items(tmp_path))


def test_add_summary_records_provenance_and_roundtrips(tmp_path, monkeypatch):
    cfg = _cfg()
    monkeypatch.setattr(vision, "_frames_with_time", lambda r, c: _items(tmp_path))
    monkeypatch.setattr(vision, "_via_local",
                        lambda r, c, it: (VALID, {"input": 100, "output": 30, "cost_usd": 0.0}))

    reel = Reel(id="X", url="https://instagram.com/reel/X/")
    vision.add_summary(reel, cfg)
    assert reel.genre == "tutorial"
    assert reel.tokens["backend"] == "local"
    assert reel.tokens["model"] == "moonshotai/Kimi-VL-A3B-Instruct"
    # tokens now mixes ints + strings — must still save + load (dict[str, Any])
    reel.save(tmp_path)
    again = Reel.load(tmp_path / "X.json")
    assert again.tokens["backend"] == "local"
    assert again.tokens["input"] == 100


def test_config_rejects_local_without_base_url():
    with pytest.raises(Exception):
        ExtractCfg(vision_backend="local", vision_local=VisionLocalCfg(base_url=""))
