"""Reading a model's answer: parse the JSON, clean the fields, write the reel.

Owns everything between "the backend returned text" and "the Reel is filled in" —
JSON salvage, tag/structured normalisation, fact hygiene. Owns no prompt text
(`prompts.py`) and no HTTP (`vision.py`).

Every rule here exists because a model got something honestly-but-differently
right: nested `structured`, bare-string facts, lower-case claims, subtitle
fragments. Normalise rather than argue — otherwise the pipeline reports a model
as having found nothing when it only answered in another shape.
"""

from __future__ import annotations

import json
import re

from ..models import Fact, Reel
from ..observability import log
from .prompts import GENRES


def parse_json(text: str) -> dict:
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


def norm_tags(raw) -> list[str]:
    """Lowercase, hyphenate, de-dupe tags; drop empties. Cap at 8."""
    out: list[str] = []
    for t in raw or []:
        s = re.sub(r"\s+", "-", str(t).strip().lower())
        s = re.sub(r"[^a-z0-9-]", "", s).strip("-")
        if s and s not in out:
            out.append(s)
    return out[:8]


def unwrap_structured(structured, genre: str) -> dict:
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


def is_fragment(text: str) -> bool:
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


def dedupe_facts(facts: list[Fact]) -> list[Fact]:
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


def strip_subtitles(lines: list[str], transcript: str) -> list[str]:
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


def apply(reel: Reel, data: dict) -> None:
    """Write one parsed model answer onto the reel, normalised."""
    reel.genre = str(data.get("genre", "") or "")
    reel.summary = str(data.get("summary", "") or "")
    reel.key_points = [str(k).strip() for k in (data.get("key_points") or []) if str(k).strip()][:8]
    reel.on_screen_text = strip_subtitles(
        [str(s).strip() for s in (data.get("on_screen_text") or []) if str(s).strip()],
        reel.transcript_text or "",
    )[:20]
    reel.tags = norm_tags(data.get("tags"))
    reel.structured = unwrap_structured(data.get("structured"), reel.genre)
    facts = []
    for f in data.get("facts", []) or []:
        # smaller models answer `"facts": ["…", "…"]` — a claim without its frame.
        # Dropping those silently would count a model as having found nothing when
        # it only failed to ground what it found.
        if isinstance(f, str):
            f = {"text": f}
        if not isinstance(f, dict) or not f.get("text"):
            continue
        if is_fragment(str(f["text"])):
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
    reel.facts = dedupe_facts(facts)
