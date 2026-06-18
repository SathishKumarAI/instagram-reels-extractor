"""Pydantic schemas = the backend↔frontend contract."""

from __future__ import annotations

from pydantic import BaseModel

from ..chat.rag import Answer  # re-exported as the /chat response
from ..knowledge.aggregate import Knowledge  # re-exported as /knowledge response


class ReelSummary(BaseModel):
    id: str
    title: str
    author: str = ""
    genre: str = ""
    url: str
    thumbnail_path: str | None = None
    likes: int | None = None
    views: int | None = None
    comments: int | None = None
    duration: float | None = None
    has_pdf: bool = False


class SearchHit(BaseModel):
    reel_id: str
    title: str
    url: str
    kind: str
    text: str
    score: float
    timestamp: float | None = None


class ChatRequest(BaseModel):
    question: str
    k: int = 8
    history: list[dict] = []


__all__ = ["ReelSummary", "SearchHit", "ChatRequest", "Answer", "Knowledge"]
