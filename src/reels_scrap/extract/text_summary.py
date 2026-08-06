"""Structure a TEXT record (article / paper / release) into the same typed schema
as vision — genre, summary, tags, structured fields, facts, tokens — but from
text instead of frames. Used for RSS/arXiv/GitHub sources (no video).

Reuses the vision module's schema + JSON parsing + `_apply` so text and reel
records are schema-identical downstream. Same backend selection (claude-cli /
api / local), same provenance + strict-local behavior.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from ..config import Config
from ..models import Reel
from ..observability import log
from .vision import GENRES, _apply, _parse_json, _resolve_backend, message_text

MAX_CHARS = 12000  # cap the text sent to the model

TEXT_SCHEMA = (
    "You are given the full text of an article, paper, or release note. "
    "Return ONLY a single JSON object (no prose, no code fences) with this shape:\n"
    "{\n"
    '  "genre": one of ' + str(GENRES) + ",\n"
    '  "summary": "2-3 factual sentences capturing the core contribution/point",\n'
    '  "tags": ["3-6 short lowercase topical tags for search/filter"],\n'
    '  "structured": { genre-appropriate fields, e.g. educational -> '
    '{"topic":"","key_concepts":[],"resources":[]}; product -> '
    '{"name":"","link":"","claims":[]} },\n'
    '  "facts": [ {"text":"a specific claim stated in the text"} ]\n'
    "}\n"
    "Rules: 3-8 facts, each a concrete claim grounded in the text (no timestamps). "
    "Describe only what the text states. Do NOT invent numbers or names."
)


def _prompt(reel: Reel) -> str:
    body = (reel.caption or reel.transcript_text or "")[:MAX_CHARS]
    return (f"Title: {reel.title or '(none)'}\nAuthor: {reel.author or '(none)'}\n\n"
            f"TEXT:\n{body}\n\n{TEXT_SCHEMA}\n")


def _via_cli(prompt: str, cfg: Config) -> tuple[dict, dict]:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("claude CLI not found; set vision_backend=api")
    proc = subprocess.run(
        [claude, "-p", "--output-format", "json"],
        input=prompt,   # not argv: Windows caps a command line at ~32k chars
        capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace",   # cp1252 default cannot read our own captions
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr.strip()[:200]}")
    text, tokens = proc.stdout, {}
    try:
        env = json.loads(proc.stdout)
        text = env.get("result", proc.stdout)
        u = env.get("usage", {}) or {}
        tokens = {"input": int(u.get("input_tokens", 0)),
                  "cache_read": int(u.get("cache_read_input_tokens", 0)),
                  "cache_creation": int(u.get("cache_creation_input_tokens", 0)),
                  "output": int(u.get("output_tokens", 0)),
                  "cost_usd": float(env.get("total_cost_usd", 0.0))}
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    return _parse_json(text), tokens


def _via_api(prompt: str, cfg: Config) -> tuple[dict, dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; use vision_backend=claude-cli")
    import anthropic
    msg = anthropic.Anthropic(api_key=key).messages.create(
        model=cfg.extract.vision_model, max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    i, o = int(msg.usage.input_tokens), int(msg.usage.output_tokens)
    tokens = {"input": i, "cache_read": 0, "cache_creation": 0, "output": o,
              "cost_usd": round(i / 1e6 * 3.0 + o / 1e6 * 15.0, 4)}
    return _parse_json("".join(b.text for b in msg.content if b.type == "text")), tokens


def _via_local(prompt: str, cfg: Config) -> tuple[dict, dict]:
    import requests
    lc = cfg.extract.vision_local
    if not lc.base_url:
        raise RuntimeError("vision_local.base_url is empty")
    headers = {"Content-Type": "application/json"}
    if lc.api_key:
        headers["Authorization"] = f"Bearer {lc.api_key}"
    resp = requests.post(
        lc.base_url.rstrip("/") + "/chat/completions",
        json={"model": lc.model, "temperature": 0, "max_tokens": lc.max_tokens,
              "messages": [{"role": "user", "content": prompt}]},
        headers=headers, timeout=lc.timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"local text HTTP {resp.status_code}: {resp.text[:200]}")
    p = resp.json()
    u = p.get("usage", {}) or {}
    tokens = {"input": int(u.get("prompt_tokens", 0)), "cache_read": 0,
              "cache_creation": 0, "output": int(u.get("completion_tokens", 0)),
              "cost_usd": 0.0}
    text, salvaged = message_text(p["choices"][0])
    tokens["salvaged"] = salvaged
    return _parse_json(text), tokens


_TEXT_BACKENDS = {"claude-cli": _via_cli, "api": _via_api, "local": _via_local}


def add_text_summary(reel: Reel, cfg: Config) -> Reel:
    """Structure the record's text into genre/summary/tags/facts/tokens."""
    if not (reel.caption or reel.transcript_text):
        return reel
    backend = _resolve_backend(cfg.extract.vision_backend)
    prompt = _prompt(reel)
    e = cfg.extract

    def _run(b):
        return _TEXT_BACKENDS[b](prompt, cfg)

    used = backend
    if backend == "local":
        last = None
        for attempt in range(1, e.vision_max_retries + 1):
            try:
                data, tokens = _run("local")
                used = "local"
                break
            except Exception as ex:
                last = ex
                log.warning("%s: local text attempt %d failed: %s", reel.id, attempt, ex)
                if attempt < e.vision_max_retries:
                    time.sleep(e.vision_retry_backoff * (2 ** (attempt - 1)))
        else:
            if not e.vision_local_fallback:
                raise RuntimeError(f"local text failed, fallback disabled: {last}")
            data, tokens = _run("claude-cli")
            used = "local->claude-cli"
    else:
        data, tokens = _run(backend)

    _apply(reel, data)
    tokens = dict(tokens or {})
    tokens["backend"] = used
    tokens["model"] = cfg.extract.vision_local.model if used == "local" else cfg.extract.vision_model
    reel.tokens = tokens
    log.info("%s: [text/%s] genre=%s, %d facts, %d tags", reel.id, used,
             reel.genre, len(reel.facts), len(reel.tags))
    return reel
