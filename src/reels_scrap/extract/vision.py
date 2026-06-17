"""Structured visual extraction with provenance.

Instead of a prose blurb, the model returns typed JSON: a genre, genre-specific
fields, and a list of FACTS — each tied to the frame + timestamp it was read from.
That makes the output queryable data and verifiable (scrub the reel to the second).

Backends (extract.vision_backend):
  - "claude-cli": Claude Code CLI (`claude -p`). Subscription auth, NO API key. Default.
  - "api": Anthropic SDK + ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess

from ..config import Config
from ..models import Fact, Reel
from ..observability import log
from .frames import sample_frames

MAX_FRAMES = 8
CLI_TIMEOUT = 240

GENRES = ["tutorial", "product", "educational", "recipe", "news", "entertainment", "other"]

SCHEMA_INSTRUCTION = (
    "Return ONLY a single JSON object (no prose, no code fences) with this shape:\n"
    "{\n"
    '  "genre": one of ' + str(GENRES) + ",\n"
    '  "summary": "1-2 factual sentences, no fluff",\n'
    '  "structured": { genre-appropriate fields. e.g. tutorial -> '
    '{"tools":[],"commands":[],"links":[],"steps":[]}; '
    'product -> {"name":"","price":"","link":"","claims":[]}; '
    'recipe -> {"ingredients":[],"steps":[],"time":""}; '
    'educational -> {"topic":"","key_concepts":[],"resources":[]} },\n'
    '  "facts": [ {"text":"a specific claim VISIBLE in a frame", '
    '"frame": <frame index int>, "timestamp": <seconds number>} ]\n'
    "}\n"
    "Rules: 3-8 facts. Every fact MUST be grounded in a specific frame you were given; "
    "set frame/timestamp to that frame's label. Describe only what is visible. "
    "Do NOT invent prices, names, or numbers you cannot read."
)


def _frames_with_time(reel: Reel, cfg: Config):
    """Return [(idx, timestamp_sec, path)] subsampled to MAX_FRAMES."""
    video = cfg.data_dir / reel.video_path
    if not reel.video_path or not video.exists():
        return []
    every = cfg.extract.frame_every_sec
    frames = sample_frames(video, cfg.data_dir / f"{reel.id}_frames", every)
    items = [(i, round(i * every, 1), p) for i, p in enumerate(frames)]
    if len(items) > MAX_FRAMES:
        step = len(items) / MAX_FRAMES
        items = [items[int(k * step)] for k in range(MAX_FRAMES)]
    return items


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from model output, tolerant of fences/prose."""
    text = text.strip()
    # strip ```json ... ``` fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in model output: {text[:120]!r}")
    return json.loads(m.group(0))


def _apply(reel: Reel, data: dict) -> None:
    reel.genre = str(data.get("genre", "") or "")
    reel.summary = str(data.get("summary", "") or "")
    structured = data.get("structured")
    reel.structured = structured if isinstance(structured, dict) else {}
    facts = []
    for f in data.get("facts", []) or []:
        if not isinstance(f, dict) or not f.get("text"):
            continue
        facts.append(
            Fact(
                text=str(f["text"]),
                frame=f.get("frame") if isinstance(f.get("frame"), int) else None,
                timestamp=(
                    float(f["timestamp"])
                    if isinstance(f.get("timestamp"), (int, float))
                    else None
                ),
            )
        )
    reel.facts = facts


def _prompt_header(reel: Reel) -> str:
    return (
        f"These are frames sampled in order from a short Instagram reel.\n"
        f"Caption: {reel.caption[:500] or '(none)'}\n\n{SCHEMA_INSTRUCTION}\n"
    )


def _via_cli(reel: Reel, cfg: Config, items) -> dict:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("claude CLI not found; set vision_backend=api")
    listing = "\n".join(f"Frame {i} at {t}s: {p.resolve()}" for i, t, p in items)
    prompt = _prompt_header(reel) + "\nRead these frame images, in order:\n" + listing
    proc = subprocess.run(
        [claude, "-p", prompt, "--allowedTools", "Read"],
        capture_output=True, text=True, timeout=CLI_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr.strip()[:200]}")
    return _parse_json(proc.stdout)


def _via_api(reel: Reel, cfg: Config, items) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; use vision_backend=claude-cli")
    import anthropic

    content: list[dict] = []
    for i, t, p in items:
        content.append({"type": "text", "text": f"Frame {i} at {t}s:"})
        data = base64.standard_b64encode(p.read_bytes()).decode()
        content.append(
            {"type": "image",
             "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}
        )
    content.append({"type": "text", "text": _prompt_header(reel)})
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=cfg.extract.vision_model,
        max_tokens=900,
        messages=[{"role": "user", "content": content}],
    )
    return _parse_json("".join(b.text for b in msg.content if b.type == "text"))


def add_summary(reel: Reel, cfg: Config) -> Reel:
    items = _frames_with_time(reel, cfg)
    if not items:
        return reel
    backend = cfg.extract.vision_backend
    log.info("%s: structured vision via %s (%d frames)", reel.id, backend, len(items))
    data = _via_cli(reel, cfg, items) if backend == "claude-cli" else _via_api(reel, cfg, items)
    _apply(reel, data)
    log.info("%s: genre=%s, %d facts", reel.id, reel.genre, len(reel.facts))
    return reel
