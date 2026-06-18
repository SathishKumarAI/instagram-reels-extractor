"""Optional per-topic overview via Claude — layered on top of aggregate.py.

Cost lever: one LLM call per topic. OFF by default; enabled via flag/config.
Cached into each topic so it only regenerates when the member set changes.
"""

from __future__ import annotations

from ..config import Config
from ..llm import LLMError, claude_text
from ..observability import log
from .aggregate import Knowledge, knowledge_path

PROMPT = (
    "You are a research assistant. Below are factual notes extracted from several "
    "short videos on the topic '{topic}'. Write a concise 2-4 sentence overview of "
    "what this topic collectively covers — synthesise, do not list. Use ONLY the "
    "notes; do not invent.\n\nNotes:\n{notes}\n\nOverview:"
)


def synthesize_topics(cfg: Config, kb: Knowledge, max_notes: int = 30) -> Knowledge:
    """Fill each topic's `overview` via the configured text backend. Best-effort."""
    backend = cfg.extract.vision_backend  # reuse the same backend choice
    for topic in kb.topics:
        notes = "\n".join(f"- {f.text}" for f in topic.facts[:max_notes])
        if not notes:
            continue
        prompt = PROMPT.format(topic=topic.name, notes=notes)
        try:
            topic.overview = claude_text(prompt, backend=backend, model=cfg.extract.vision_model)
            log.info("knowledge: synthesised overview for '%s'", topic.name)
        except LLMError as e:
            log.warning("knowledge: overview skipped for '%s': %s", topic.name, e)
    knowledge_path(cfg).write_text(kb.model_dump_json(indent=2))
    return kb
