"""Give every reel a `local` variant, without touching its active record.

Why a variant and not a re-extract: the corpus already carries Claude summaries,
and the Compare scoreboard says local is thinner (fewer structured fields, shorter
summaries). Overwriting would be a downgrade. Storing local alongside gives a
full-corpus comparison, a $0 copy of every record, and a fallback if the Claude
path is ever unavailable — while the active fields stay as they are.

    python scripts/backfill_local_variants.py [--limit N] [--redo]

Resumable: reels that already have a `local` variant are skipped unless --redo.
"""

from __future__ import annotations

import argparse
import time

from reels_scrap.config import Config
from reels_scrap.extract.vision import run_variant
from reels_scrap.models import Reel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-local.yaml")
    ap.add_argument("--limit", type=int, default=0, help="0 = every reel")
    ap.add_argument("--redo", action="store_true", help="re-run reels that already have one")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    base = Config.load("config.yaml")          # data_dir of the real corpus
    paths = sorted(base.data_dir.glob("*.json"))

    todo = []
    for p in paths:
        r = Reel.load(p)
        if not r.video_path or not (base.data_dir / r.video_path).exists():
            continue
        if not args.redo and "local" in (r.variants or {}):
            continue
        todo.append(p)
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(paths)} reels, {len(todo)} to process")
    ok = failed = 0
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        r = Reel.load(p)
        try:
            v = run_variant(r, cfg, "local")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(todo)}] {r.id} FAILED: {str(e)[:110]}")
            continue
        r = Reel.load(p)                        # re-read: the run took seconds
        r.variants = {**(r.variants or {}), "local": v}
        r.save(base.data_dir)
        ok += 1
        if i % 10 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            left = (len(todo) - i) * rate
            print(f"  [{i}/{len(todo)}] ok={ok} failed={failed} "
                  f"{rate:.1f}s/reel, ~{left/60:.0f} min left")
    print(f"done: {ok} ok, {failed} failed in {(time.time()-t0)/60:.1f} min")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
