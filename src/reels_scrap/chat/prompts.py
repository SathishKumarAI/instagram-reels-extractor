"""Prompt builder for the research chat (kept separate so it's easy to tune)."""

from __future__ import annotations

SYSTEM = (
    "You are a research assistant answering questions using ONLY an archive of "
    "short videos (Instagram reels). Each source below is tagged with its id like "
    "[abc123]. Answer the question from these sources only. Cite every claim with "
    "the source id in square brackets, e.g. [abc123]. If the archive does not "
    "contain the answer, say exactly: 'Not in the archive.' Be concise and factual."
)


def build_prompt(question: str, sources: list[dict], history: list[dict] | None = None) -> str:
    """sources: [{reel_id, title, text}]; history: [{role, content}]."""
    blocks = []
    for s in sources:
        blocks.append(f"[{s['reel_id']}] {s.get('title','')}\n{s['text']}")
    context = "\n\n".join(blocks) if blocks else "(no sources)"
    convo = ""
    if history:
        convo = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-6:]) + "\n"
    return (
        f"{SYSTEM}\n\n=== SOURCES ===\n{context}\n\n=== CONVERSATION ===\n{convo}"
        f"QUESTION: {question}\n\nANSWER (with [id] citations):"
    )
