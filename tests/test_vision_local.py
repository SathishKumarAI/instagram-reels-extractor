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

    data, _tokens, used = vision._run_local(Reel(id="X", url="https://instagram.com/reel/X/"), cfg, _items(tmp_path))
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
    cfg.extract.vision_local_two_pass = False   # this test stubs the single-pass call
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


def test_two_pass_reads_then_structures(tmp_path, monkeypatch):
    """Pass 1 transcribes the frames; pass 2 turns that text into the schema.

    Pass 2 never sees the images — that is the whole point, it cannot invent what
    was not read. Opt-in: measured worse on summaries and structured fields, so the
    default is single-pass (see ExtractCfg.vision_local_two_pass).
    """
    cfg = _cfg()
    cfg.extract.vision_local_two_pass = True
    monkeypatch.setattr(vision, "_frames_with_time", lambda r, c: _items(tmp_path))

    seen = {}
    import requests
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: _Resp(_openai_payload("Frame 0 (0s): PYTEST 101 | a slide")))

    def fake_text_local(prompt, c):
        seen["prompt"] = prompt
        return VALID, {"input": 10, "output": 5}

    import reels_scrap.extract.text_summary as ts
    monkeypatch.setattr(ts, "_via_local", fake_text_local)

    reel = Reel(id="X", url="https://instagram.com/reel/X/")
    vision.add_summary(reel, cfg)

    assert "PYTEST 101" in seen["prompt"]          # pass 1's reading reached pass 2
    assert "data:image" not in seen["prompt"]      # …and no image did
    assert reel.genre == "tutorial"
    assert reel.tokens["backend"] == "local"
    assert reel.tokens["passes"] == 2


def test_reasoning_model_with_empty_content_falls_back_to_reasoning(monkeypatch, tmp_path):
    """qwen3-vl thinks before it answers and can return an empty `content`.

    The JSON is in `reasoning`; treating the reply as "no output" threw away a
    usable answer and cost 59s of GPU per reel.
    """
    import requests

    payload = {
        "choices": [{"message": {"content": "", "reasoning": f"Let me see. {json.dumps(VALID)}"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 900},
    }
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(payload))
    data, tokens = vision._via_local(Reel(id="X", url="u"), _cfg(), _items(tmp_path))
    assert data["genre"] == "tutorial"
    assert tokens["output"] == 900


def test_no_content_at_all_says_why(monkeypatch, tmp_path):
    import requests

    payload = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}], "usage": {}}
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(payload))
    with pytest.raises(RuntimeError, match="max_tokens"):
        vision._via_local(Reel(id="X", url="u"), _cfg(), _items(tmp_path))


def test_parse_json_picks_the_finished_object_not_the_sketch():
    """Reasoning models draft, correct, then answer — three objects in one reply.

    A greedy regex spans all of them ("Extra data"); the first one is the sketch.
    """
    text = (
        'Let me start: {"genre": "tutorial"}\n'
        'Actually the summary matters too: {"genre": "tutorial", "summary": "draft"}\n'
        'Final answer:\n'
        '{"genre": "tutorial", "summary": "A short demo.", "tags": ["python"], '
        '"structured": {}, "facts": [{"text": "uses pytest"}]}'
    )
    out = vision._parse_json(text)
    assert out["summary"] == "A short demo."
    assert out["facts"][0]["text"] == "uses pytest"


def test_parse_json_still_reads_a_fenced_object():
    assert vision._parse_json('prose\n```json\n{"genre": "news"}\n```\ntrailing')["genre"] == "news"


def test_parse_json_without_any_object_names_the_output():
    with pytest.raises(ValueError, match="no JSON object"):
        vision._parse_json("I cannot read these frames.")


def test_bare_string_facts_are_kept_ungrounded(monkeypatch, tmp_path):
    """A small model answers `"facts": ["…"]` — a claim with no frame.

    Counting that as "found nothing" would blame the model for the wrong failure.
    """
    import requests

    payload = dict(VALID, facts=["five github repos for a homelab setup",
                                 "coolify is a self-hostable heroku alternative"])
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(_openai_payload(json.dumps(payload))))
    monkeypatch.setattr(vision, "_frames_with_time", lambda r, c: _items(tmp_path))

    reel = Reel(id="X", url="https://instagram.com/reel/X/")
    vision.add_summary(reel, _cfg())
    assert [f.text for f in reel.facts] == ["five github repos for a homelab setup",
                                            "coolify is a self-hostable heroku alternative"]
    assert reel.facts[0].timestamp is None      # ungrounded, and honest about it


def test_message_text_helper_covers_all_three_shapes():
    """Every OpenAI-style reader goes through one helper, so a reasoning model
    behaves the same in the vision call, the two-pass reader and the text call."""
    ok = {"message": {"content": " {\"a\": 1} "}}
    assert vision.message_text(ok) == ('{"a": 1}', False)

    thinking = {"message": {"content": "", "reasoning": "draft"}, "finish_reason": "length"}
    assert vision.message_text(thinking) == ("draft", True)

    with pytest.raises(RuntimeError, match="max_tokens"):
        vision.message_text({"message": {"content": None}, "finish_reason": "length"})
