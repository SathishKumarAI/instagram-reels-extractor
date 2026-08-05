"""Extract stage: fill Reel text fields per config toggles."""

from __future__ import annotations

from ..config import Config
from ..models import Reel
from ..observability import log


def extract_all(reel: Reel, cfg: Config) -> dict[str, str]:
    """Run each enabled extractor on one reel. Independent + guarded.

    Returns {stage: error_message} for stages that failed (empty = all ok).
    """
    e = cfg.extract
    errors: dict[str, str] = {}
    # caption/metadata already populated at ingest; nothing to do if only caption.
    # Text records (RSS/arXiv/GitHub) have no video → structure their text instead
    # of running audio/frame extractors.
    is_text = not reel.video_path and bool(reel.caption or reel.transcript_text)

    if e.transcript and not is_text:
        try:
            from .transcript import add_transcript

            add_transcript(reel, cfg)
        except Exception as ex:
            log.error("transcript failed %s: %s", reel.id, ex)
            errors["transcript"] = str(ex)

    if e.ocr and not is_text:
        try:
            from .ocr import add_ocr

            add_ocr(reel, cfg)
        except Exception as ex:
            log.error("ocr failed %s: %s", reel.id, ex)
            errors["ocr"] = str(ex)

    # `vision` toggle drives structuring for BOTH kinds: frames for reels, text
    # for feed records — same schema + backend, so results are interchangeable.
    if e.vision and is_text:
        try:
            from ..ratelimit import vision_semaphore, with_retry
            from .text_summary import add_text_summary

            with vision_semaphore(e.vision_concurrency):
                with_retry(lambda: add_text_summary(reel, cfg),
                           attempts=e.vision_max_retries, backoff=e.vision_retry_backoff,
                           label=f"text {reel.id}")
        except Exception as ex:
            log.error("text-structure failed %s: %s", reel.id, ex)
            errors["text"] = str(ex)
    elif e.vision:
        try:
            from ..ratelimit import vision_semaphore, with_retry
            from .vision import add_summary

            # Gate vision to a small global concurrency + retry/backoff: parallel
            # `claude -p` calls throttle. Transcript/OCR above stay parallel.
            sem = vision_semaphore(e.vision_concurrency)
            with sem:
                with_retry(
                    lambda: add_summary(reel, cfg),
                    attempts=e.vision_max_retries,
                    backoff=e.vision_retry_backoff,
                    label=f"vision {reel.id}",
                )
        except Exception as ex:
            log.error("vision failed %s: %s", reel.id, ex)
            errors["vision"] = str(ex)

    reel.save(cfg.data_dir)
    return errors
