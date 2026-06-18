"""Aggregate the reel corpus into topics for the Knowledge Base.

Pure, deterministic, cheap: read every per-reel JSON record, group by genre
(the structured-vision classification), and collect each group's summaries,
provenance facts, top hashtags, and source-reel refs. Optional per-topic Claude
synthesis lives in `synthesize.py` and is layered on top — never required here.

Result is cached to `output/knowledge/knowledge.json` so the API serves it
instantly and only rebuilds when reels change.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from ..config import Config
from ..models import Reel
from ..observability import log


class TopicReel(BaseModel):
    id: str
    title: str
    url: str
    author: str = ""
    summary: str = ""
    thumbnail_path: str | None = None


class TopicFact(BaseModel):
    reel_id: str
    text: str
    timestamp: float | None = None


class Topic(BaseModel):
    name: str                       # the genre / topic key
    reel_count: int
    hashtags: list[str] = []        # most common hashtags in the group
    overview: str = ""              # optional Claude synthesis (synthesize.py)
    reels: list[TopicReel] = []
    facts: list[TopicFact] = []


class Knowledge(BaseModel):
    total_reels: int
    topics: list[Topic]


def _load_reels(cfg: Config) -> list[Reel]:
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


def knowledge_path(cfg: Config) -> Path:
    return cfg.knowledge_dir / "knowledge.json"


def build_knowledge(cfg: Config, max_facts_per_topic: int = 40) -> Knowledge:
    """Group reels by genre into topics; cache to output/knowledge/knowledge.json."""
    reels = _load_reels(cfg)
    groups: dict[str, list[Reel]] = {}
    for r in reels:
        key = (r.genre or "uncategorized").strip().lower()
        groups.setdefault(key, []).append(r)

    topics: list[Topic] = []
    for name, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        tags = Counter(h.lower() for m in members for h in m.hashtags)
        facts: list[TopicFact] = []
        for m in members:
            for f in m.facts:
                facts.append(TopicFact(reel_id=m.id, text=f.text, timestamp=f.timestamp))
        topics.append(
            Topic(
                name=name,
                reel_count=len(members),
                hashtags=[t for t, _ in tags.most_common(10)],
                reels=[
                    TopicReel(
                        id=m.id,
                        title=m.title or m.id,
                        url=m.url,
                        author=m.author,
                        summary=m.summary,
                        thumbnail_path=m.thumbnail_path,
                    )
                    for m in members
                ],
                facts=facts[:max_facts_per_topic],
            )
        )

    kb = Knowledge(total_reels=len(reels), topics=topics)
    knowledge_path(cfg).write_text(kb.model_dump_json(indent=2))
    log.info("knowledge: %d topics over %d reels", len(topics), len(reels))
    return kb


def load_knowledge(cfg: Config, rebuild: bool = False) -> Knowledge:
    """Return cached knowledge, building it if missing or rebuild=True."""
    p = knowledge_path(cfg)
    if rebuild or not p.exists():
        return build_knowledge(cfg)
    return Knowledge.model_validate_json(p.read_text())
