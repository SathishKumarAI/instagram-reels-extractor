"""Core data model: one Reel flows through every pipeline stage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class Fact(BaseModel):
    """One verifiable claim extracted from the reel, with provenance.

    timestamp + frame point back to exactly where in the clip the fact came from
    — scrub the reel to that second to verify. Anti-hallucination by construction.
    """

    text: str
    timestamp: float | None = None  # seconds into the reel
    frame: int | None = None        # sampled-frame index it was read from


class Reel(BaseModel):
    """Single reel; extractors fill fields, renderers consume them."""

    # identity / ingest
    id: str
    url: str
    author: str = ""              # display name, e.g. "Bharat Aanjna ( HINDIAN )"
    author_handle: str = ""       # @username — the only form IG's API accepts
    title: str = ""

    timestamp: datetime | None = None

    # metadata
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    likes: int | None = None
    views: int | None = None
    comments: int | None = None
    duration: float | None = None

    # media paths (relative to data_dir)
    video_path: str | None = None
    thumbnail_path: str | None = None
    audio_path: str | None = None

    # extracted text
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    transcript_text: str = ""
    transcript_language: str = ""          # detected source language (ISO code, e.g. "hi")
    transcript_translated: bool = False    # True when translated to English from another language
    transcript_confidence: float | None = None  # whisper language-detection probability [0..1]
    ocr_text: list[str] = Field(default_factory=list)
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)   # actionable takeaways
    on_screen_text: list[str] = Field(default_factory=list)  # verbatim overlay text
    genre: str = ""                                       # tutorial|product|educational|...
    tags: list[str] = Field(default_factory=list)         # topical tags for search/filter
    structured: dict[str, Any] = Field(default_factory=dict)  # genre-specific typed fields
    facts: list[Fact] = Field(default_factory=list)      # claims with provenance
    # vision usage {input, cache_read, output, cost_usd} + provenance {backend, model}
    tokens: dict[str, Any] = Field(default_factory=dict)
    # one entry per backend that has ever summarised this reel, keyed by backend name
    # ("claude-cli", "local", …): {summary, genre, tags, structured, facts, tokens,
    # elapsed_s, created_at}. The top-level fields above stay the ACTIVE variant so
    # nothing downstream needs to know this exists.
    variants: dict[str, Any] = Field(default_factory=dict)

    # render outputs
    markdown_path: str | None = None
    pdf_path: str | None = None

    scraped_at: datetime | None = None

    @property
    def slug(self) -> str:
        return self.id

    def json_path(self, data_dir: Path) -> Path:
        return data_dir / f"{self.id}.json"

    def save(self, data_dir: Path) -> Path:
        p = self.json_path(data_dir)
        # explicit utf-8: captions carry emoji and non-Latin text, and Windows
        # defaults to cp1252, which cannot even read back what it wrote
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: Path) -> Reel:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
