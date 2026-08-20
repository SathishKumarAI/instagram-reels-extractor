"""Structured visual extraction with provenance — the backends and the run loop.

Instead of a prose blurb, the model returns typed JSON: a genre, genre-specific
fields, and a list of FACTS — each tied to the frame + timestamp it was read from.
That makes the output queryable data and verifiable (scrub the reel to the second).

This file owns frame selection, the four backends, retry/fallback and provenance.
It does NOT own the prompt (`prompts.py`) or the reading of the answer
(`normalise.py`) — both are re-exported below under their old private names so
callers and tests keep working.

Backends (extract.vision_backend):
  - "claude-cli": Claude Code CLI (`claude -p`). Subscription auth, NO API key. Default.
  - "api": Anthropic SDK + ANTHROPIC_API_KEY.
  - "local": self-hosted OpenAI-compatible vision endpoint (vLLM/Ollama on your own
    GPU box). Frames stay on your LAN — no egress. On failure it falls back to
    claude-cli (unless vision_local_fallback=false).

Every backend returns the SAME parsed-JSON shape, so genre/summary/tags/facts are
schema-identical regardless of which model produced them. The reel's `tokens` dict
carries `backend` + `model` provenance.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from datetime import UTC

from ..config import Config
from ..models import Reel
from ..observability import log
from .frames import sample_frames
from .normalise import apply as _apply
from .normalise import dedupe_facts as _dedupe_facts
from .normalise import is_fragment as _is_fragment
from .normalise import message_text
from .normalise import norm_tags as _norm_tags
from .normalise import parse_json as _parse_json
from .normalise import strip_subtitles as _strip_subtitles
from .normalise import unwrap_structured as _unwrap_structured
from .prompts import (
    CAPTION_CHARS,
    GENRES,
    LOCAL_NUDGE,
    READ_PROMPT,
    SCHEMA_INSTRUCTION,
    TRANSCRIPT_CHARS,
)
from .prompts import caption_for_prompt as _caption_for_prompt
from .prompts import prompt_header as _prompt_header

# re-exports: these names moved to prompts.py / normalise.py in the 2026-08-20 split.
# Listing them keeps `from .vision import _apply` (text_summary, tests, scripts)
# working — one module is still the door to structured extraction.
__all__ = [
    "CAPTION_CHARS", "GENRES", "LOCAL_NUDGE", "READ_PROMPT", "SCHEMA_INSTRUCTION",
    "TRANSCRIPT_CHARS", "_apply", "_caption_for_prompt", "_dedupe_facts",
    "_is_fragment", "_norm_tags", "_parse_json", "_prompt_header", "_strip_subtitles",
    "_unwrap_structured", "add_summary", "message_text", "run_variant",
]

MAX_FRAMES = 6  # default; overridden by cfg.extract.max_frames
CLI_TIMEOUT = 240


def _frames_with_time(reel: Reel, cfg: Config):
    """Return [(idx, timestamp_sec, path)] subsampled to MAX_FRAMES."""
    # the None check has to come FIRST: `data_dir / None` raises TypeError, so a
    # reel with no video (image carousel, failed download) crashed the caller
    # instead of returning "no frames"
    if not reel.video_path:
        return []
    video = cfg.data_dir / reel.video_path
    if not video.exists():
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


def _image_content(items, url_style: bool) -> list[dict]:
    """Frames as OpenAI/Anthropic message parts, each labelled with its timestamp.

    One builder for both wire formats: they differ only in how an image is spelled
    (`image_url` data-URI vs `image` + base64 source), and having written that twice
    is how the two paths drifted apart before.
    """
    content: list[dict] = []
    for i, t, p in items:
        content.append({"type": "text", "text": f"Frame {i} at {t}s:"})
        b64 = base64.standard_b64encode(p.read_bytes()).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            if url_style else
            {"type": "image",
             "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}
        )
    return content


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
        [claude, "-p", "--allowedTools", "Read", "--output-format", "json"],
        input=prompt,   # not argv: Windows caps a command line at ~32k chars
        capture_output=True, text=True, timeout=CLI_TIMEOUT,
        # a caption with an emoji in the reply is enough to kill the decode on
        # Windows, where text mode defaults to cp1252
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {(proc.stderr or '').strip()[:200]}")
    tokens: dict[str, float] = {}
    # exit 0 with nothing on stdout happens (a refused/empty turn). Say that, rather
    # than letting json.loads(None) surface as a TypeError with no context.
    if not proc.stdout:
        raise RuntimeError(
            f"claude CLI returned no output: {(proc.stderr or '').strip()[:200] or 'empty stdout'}"
        )
    text = proc.stdout
    try:
        env = json.loads(proc.stdout)
        text = env.get("result") or proc.stdout   # `result: null` on an errored turn
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

    content = _image_content(items, url_style=False)
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


def _post_local(cfg: Config, content: list[dict]) -> dict:
    """One call to the local OpenAI-compatible endpoint. Returns the raw payload."""
    import requests

    lc = cfg.extract.vision_local
    if not lc.base_url:
        raise RuntimeError(
            "vision_local.base_url is empty — set your OpenAI-compatible endpoint "
            "(e.g. http://gpu-box:8000/v1)"
        )
    headers = {"Content-Type": "application/json"}
    if lc.api_key:
        headers["Authorization"] = f"Bearer {lc.api_key}"
    resp = requests.post(
        lc.base_url.rstrip("/") + "/chat/completions",
        json={
            "model": lc.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": lc.max_tokens,
            "temperature": 0,   # deterministic → repeatable results per reel
        },
        headers=headers, timeout=lc.timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"local vision HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _via_local(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
    """Self-hosted OpenAI-compatible vision endpoint (vLLM/Ollama).

    POSTs frames as base64 data-URI images. Runs on your own GPU box — no data
    egress. Returns (parsed JSON, token usage).
    """
    content = _image_content(items, url_style=True)
    content.append({"type": "text", "text": _prompt_header(reel) + LOCAL_NUDGE})
    payload = _post_local(cfg, content)
    choice = payload["choices"][0]
    text, salvaged = message_text(choice)
    u = payload.get("usage", {}) or {}
    tokens = {
        "input": int(u.get("prompt_tokens", 0)),
        "cache_read": 0,
        "cache_creation": 0,
        "output": int(u.get("completion_tokens", 0)),
        # a record scraped out of a reasoning trace is not the same as one the model
        # finished — the bench counts these separately rather than averaging them in
        "salvaged": salvaged,
        "finish_reason": str(choice.get("finish_reason") or ""),
        "cost_usd": 0.0,   # your own hardware
    }
    return _parse_json(text), tokens   # _parse_json raises on malformed → triggers fallback


def _via_local_2pass(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
    """Read-then-structure. Pass 1 asks the VLM only to transcribe the frames;
    pass 2 is a text-only call that turns those readings into the schema.

    Splitting the job stops a 7B from having to see and reason at once — and pass 2
    cannot invent what it never saw, because it only gets pass 1's text.
    """
    content = _image_content(items, url_style=True)
    content.append({"type": "text", "text": READ_PROMPT})
    p1 = _post_local(cfg, content)
    readings, _ = message_text(p1["choices"][0])
    u1 = p1.get("usage", {}) or {}
    log.info("%s: [local/pass1] read %d chars from %d frames", reel.id, len(readings), len(items))

    from .text_summary import _via_local as _text_local

    prompt = (
        f"A short Instagram reel. Caption: {reel.caption[:500] or '(none)'}\n\n"
        f"What is on screen, frame by frame:\n{readings}\n\n"
        f"{SCHEMA_INSTRUCTION}\n{LOCAL_NUDGE}"
        "Every fact MUST quote or closely paraphrase a line above, and its `frame`/"
        "`timestamp` MUST be the frame that line came from. Invent nothing.\n"
    )
    data, u2 = _text_local(prompt, cfg)
    tokens = {
        "input": int(u1.get("prompt_tokens", 0)) + int(u2.get("input", 0)),
        "cache_read": 0, "cache_creation": 0,
        "output": int(u1.get("completion_tokens", 0)) + int(u2.get("output", 0)),
        "cost_usd": 0.0,
        "passes": 2,
    }
    return data, tokens


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
            # looked up per attempt, not hoisted: the tests (and the bench) monkeypatch
            # `vision._via_local`, and a hoisted reference would miss the patch
            run = _via_local_2pass if e.vision_local_two_pass else _via_local
            data, tokens = run(reel, cfg, items)
            return data, tokens, "local"
        except Exception as ex:
            last = ex
            log.warning("%s: local vision attempt %d/%d failed: %s",
                        reel.id, attempt, e.vision_max_retries, ex)
            # a failure is the moment to ask WHY: if something else took the card,
            # ollama has silently put layers on CPU and every retry costs a full
            # timeout to fail identically. One reel wasted, not the whole run.
            from ..modelreg import GpuContended, processor_of

            proc = processor_of(e.vision_local.model)
            if proc and not proc.startswith("100%"):
                raise GpuContended(
                    f"{e.vision_local.model} is running {proc} — another job has the "
                    f"GPU. Stopping: retries would each cost {e.vision_local.timeout:.0f}s "
                    f"and fail the same way. Re-run when the card is free."
                ) from ex
            if attempt < e.vision_max_retries:
                time.sleep(e.vision_retry_backoff * (2 ** (attempt - 1)))
    if e.vision_local_fallback:
        log.warning("%s: local vision exhausted — falling back to claude-cli "
                    "(frames egress to Claude)", reel.id)
        data, tokens = _via_cli(reel, cfg, items)
        return data, tokens, "local->claude-cli"
    raise RuntimeError(f"local vision failed and fallback disabled: {last}") from last


def _extract(reel: Reel, cfg: Config, backend: str, items) -> tuple[dict, dict, str]:
    """Run one backend over `items`. Returns (data, tokens-with-provenance, used)."""
    b = _resolve_backend(backend)
    if b == "local":
        data, tokens, used = _run_local(reel, cfg, items)
    else:
        data, tokens = _BACKENDS[b](reel, cfg, items)
        used = b
    tokens = dict(tokens or {})
    tokens["backend"] = used   # provenance: which model actually produced this record
    # "local->claude-cli" is a fallback that ran on Claude — name Claude, not the
    # local model that failed
    tokens["model"] = (
        cfg.extract.vision_local.model if used == "local" else cfg.extract.vision_model
    )
    return data, tokens, used


def run_variant(reel: Reel, cfg: Config, backend: str) -> dict:
    """Summarise `reel` with ONE named backend and return the result as a variant.

    Does not touch the reel — the caller decides what to store. This is what the
    Compare tab runs to put two models on the same frames and diff them.
    """
    from datetime import datetime

    items = _frames_with_time(reel, cfg)
    if not items:
        raise RuntimeError(f"{reel.id}: no frames (missing video?)")
    t0 = time.time()
    data, tokens, used = _extract(reel, cfg, backend, items)
    elapsed = round(time.time() - t0, 2)

    # reuse _apply's normalisation by running it on a throwaway copy
    probe = reel.model_copy(deep=True)
    _apply(probe, data)
    log.info("%s: [variant/%s] %d facts, %d tags in %.1fs",
             reel.id, used, len(probe.facts), len(probe.tags), elapsed)
    return {
        "backend": used,
        "model": tokens["model"],
        "summary": probe.summary,
        "key_points": probe.key_points,
        "on_screen_text": probe.on_screen_text,
        "genre": probe.genre,
        "tags": probe.tags,
        "structured": probe.structured,
        "facts": [f.model_dump() for f in probe.facts],
        "tokens": tokens,
        "elapsed_s": elapsed,
        "frames": len(items),
        "created_at": datetime.now(tz=UTC).isoformat(),
    }


def add_summary(reel: Reel, cfg: Config) -> Reel:
    items = _frames_with_time(reel, cfg)
    if not items:
        return reel
    backend = _resolve_backend(cfg.extract.vision_backend)
    log.info("%s: structured vision via %s (%d frames)", reel.id, backend, len(items))
    data, tokens, used = _extract(reel, cfg, backend, items)
    _apply(reel, data)
    reel.tokens = tokens
    log.info(
        "%s: [%s] genre=%s, %d facts, %d tags, tokens in/out=%s/%s",
        reel.id, used, reel.genre, len(reel.facts), len(reel.tags),
        reel.tokens.get("input", "?"), reel.tokens.get("output", "?"),
    )
    return reel
