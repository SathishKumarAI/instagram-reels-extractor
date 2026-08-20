"""Asking the corpus things: semantic search, RAG chat, aggregated knowledge.

All three need the embedding index. Missing index is a 409 with what to run, not
a 500 — it is a state you get into by syncing before extracting, not a bug.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...config import Config
from ..deps import hits
from ..schemas import Answer, ChatRequest, Knowledge, SearchHit


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/knowledge", response_model=Knowledge)
    def knowledge(rebuild: bool = False) -> Knowledge:
        from ...knowledge import load_knowledge

        return load_knowledge(cfg, rebuild=rebuild)

    @router.get("/api/search", response_model=list[SearchHit])
    def search(q: str, k: int = 8) -> list[SearchHit]:
        from ...search import search as do_search

        try:
            rows = do_search(cfg, q, k)
        except FileNotFoundError as e:
            raise HTTPException(409, "no search index — run extraction first") from e
        return hits(cfg, rows)

    @router.post("/api/chat", response_model=Answer)
    def chat(req: ChatRequest) -> Answer:
        from ...chat import answer_question

        try:
            return answer_question(cfg, req.question, k=req.k, history=req.history)
        except FileNotFoundError as e:
            raise HTTPException(409, "no search index — run extraction first") from e

    return router
