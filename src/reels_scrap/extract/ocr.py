"""On-screen text via easyocr on sampled frames. Deduped."""

from __future__ import annotations

import threading

from ..config import Config
from ..models import Reel
from .frames import sample_frames

_READER = None
_READER_LOCK = threading.Lock()


def _get_reader():
    global _READER
    with _READER_LOCK:  # serialize load under parallel workers
        if _READER is None:
            import easyocr

            _READER = easyocr.Reader(["en"], gpu=False)
    return _READER


def order_detections(detections):
    """Order one frame's (bbox, text, conf) tuples into reading order.

    Pure: returns a new list, leaves the input untouched, and imports no
    third-party packages (bbox = four [x, y] corner points, list or numpy).
    Detections whose vertical centres fall within half the frame's median
    text height join as one visual line, so a few pixels of y-jitter
    doesn't split a line; lines come out top to bottom, left to right
    inside a line.
    """
    if not detections:
        return list(detections)

    heights = []
    items = []
    for det in detections:
        xs = [float(p[0]) for p in det[0]]
        ys = [float(p[1]) for p in det[0]]
        heights.append(max(ys) - min(ys))
        # bbox centre: x ranks left-to-right within a line, y between lines
        items.append((sum(xs) / len(xs), (min(ys) + max(ys)) / 2.0, det))

    median_h = sorted(heights)[len(heights) // 2]
    line_tol = median_h / 2.0  # same-line y-jitter band, in pixels

    lines = []
    for cx, cy, det in sorted(items, key=lambda it: (it[1], it[0])):
        if lines and cy - lines[-1][0] <= line_tol:
            lines[-1][1].append((cx, det))
        else:
            lines.append((cy, [(cx, det)]))

    ordered = []
    for line in lines:
        ordered.extend(det for _cx, det in sorted(line[1], key=lambda m: m[0]))
    return ordered


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
        # detail=1 -> (bbox, text, confidence); reading order, then filter
        # low-confidence garbage
        for _bbox, text, conf in order_detections(reader.readtext(str(fp), detail=1)):
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
