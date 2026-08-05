"""Transcribe every reel that has none, on the GPU.

89.5% of the corpus had no spoken text captured — the single biggest cause of vague
summaries. Whisper large-v3 batched runs ~12x realtime on an RTX 5070 Ti, so the
whole corpus is well under an hour.

    python scripts/backfill_transcripts.py [--limit N] [--redo]

Resumable: reels that already have transcript text are skipped unless --redo.
Re-running vision afterwards is what turns the transcript into better summaries —
see scripts/backfill_local_variants.py.
"""

from __future__ import annotations

import argparse
import time

from reels_scrap.config import Config
from reels_scrap.extract.transcript import add_transcript
from reels_scrap.models import Reel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-local.yaml")
    ap.add_argument("--limit", type=int, default=0, help="0 = every reel")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--model", default="", help="override whisper_model")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    cfg.extract.transcript = True
    if args.model:
        cfg.extract.whisper_model = args.model

    base = Config.load("config.yaml")
    todo = []
    skipped_no_video = 0
    for p in sorted(base.data_dir.glob("*.json")):
        r = Reel.load(p)
        if not r.video_path or not (base.data_dir / r.video_path).exists():
            skipped_no_video += 1
            continue
        if not args.redo and (r.transcript_text or "").strip():
            continue
        todo.append(p)
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(todo)} reel(s) to transcribe "
          f"({skipped_no_video} have no video file), model={cfg.extract.whisper_model}")
    ok = empty = failed = 0
    audio_secs = 0.0
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        r = Reel.load(p)
        try:
            add_transcript(r, cfg)
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(todo)}] {r.id} FAILED: {str(e)[:120]}")
            continue
        if (r.transcript_text or "").strip():
            ok += 1
        else:
            empty += 1          # music-only or silent reel — legitimate
        audio_secs += r.duration or 0
        r.save(base.data_dir)
        if i % 20 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"  [{i}/{len(todo)}] ok={ok} silent={empty} failed={failed} "
                  f"· {audio_secs/max(el,1):.1f}x realtime · ~{(len(todo)-i)*el/i/60:.0f} min left")
    el = time.time() - t0
    print(f"done: {ok} transcribed, {empty} silent, {failed} failed in {el/60:.1f} min "
          f"({audio_secs/max(el,1):.1f}x realtime)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
