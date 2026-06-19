"""RAG: retrieve top-k reels/facts, synthesise a cited answer via Claude.

Flow: embed question -> search index -> build [id]-tagged context -> claude_text
-> map [id] cites back to reel metadata. On LLM failure, degrade gracefully:
return the retrieved sources with answer=None and a note (same resilience policy
as the vision stage).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from ..config import Config
from ..llm import LLMError, claude_text
from ..observability import log
from ..search import search as semantic_search
from .prompts import build_prompt


class Citation(BaseModel):
    reel_id: str
    title: str
    url: str
    score: float
    snippet: str
    timestamp: float | None = None


class Answer(BaseModel):
    answer: str | None                # None when synthesis unavailable
    citations: list[Citation]
    note: str | None = None           # set when degraded (e.g. LLM unavailable)


_CITE_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")


def answer_question(
    cfg: Config,
    question: str,
    k: int = 8,
    history: list[dict] | None = None,
) -> Answer:
    """Answer a research question from the reel archive, with citations."""
    matches = semantic_search(cfg, question, k=k)
    # de-dupe sources by reel for the prompt, keep best snippet each
    by_reel: dict[str, dict] = {}
    for m in matches:
        rid = m["reel_id"]
        if rid not in by_reel:
            by_reel[rid] = m
    sources = [
        {"reel_id": m["reel_id"], "title": m["title"], "text": m["text"]}
        for m in by_reel.values()
    ]

    # one citation per reel (best-scoring match), preserving rank order
    citations: list[Citation] = []
    seen_cite: set[str] = set()
    for m in matches:
        if m["reel_id"] in seen_cite:
            continue
        seen_cite.add(m["reel_id"])
        citations.append(
            Citation(
                reel_id=m["reel_id"], title=m["title"], url=m["url"],
                score=m["score"], snippet=m["text"][:300], timestamp=m.get("timestamp"),
            )
        )

    if not sources:
        return Answer(answer=None, citations=[], note="archive is empty — run extraction first")

    prompt = build_prompt(question, sources, history)
    try:
        text = claude_text(
            prompt,
            backend=cfg.extract.vision_backend,
            model=cfg.extract.vision_model,
        )
    except LLMError as e:
        log.warning("chat: synthesis unavailable: %s", e)
        return Answer(answer=None, citations=citations, note=f"synthesis unavailable: {e}")

    # keep only citations the model actually referenced, when it cited any
    cited_ids = set(_CITE_RE.findall(text))
    if cited_ids:
        used = [c for c in citations if c.reel_id in cited_ids]
        if used:
            citations = used
    return Answer(answer=text, citations=citations)
