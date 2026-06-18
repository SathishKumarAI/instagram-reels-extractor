"""RAG tests with search + LLM mocked (no fastembed, no Claude)."""

from __future__ import annotations

import reels_scrap.chat.rag as rag
from reels_scrap.llm import LLMError

HITS = [
    {"reel_id": "AAA", "title": "Homelab repos", "url": "https://insta/reel/AAA/",
     "kind": "fact", "text": "coolify is a self-hostable Heroku alternative", "score": 0.82, "timestamp": 10.0},
    {"reel_id": "AAA", "title": "Homelab repos", "url": "https://insta/reel/AAA/",
     "kind": "reel", "text": "Self-hosting GitHub repos.", "score": 0.71, "timestamp": None},
]


def test_answer_with_citations(cfg, monkeypatch):
    monkeypatch.setattr(rag, "semantic_search", lambda c, q, k=8: HITS)
    monkeypatch.setattr(rag, "claude_text", lambda *a, **k: "Coolify self-hosts apps [AAA].")
    ans = rag.answer_question(cfg, "what is coolify?")
    assert ans.answer and "Coolify" in ans.answer
    assert [c.reel_id for c in ans.citations] == ["AAA"]  # deduped to one per reel
    assert ans.note is None


def test_fallback_when_llm_unavailable(cfg, monkeypatch):
    monkeypatch.setattr(rag, "semantic_search", lambda c, q, k=8: HITS)
    def boom(*a, **k):
        raise LLMError("claude CLI failed")
    monkeypatch.setattr(rag, "claude_text", boom)
    ans = rag.answer_question(cfg, "what is coolify?")
    assert ans.answer is None
    assert ans.citations  # sources still returned
    assert "unavailable" in (ans.note or "")


def test_empty_archive(cfg, monkeypatch):
    monkeypatch.setattr(rag, "semantic_search", lambda c, q, k=8: [])
    ans = rag.answer_question(cfg, "anything?")
    assert ans.answer is None and ans.citations == []
