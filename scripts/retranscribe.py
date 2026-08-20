#!/usr/bin/env python3
"""Re-run ONLY the transcript stage over already-downloaded reels.

Applies the current config (auto-detect + translate) to fix garbled non-English
transcripts and populate the new transcript_language / _translated / _confidence
fields — without touching vision/OCR (which need heavier deps). Re-renders the
consolidated docs at the end so the ⚠ translated badges appear.

    PYTHONPATH=src .venv/bin/python scripts/retranscribe.py [config.yaml]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reels_scrap.config import Config
from reels_scrap.docs import rebuild_all
from reels_scrap.extract.transcript import add_transcript
from reels_scrap.models import Reel


def main() -> None:
    cfg = Config.load(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
    paths = sorted(p for p in cfg.data_dir.glob("*.json") if p.stem != "DEMO123")
    print(f"re-transcribing {len(paths)} reels (translate={cfg.extract.whisper_translate})…")
    changed = translated = 0
    for p in paths:
        reel = Reel.load(p)
        before = reel.transcript_text
        add_transcript(reel, cfg)
        reel.save(cfg.data_dir)
        tag = ""
        if reel.transcript_translated:
            translated += 1
            tag = f"  ⚠ {reel.transcript_language}→en (p={reel.transcript_confidence:.2f})"
        if reel.transcript_text != before:
            changed += 1
        print(f"  {reel.id}: {len(reel.transcript_text)} chars{tag}")
    print(f"\n{changed} transcripts changed, {translated} translated from another language")
    docs, index = rebuild_all(cfg)
    print(f"rebuilt {len(docs)} doc(s) + index → {index}")


if __name__ == "__main__":
    main()
