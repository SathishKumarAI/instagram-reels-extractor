"""On-screen text via easyocr on sampled frames. Deduped."""

from __future__ import annotations

from ..config import Config
from ..models import Reel
from .frames import sample_frames

import threading

_READER = None
_READER_LOCK = threading.Lock()


def _get_reader():
    global _READER
    with _READER_LOCK:  # serialize load under parallel workers
        if _READER is None:
            import easyocr

            _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


def add_ocr(reel: Reel, cfg: Config) -> Reel:
    if not reel.video_path:
        return reel
    data_dir = cfg.data_dir
    video = data_dir / reel.video_path
    if not video.exists():
        return reel

    frames_dir = data_dir / f"{reel.id}_frames"
    frames = sample_frames(video, frames_dir, cfg.extract.frame_every_sec)
    reader = _get_reader()

    seen: set[str] = set()
    ordered: list[str] = []
    min_conf = cfg.extract.ocr_min_confidence
    for fp in frames:
        # detail=1 -> (bbox, text, confidence); filter low-confidence garbage
        for _bbox, text, conf in reader.readtext(str(fp), detail=1):
            t = text.strip()
            key = t.lower()
            # keep confident, reasonably-long, alphanumeric-bearing lines
            if (
                conf >= min_conf
                and len(t) >= 3
                and any(c.isalnum() for c in t)
                and key not in seen
            ):
                seen.add(key)
                ordered.append(t)
    reel.ocr_text = ordered
    return reel
