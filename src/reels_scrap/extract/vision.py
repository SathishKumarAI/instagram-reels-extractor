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
from datetime import UTC

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
    '  "summary": "3-5 sentences. What the reel actually teaches or claims — the '
    "substance, not a description of the video. Name the specific tools, people, "
    'numbers and steps involved.",\n'
    '  "key_points": ["3-6 takeaways someone could act on, one line each"],\n'
    '  "on_screen_text": ["title cards, labels, list items, prices, URLs and handles '
    "rendered ON the video, quoted verbatim. NOT the subtitle/caption stream of what "
    'is being said."],\n'
    '  "tags": ["3-6 short lowercase topical tags for search/filter, e.g. '
    '\\"machine-learning\\", \\"resume-tips\\", \\"open-source\\"],\n'
    '  "structured": { genre-appropriate fields, FLAT (do not nest under the genre). '
    'e.g. tutorial -> {"tools":[],"commands":[],"links":[],"steps":[]}; '
    'product -> {"name":"","price":"","link":"","claims":[]}; '
    'recipe -> {"ingredients":[],"steps":[],"time":""}; '
    'educational -> {"topic":"","key_concepts":[],"resources":[]} },\n'
    '  "facts": [ {"text":"one complete, self-contained claim", '
    '"frame": <frame index int>, "timestamp": <seconds number>} ]\n'
    "}\n"
    "Rules: 3-8 facts. Every fact MUST be a COMPLETE statement that stands on its own "
    "— never a sentence fragment copied from a moving subtitle line "
    '(bad: "years now and", "so here are"; good: "The Microsoft Web-Dev-For-Beginners '
    'curriculum runs 12 weeks over 24 lessons"). Ground each fact in a frame or in the '
    "spoken transcript and set frame/timestamp accordingly. "
    "Do NOT invent prices, names, or numbers you cannot read or hear."
)


# A 7B model treats "3-8 facts" as "3" and writes one-clause summaries, so the
# local backend gets the floor spelled out. Not added to the Claude prompt — it
# already fills the schema, and a shorter prompt is a cheaper prompt there.
LOCAL_NUDGE = (
    "\nIMPORTANT — every one of these fields is REQUIRED and must be non-empty:\n"
    "- `summary`: at least 3 full sentences naming the specific tools, numbers and steps.\n"
    "- `key_points`: at least 3 one-line takeaways someone could act on.\n"
    "- `on_screen_text`: every title card, list item, label, price, URL or @handle you "
    "can read in the frames, quoted verbatim. If a line only repeats what is spoken, "
    "leave it out — that is a subtitle, not overlay text.\n"
    "- `facts`: at least 6 (up to 8), each a COMPLETE sentence. Never a fragment.\n"
    "- `tags`: at least 5.\n"
    "- `structured`: filled with the genre-appropriate fields, flat.\n"
)


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


def _parse_json(text: str) -> dict:
    """Extract the best JSON object from model output, tolerant of fences/prose.

    A reasoning model's reply can hold several objects — a sketch, a correction,
    then the answer. A greedy `\\{.*\\}` spans them all and json.loads reports
    "Extra data"; taking the first gives you the sketch. So decode every object in
    the text and keep the richest one, which is the finished answer.
    """
    text = (text or "").strip()
    # strip ```json ... ``` fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    decoder = json.JSONDecoder()
    best: dict | None = None
    i = text.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(text[i:])
        except ValueError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict) and (best is None or len(obj) >= len(best)):
            best = obj
        i = text.find("{", i + end)
    if best is None:
        raise ValueError(f"no JSON object in model output: {text[:120]!r}")
    return best


def message_text(choice: dict) -> tuple[str, bool]:
    """The text of one OpenAI-style choice, and whether it had to be salvaged.

    A reasoning model (qwen3-vl and friends) puts its draft in `reasoning` and can
    return an empty `content` when the budget runs out mid-thought. Indexing
    `["content"]` blindly turns that into an AttributeError with no clue attached,
    so every caller goes through here.
    """
    msg = (choice or {}).get("message", {}) or {}
    text = (msg.get("content") or "").strip()
    if text:
        return text, False
    salvaged = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
    if salvaged:
        return salvaged, True
    raise RuntimeError(
        f"model returned no content (finish_reason={(choice or {}).get('finish_reason')!r})"
        " — a reasoning model needs a larger max_tokens"
    )


def _norm_tags(raw) -> list[str]:
    """Lowercase, hyphenate, de-dupe tags; drop empties. Cap at 8."""
    out: list[str] = []
    for t in raw or []:
        s = re.sub(r"\s+", "-", str(t).strip().lower())
        s = re.sub(r"[^a-z0-9-]", "", s).strip("-")
        if s and s not in out:
            out.append(s)
    return out[:8]


def _unwrap_structured(structured, genre: str) -> dict:
    """Flatten `{"educational": {...}}` to `{...}`.

    The schema shows `structured` holding genre-appropriate fields; Claude returns
    them flat, local models often nest them under the genre name. Both are honest
    readings of the prompt, so normalise instead of arguing — otherwise the record
    looks like it has 1 field when it has 4, and every consumer has to special-case.
    """
    if not isinstance(structured, dict):
        return {}
    if len(structured) == 1:
        (k, v), = structured.items()
        if isinstance(v, dict) and (k == genre or k in GENRES):
            return v
    return structured


_FRAGMENT_TAILS = (" and", " the", " a", " to", " of", " so", " but", " that", " with")
# words a sliced caption tends to open on — a real claim opens on its subject
_FRAGMENT_HEADS = {
    "the", "a", "an", "and", "but", "so", "or", "of", "to", "that", "this", "these",
    "those", "it", "its", "they", "them", "you", "your", "we", "our", "he", "she",
    "his", "her", "in", "on", "at", "for", "with", "from", "by", "as", "if", "then",
    "because", "when", "while", "which", "who", "what",
}


def _is_fragment(text: str) -> bool:
    """True for a subtitle line caught mid-sentence rather than a real claim.

    Sampling frames every ~8s slices a moving caption at arbitrary points, giving
    "years now and", "clutch", "you'll ever". They are not claims and they poison
    both search and any draft built from the corpus.
    """
    t = text.strip().rstrip(".")
    words = t.split()
    if len(words) < 4:
        return True
    if any(t.lower().endswith(tail) for tail in _FRAGMENT_TAILS):
        return True   # trails off mid-sentence: "aspiring software engineer needs to"
    # A slice that STARTS mid-sentence opens on a function word: "the only way you".
    # Lower case alone is not the signal — several local models write every claim in
    # lower case, and rejecting those counted the model as having found nothing when
    # it had only failed to capitalise.
    return words[0].lower() in _FRAGMENT_HEADS and t[:1].islower()


def _dedupe_facts(facts: list[Fact]) -> list[Fact]:
    """Drop repeats of the same claim read off several frames."""
    out: list[Fact] = []
    seen: list[set[str]] = []
    for f in facts:
        words = {w for w in re.findall(r"[a-z0-9]+", f.text.lower()) if len(w) > 2}
        if any(words and s and len(words & s) / len(words | s) > 0.7 for s in seen):
            continue
        seen.append(words)
        out.append(f)
    return out


def _strip_subtitles(lines: list[str], transcript: str) -> list[str]:
    """Remove overlay lines that are really burned-in subtitles.

    With the transcript in hand this is decidable rather than a guess: if the line
    appears verbatim in what was said, it is the caption of the speech, not overlay
    content. Keeps genuinely short overlays like "no. 1 PROJECT BASED LEARNING",
    which a length rule would wrongly discard.
    """
    if not transcript:
        return lines
    spoken = re.sub(r"[^a-z0-9 ]", " ", transcript.lower())
    spoken = re.sub(r"\s+", " ", spoken)
    out = []
    for line in lines:
        norm = re.sub(r"[^a-z0-9 ]", " ", line.lower())
        norm = re.sub(r"\s+", " ", norm).strip()
        if norm and len(norm.split()) >= 2 and norm in spoken:
            continue
        out.append(line)
    return out


def _apply(reel: Reel, data: dict) -> None:
    reel.genre = str(data.get("genre", "") or "")
    reel.summary = str(data.get("summary", "") or "")
    reel.key_points = [str(k).strip() for k in (data.get("key_points") or []) if str(k).strip()][:8]
    reel.on_screen_text = _strip_subtitles(
        [str(s).strip() for s in (data.get("on_screen_text") or []) if str(s).strip()],
        reel.transcript_text or "",
    )[:20]
    reel.tags = _norm_tags(data.get("tags"))
    reel.structured = _unwrap_structured(data.get("structured"), reel.genre)
    facts = []
    for f in data.get("facts", []) or []:
        # smaller models answer `"facts": ["…", "…"]` — a claim without its frame.
        # Dropping those silently would count a model as having found nothing when
        # it only failed to ground what it found.
        if isinstance(f, str):
            f = {"text": f}
        if not isinstance(f, dict) or not f.get("text"):
            continue
        if _is_fragment(str(f["text"])):
            log.debug("%s: dropped fragment fact %r", reel.id, f["text"])
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
    reel.facts = _dedupe_facts(facts)


CAPTION_CHARS = 1200
TRANSCRIPT_CHARS = 2500


def _caption_for_prompt(caption: str) -> str:
    """The caption, with its hashtags kept even when the body is trimmed.

    Instagram captions end with their hashtags, so a head-only truncation removed
    exactly the part that carries the sponsorship and topic markers — measured on
    the bench sample: 11 of 30 captions ran past the old 500-char cut and 6 lost
    their hashtags with it. Every model was then blamed for missing `#ad`.
    """
    caption = (caption or "").strip()
    if not caption:
        return "(none)"
    if len(caption) <= CAPTION_CHARS:
        return caption
    tags = re.findall(r"#\w+", caption[CAPTION_CHARS:])
    head = caption[:CAPTION_CHARS].rstrip()
    return f"{head}… [trimmed]" + (f"\nHashtags: {' '.join(dict.fromkeys(tags))}" if tags else "")


def _prompt_header(reel: Reel) -> str:
    """What the model is told about the reel, besides the frames.

    The transcript belongs here. The schema asks for facts grounded "in a frame or
    in the spoken transcript", but the transcript was never sent — 527 of 674 reels
    have one, and the model was being asked to ground claims in text it could not
    see. Frames show what is written; the transcript is what is said, and for a
    talking-head reel that is most of the substance.
    """
    parts = [
        "These are frames sampled in order from a short Instagram reel.\n",
        f"Caption: {_caption_for_prompt(reel.caption)}\n",
    ]
    spoken = (reel.transcript_text or "").strip()
    if spoken:
        parts.append(
            f"\nWhat is said in the reel (transcript{', translated' if reel.transcript_translated else ''}):\n"
            f"{spoken[:TRANSCRIPT_CHARS]}{'… [trimmed]' if len(spoken) > TRANSCRIPT_CHARS else ''}\n"
        )
    parts.append(f"\n{SCHEMA_INSTRUCTION}\n")
    return "".join(parts)


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
    content.append({"type": "text", "text": _prompt_header(reel) + LOCAL_NUDGE})

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


READ_PROMPT = (
    "Read these frames from a short video, in order. For EACH frame output one line:\n"
    "`Frame <i> (<t>s): <every piece of text visible in that frame, verbatim>` — then, "
    "after a `|`, a short description of what is happening in the image.\n"
    "Transcribe text exactly as written, including numbers, handles, URLs and prices. "
    "Write `(no text)` when a frame has none. Output nothing else."
)


def _via_local_2pass(reel: Reel, cfg: Config, items) -> tuple[dict, dict]:
    """Read-then-structure. Pass 1 asks the VLM only to transcribe the frames;
    pass 2 is a text-only call that turns those readings into the schema.

    Splitting the job stops a 7B from having to see and reason at once — and pass 2
    cannot invent what it never saw, because it only gets pass 1's text.
    """
    import requests

    lc = cfg.extract.vision_local
    content: list[dict] = []
    for i, t, p in items:
        content.append({"type": "text", "text": f"Frame {i} at {t}s:"})
        b64 = base64.standard_b64encode(p.read_bytes()).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": READ_PROMPT})

    headers = {"Content-Type": "application/json"}
    if lc.api_key:
        headers["Authorization"] = f"Bearer {lc.api_key}"
    r = requests.post(
        lc.base_url.rstrip("/") + "/chat/completions",
        json={"model": lc.model, "messages": [{"role": "user", "content": content}],
              "max_tokens": lc.max_tokens, "temperature": 0},
        headers=headers, timeout=lc.timeout,
    )
    if r.status_code != 200:
        raise RuntimeError(f"local read pass HTTP {r.status_code}: {r.text[:200]}")
    p1 = r.json()
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
    run = _via_local_2pass if e.vision_local_two_pass else _via_local
    for attempt in range(1, e.vision_max_retries + 1):
        try:
            data, tokens = run(reel, cfg, items)
            return data, tokens, "local"
        except Exception as ex:
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


def run_variant(reel: Reel, cfg: Config, backend: str) -> dict:
    """Summarise `reel` with ONE named backend and return the result as a variant.

    Does not touch the reel — the caller decides what to store. This is what the
    Compare tab runs to put two models on the same frames and diff them.
    """
    from datetime import datetime

    items = _frames_with_time(reel, cfg)
    if not items:
        raise RuntimeError(f"{reel.id}: no frames (missing video?)")
    b = _resolve_backend(backend)
    t0 = time.time()
    if b == "local":
        data, tokens, used = _run_local(reel, cfg, items)
    else:
        data, tokens = _BACKENDS[b](reel, cfg, items)
        used = b
    elapsed = round(time.time() - t0, 2)

    # reuse _apply's normalisation by running it on a throwaway copy
    probe = reel.model_copy(deep=True)
    _apply(probe, data)
    tokens = dict(tokens or {})
    tokens["backend"] = used
    tokens["model"] = (
        cfg.extract.vision_local.model if used == "local" else cfg.extract.vision_model
    )
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
