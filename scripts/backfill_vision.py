#!/usr/bin/env python3
"""Backfill tags + token usage on reels extracted before those fields existed.

Vision-only (no re-transcribe): re-runs the structured vision pass on every reel
that has a video but is missing `tags` (or `tokens`), then rebuilds docs + index.
Idempotent — skips reels already carrying tags. Run with the CONDA env (needs
ffmpeg for frame sampling); vision uses claude-cli (no API key).

    ~/miniforge3/envs/reels-scrap/bin/python scripts/backfill_vision.py [--all] [--slug topic-research]

--all      re-vision every reel (not just those missing tags)
--slug X   limit to one collection's manifest membership
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reels_scrap.config import Config
from reels_scrap.extract.vision import add_summary
from reels_scrap.models import Reel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-deep.yaml")
    ap.add_argument("--all", action="store_true", help="re-vision even reels that already have tags")
    ap.add_argument("--slug", default="", help="limit to one collection manifest")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel vision calls — keep 1 for claude-cli; api backend can go higher")
    ap.add_argument("--backend", default="auto", choices=["auto", "claude-cli", "api"],
                    help="auto = api if ANTHROPIC_API_KEY set (parallel-safe, ~15x cheaper) else claude-cli")
    ap.add_argument("--max-cost", type=float, default=0.0,
                    help="stop once cumulative vision cost (USD, from CLI/api) exceeds this; 0 = unlimited")
    args = ap.parse_args()

    cfg = Config.load(args.config)

    # backend selection: api (inline images, parallel-safe, cheap) vs claude-cli (no key)
    import os
    backend = args.backend
    if backend == "auto":
        backend = "api" if os.environ.get("ANTHROPIC_API_KEY") else "claude-cli"
    cfg.extract.vision_backend = backend
    workers = args.workers
    if backend == "claude-cli" and workers > 1:
        print("claude-cli throttles on parallel — forcing workers=1 (set ANTHROPIC_API_KEY + --backend api for parallel)")
        workers = 1
    print(f"backend={backend}  workers={workers}  max_frames={cfg.extract.max_frames}")

    ids: list[str] | None = None
    if args.slug:
        from reels_scrap.collections import load_manifest

        m = load_manifest(cfg.output_dir, args.slug)
        if not m:
            print(f"no manifest for slug {args.slug!r}")
            return 1
        ids = m.reel_ids

    paths = (
        [cfg.data_dir / f"{i}.json" for i in ids]
        if ids is not None
        else sorted(cfg.data_dir.glob("*.json"))
    )

    todo, done, failed = [], 0, 0
    for p in paths:
        if not p.exists():
            continue
        r = Reel.load(p)
        if not r.video_path:
            continue
        if not args.all and r.tags:
            continue
        todo.append(r)

    print(f"backfilling vision on {len(todo)} reel(s) with {workers} workers "
          f"(budget: {'$'+str(args.max_cost) if args.max_cost else 'unlimited'})…")

    def _one(r):
        add_summary(r, cfg)
        r.save(cfg.data_dir)
        return r

    spent = 0.0
    stopped = False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_one, r): r for r in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                fut.result()
                done += 1
                spent += float(r.tokens.get("cost_usd", 0.0))
                print(f"  [{n}/{len(todo)}] {r.id}: {len(r.tags)} tags, "
                      f"cost ${r.tokens.get('cost_usd', 0):.3f}, cumulative ${spent:.2f}")
            except Exception as e:
                failed += 1
                print(f"  [{n}/{len(todo)}] {r.id}: FAILED {e}")
            if args.max_cost and spent >= args.max_cost and not stopped:
                stopped = True
                print(f"  ! budget ${args.max_cost} reached (${spent:.2f}) — cancelling remaining")
                for f in futs:
                    f.cancel()

    print(f"done: {done} updated, {failed} failed, spent ${spent:.2f}")

    # rebuild docs + index + search so the dashboard reflects the new tags/tokens
    from reels_scrap.docs import rebuild_all

    rebuild_all(cfg)
    try:
        from reels_scrap.search import build_index

        build_index(cfg)
    except Exception as e:
        print(f"index rebuild skipped: {e}")
    print("rebuilt docs + index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
