"""Everything the model is TOLD. One file, so tuning the prompt is one small edit.

Owns: the output schema, the per-backend nudges, and how a reel's caption and
transcript are assembled into the message. Owns no HTTP, no parsing, no reel
mutation — `vision.py` calls the backends, `normalise.py` reads their answers.

Which text goes to which backend:
  every backend   SCHEMA_INSTRUCTION + `_prompt_header` (caption + transcript)
  local only      + LOCAL_NUDGE — a 7B reads "3-8 facts" as "3" and needs the
                  floors spelled out; Claude already fills the schema and a
                  shorter prompt is a cheaper prompt there.
  two-pass only   READ_PROMPT for the transcribe pass.
"""

from __future__ import annotations

import re

from ..models import Reel

GENRES = ["tutorial", "product", "educational", "recipe", "news", "entertainment", "other"]

CAPTION_CHARS = 1200
TRANSCRIPT_CHARS = 2500

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


READ_PROMPT = (
    "Read these frames from a short video, in order. For EACH frame output one line:\n"
    "`Frame <i> (<t>s): <every piece of text visible in that frame, verbatim>` — then, "
    "after a `|`, a short description of what is happening in the image.\n"
    "Transcribe text exactly as written, including numbers, handles, URLs and prices. "
    "Write `(no text)` when a frame has none. Output nothing else."
)


def caption_for_prompt(caption: str) -> str:
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


def prompt_header(reel: Reel) -> str:
    """What the model is told about the reel, besides the frames.

    The transcript belongs here. The schema asks for facts grounded "in a frame or
    in the spoken transcript", but the transcript was never sent — 527 of 674 reels
    have one, and the model was being asked to ground claims in text it could not
    see. Frames show what is written; the transcript is what is said, and for a
    talking-head reel that is most of the substance.
    """
    parts = [
        "These are frames sampled in order from a short Instagram reel.\n",
        f"Caption: {caption_for_prompt(reel.caption)}\n",
    ]
    spoken = (reel.transcript_text or "").strip()
    if spoken:
        parts.append(
            f"\nWhat is said in the reel (transcript{', translated' if reel.transcript_translated else ''}):\n"
            f"{spoken[:TRANSCRIPT_CHARS]}{'… [trimmed]' if len(spoken) > TRANSCRIPT_CHARS else ''}\n"
        )
    parts.append(f"\n{SCHEMA_INSTRUCTION}\n")
    return "".join(parts)
