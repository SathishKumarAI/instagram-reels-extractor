"""Pydantic schemas = the backend↔frontend contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from ..chat.rag import Answer  # re-exported as the /chat response
from ..knowledge.aggregate import Knowledge  # re-exported as /knowledge response


class ReelSummary(BaseModel):
    id: str
    title: str
    author: str = ""
    genre: str = ""
    tags: list[str] = []
    collections: list[str] = []   # saved-collection slugs this reel belongs to
    url: str
    thumbnail_path: str | None = None
    likes: int | None = None
    views: int | None = None
    comments: int | None = None
    duration: float | None = None
    timestamp: datetime | None = None
    has_pdf: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    backend: str = ""      # vision provenance: claude-cli | api | local | local->claude-cli
    starred: bool = False
    read: bool = False
    archived: bool = False


class CategoryStat(BaseModel):
    genre: str
    reels: int
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0


class Stats(BaseModel):
    total_reels: int
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0          # estimated (see note); 0 on subscription/claude-cli reality
    cost_note: str = ""
    categories: list[CategoryStat]
    top_tags: list[list]  # [tag, count] pairs


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


__all__ = ["ReelSummary", "CategoryStat", "Stats", "SearchHit", "ChatRequest", "Answer", "Knowledge"]
