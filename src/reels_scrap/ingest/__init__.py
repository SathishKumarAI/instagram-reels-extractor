"""Ingest stage: turn a source into a list of Reel objects with media downloaded."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import Config
from ..models import Reel
from ..observability import log

# accept instagram reel/post/tv permalinks only
_REEL_URL_RE = re.compile(
    r"^https?://(www\.)?instagram\.com/(reel|reels|p|tv)/[A-Za-z0-9_-]+/?", re.I
)


def ingest(cfg: Config, failures: dict[str, tuple[str, str]] | None = None) -> list[Reel]:
    """Dispatch to the right ingester based on config.source.type.

    `failures`, if given, is populated with {reel_id: (url, error)} for any
    source that could not be downloaded — so the caller can record dropped
    URLs in the run report instead of losing them.
    """
    stype = cfg.source.type
    if stype == "urls":
        from .ytdlp import ingest_urls

        return ingest_urls(cfg, failures)
    if stype in {"profile", "hashtag", "saved"}:
        from .instaloader_src import ingest_instaloader

        return ingest_instaloader(cfg, failures)
    raise ValueError(f"Unknown source.type: {stype!r}")


def read_urls_file(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"urls_file not found: {p}")
    out, bad = [], []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if _REEL_URL_RE.match(line):
            out.append(line)
        else:
            bad.append(line)
    if bad:
        log.warning("skipping %d invalid reel URL(s): %s", len(bad), ", ".join(bad[:3]))
    if not out:
        raise ValueError(f"no valid Instagram reel URLs in {p}")
    return out
