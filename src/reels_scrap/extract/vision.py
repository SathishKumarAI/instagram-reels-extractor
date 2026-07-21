"""Structured visual extraction with provenance.

Instead of a prose blurb, the model returns typed JSON: a genre, genre-specific
fields, and a list of FACTS — each tied to the frame + timestamp it was read from.
That makes the output queryable data and verifiable (scrub the reel to the second).

Backends (extract.vision_backend):
  - "claude-cli": Claude Code CLI (`claude -p`). Subscription auth, NO API key. Default.
  - "api": Anthropic SDK + ANTHROPIC_API_KEY.
  - "local": self-hosted OpenAI-compatible vision endpoint (vLLM/Ollama on your own
    GPU box, e.g. open-weights Kimi-VL). Frames stay on your LAN — no egress. On
    failure it falls back to claude-cli (unless vision_local_fallback=false).

Every backend returns the SAME parsed-JSON shape via `_apply`, so genre/summary/
tags/facts are schema-identical regardless of which model produced them. The reel's
`tokens` dict carries `backend` + `model` provenance.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time

from ..config import Config
from ..models import Fact, Reel
from ..observability import log
from .frames import sample_frames

MAX_FRAMES = 6  # default; overridden by cfg.extract.max_frames
CLI_TIMEOUT = 240

GENRES = ["tutorial", "product", "educational", "recipe", "news", "entertainment", "other"]

SCHEMA_INSTRUCTION = (
    "Return ONLY a single JSON object (no prose, no code fences) with this shape:\n"
    "{\n"
    '  "genre": one of ' + str(GENRES) + ",\n"
    '  "summary": "1-2 factual sentences, no fluff",\n'
    '  "tags": ["3-6 short lowercase topical tags for search/filter, e.g. '
    '\\"machine-learning\\", \\"resume-tips\\", \\"open-source\\"],\n'
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
    frames = sample_frames(
        video, cfg.data_dir / f"{reel.id}_frames", every,  # cached
        max_width=getattr(cfg.extract, "frame_max_width", 0),
    )
    items = [(i, round(i * every, 1), p) for i, p in enumerate(frames)]
    cap = getattr(cfg.extract, "max_frames", MAX_FRAMES)
    if len(items) > cap:
        step = len(items) / cap
        items = [items[int(k * step)] for k in range(cap)]
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


def _norm_tags(raw) -> list[str]:
    """Lowercase, hyphenate, de-dupe tags; drop empties. Cap at 8."""
    out: list[str] = []
    for t in raw or []:
        s = re.sub(r"\s+", "-", str(t).strip().lower())
        s = re.sub(r"[^a-z0-9-]", "", s).strip("-")
        if s and s not in out:
            out.append(s)
    return out[:8]


def _apply(reel: Reel, data: dict) -> None:
    reel.genre = str(data.get("genre", "") or "")
    reel.summary = str(data.get("summary", "") or "")
    reel.tags = _norm_tags(data.get("tags"))
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


def _via_cli(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
    """Returns (parsed model JSON, {input, output} token usage)."""
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("claude CLI not found; set vision_backend=api")
    listing = "\n".join(f"Frame {i} at {t}s: {p.resolve()}" for i, t, p in items)
    prompt = _prompt_header(reel) + "\nRead these frame images, in order:\n" + listing
    # --output-format json wraps the reply in an envelope carrying token usage.
    # NOTE: claude-cli usage counts the whole CLI turn (system prompt + tool schemas +
    # cache), so `input` here is an UPPER BOUND, not the raw vision-call tokens. For
    # precise per-reel cost use vision_backend=api (msg.usage is the true call cost).
    proc = subprocess.run(
        [claude, "-p", prompt, "--allowedTools", "Read", "--output-format", "json"],
        capture_output=True, text=True, timeout=CLI_TIMEOUT,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr.strip()[:200]}")
    tokens: dict[str, float] = {}
    text = proc.stdout
    try:
        env = json.loads(proc.stdout)
        text = env.get("result", proc.stdout)
        u = env.get("usage", {}) or {}
        # keep components separate: cache_read is ~free (~10% price) and is mostly the
        # CLI's own system-prompt/tools reloaded each call — NOT reel content.
        tokens = {
            "input": int(u.get("input_tokens", 0)),                        # fresh
            "cache_read": int(u.get("cache_read_input_tokens", 0)),        # cheap
            "cache_creation": int(u.get("cache_creation_input_tokens", 0)),
            "output": int(u.get("output_tokens", 0)),
            "cost_usd": float(env.get("total_cost_usd", 0.0)),            # real, from CLI
        }
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass  # older CLI / non-envelope output → parse raw, no usage
    return _parse_json(text), tokens


def _via_api(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
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
    # API backend: no CLI overhead → input is just prompt+images (~15-20x fewer than cli)
    i, o = int(msg.usage.input_tokens), int(msg.usage.output_tokens)
    pin, pout = 3.0, 15.0  # sonnet $/M (approx)
    tokens = {"input": i, "cache_read": 0, "cache_creation": 0, "output": o,
              "cost_usd": round(i / 1e6 * pin + o / 1e6 * pout, 4)}
    return _parse_json("".join(b.text for b in msg.content if b.type == "text")), tokens


def _via_local(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
    """Self-hosted OpenAI-compatible vision endpoint (vLLM/Ollama/Kimi-VL).

    POSTs frames as base64 data-URI images to {base_url}/chat/completions. Runs on
    your own GPU box — no data egress. Returns (parsed JSON, token usage).
    """
    import requests

    lc = cfg.extract.vision_local
    if not lc.base_url:
        raise RuntimeError(
            "vision_local.base_url is empty — set your OpenAI-compatible endpoint "
            "(e.g. http://gpu-box:8000/v1)"
        )
    content: list[dict] = []
    for i, t, p in items:
        content.append({"type": "text", "text": f"Frame {i} at {t}s:"})
        b64 = base64.standard_b64encode(p.read_bytes()).decode()
        content.append(
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )
    content.append({"type": "text", "text": _prompt_header(reel)})

    url = lc.base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if lc.api_key:
        headers["Authorization"] = f"Bearer {lc.api_key}"
    body = {
        "model": lc.model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": lc.max_tokens,
        "temperature": 0,   # deterministic → repeatable results per reel
    }
    resp = requests.post(url, json=body, headers=headers, timeout=lc.timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"local vision HTTP {resp.status_code}: {resp.text[:200]}")
    payload = resp.json()
    text = payload["choices"][0]["message"]["content"]
    u = payload.get("usage", {}) or {}
    tokens = {
        "input": int(u.get("prompt_tokens", 0)),
        "cache_read": 0,
        "cache_creation": 0,
        "output": int(u.get("completion_tokens", 0)),
        "cost_usd": 0.0,   # your own hardware
    }
    return _parse_json(text), tokens   # _parse_json raises on malformed → triggers fallback


def _resolve_backend(backend: str) -> str:
    """'auto' -> api when ANTHROPIC_API_KEY is set (cheaper + parallel), else claude-cli."""
    if backend == "auto":
        return "api" if os.environ.get("ANTHROPIC_API_KEY") else "claude-cli"
    return backend


_BACKENDS = {"claude-cli": _via_cli, "api": _via_api, "local": _via_local}


def _run_local(reel: Reel, cfg: Config, items) -> tuple[dict, dict, str]:
    """Try the local endpoint up to vision_max_retries; on total failure either
    fall back to claude-cli (vision_local_fallback=true) or re-raise. Returns
    (data, tokens, backend_used)."""
    e = cfg.extract
    last: Exception | None = None
    for attempt in range(1, e.vision_max_retries + 1):
        try:
            data, tokens = _via_local(reel, cfg, items)
            return data, tokens, "local"
        except Exception as ex:  # noqa: BLE001 — endpoint down / malformed JSON / timeout
            last = ex
            log.warning("%s: local vision attempt %d/%d failed: %s",
                        reel.id, attempt, e.vision_max_retries, ex)
            if attempt < e.vision_max_retries:
                time.sleep(e.vision_retry_backoff * (2 ** (attempt - 1)))
    if e.vision_local_fallback:
        log.warning("%s: local vision exhausted — falling back to claude-cli "
                    "(frames egress to Claude)", reel.id)
        data, tokens = _via_cli(reel, cfg, items)
        return data, tokens, "local->claude-cli"
    raise RuntimeError(f"local vision failed and fallback disabled: {last}") from last


def add_summary(reel: Reel, cfg: Config) -> Reel:
    items = _frames_with_time(reel, cfg)
    if not items:
        return reel
    backend = _resolve_backend(cfg.extract.vision_backend)
    log.info("%s: structured vision via %s (%d frames)", reel.id, backend, len(items))
    if backend == "local":
        data, tokens, used = _run_local(reel, cfg, items)
    else:
        data, tokens = _BACKENDS[backend](reel, cfg, items)
        used = backend
    _apply(reel, data)
    tokens = dict(tokens or {})
    tokens["backend"] = used   # provenance: which model actually produced this reel
    tokens["model"] = (
        cfg.extract.vision_local.model if used == "local" else cfg.extract.vision_model
    )
    reel.tokens = tokens
    log.info(
        "%s: [%s] genre=%s, %d facts, %d tags, tokens in/out=%s/%s",
        reel.id, used, reel.genre, len(reel.facts), len(reel.tags),
        reel.tokens.get("input", "?"), reel.tokens.get("output", "?"),
    )
    return reel
