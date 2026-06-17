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

    if e.transcript:
        try:
            from .transcript import add_transcript

            add_transcript(reel, cfg)
        except Exception as ex:  # noqa: BLE001
            log.error("transcript failed %s: %s", reel.id, ex)
            errors["transcript"] = str(ex)

    if e.ocr:
        try:
            from .ocr import add_ocr

            add_ocr(reel, cfg)
        except Exception as ex:  # noqa: BLE001
            log.error("ocr failed %s: %s", reel.id, ex)
            errors["ocr"] = str(ex)

    if e.vision:
        try:
            from .vision import add_summary

            add_summary(reel, cfg)
        except Exception as ex:  # noqa: BLE001
            log.error("vision failed %s: %s", reel.id, ex)
            errors["vision"] = str(ex)

    reel.save(cfg.data_dir)
    return errors
