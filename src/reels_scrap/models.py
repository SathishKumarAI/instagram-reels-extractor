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
    author: str = ""
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
    ocr_text: list[str] = Field(default_factory=list)
    summary: str = ""
    genre: str = ""                                       # tutorial|product|educational|...
    structured: dict[str, Any] = Field(default_factory=dict)  # genre-specific typed fields
    facts: list[Fact] = Field(default_factory=list)      # claims with provenance

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
        p.write_text(self.model_dump_json(indent=2))
        return p

    @classmethod
    def load(cls, path: Path) -> "Reel":
        return cls.model_validate_json(path.read_text())
