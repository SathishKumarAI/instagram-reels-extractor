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


def _is_better(v: dict, r: Reel) -> bool:
    """Is this new local record an upgrade on what the reel currently shows?

    Deliberately conservative. The existing records are Claude-made and richer on
    facts; the new local ones are the first to carry a transcript, `key_points` and
    verbatim `on_screen_text`. Promote only when the new record adds those AND does
    not lose ground on facts — otherwise a "refresh" would quietly downgrade 658
    reels.
    """
    if not v.get("key_points") and not v.get("on_screen_text"):
        return False                      # no new information to offer
    if not (v.get("summary") or "").strip():
        return False
    return len(v.get("facts") or []) >= len(r.facts or [])


def _enrich(v: dict, r: Reel) -> bool:
    """Add what the old record simply does not have, without touching what it does.

    Every existing record predates `key_points`, `on_screen_text` and transcripts.
    Swapping wholesale would trade Claude's richer fact list for the local model's
    thinner one; copying only the missing fields is strictly additive, so a reel can
    keep the better summary AND gain the takeaways and verbatim overlay text.
    """
    changed = False
    if not r.key_points and v.get("key_points"):
        r.key_points = list(v["key_points"])
        changed = True
    if not r.on_screen_text and v.get("on_screen_text"):
        r.on_screen_text = list(v["on_screen_text"])
        changed = True
    return changed


def _archive_active(r: Reel) -> None:
    """Stash the current active record as a variant so promotion is never lossy."""
    name = str((r.tokens or {}).get("backend") or "previous")
    if name in (r.variants or {}):
        name = f"{name}-prev"
    r.variants = {**(r.variants or {}), name: {
        "backend": name,
        "model": str((r.tokens or {}).get("model") or ""),
        "summary": r.summary, "genre": r.genre, "tags": list(r.tags),
        "structured": dict(r.structured or {}),
        "facts": [f.model_dump() for f in r.facts],
        "key_points": list(r.key_points or []),
        "on_screen_text": list(r.on_screen_text or []),
        "tokens": dict(r.tokens or {}), "elapsed_s": 0, "frames": 0,
        "created_at": "archived",
    }}


def _promote(v: dict, r: Reel) -> None:
    from reels_scrap.models import Fact

    r.summary = v["summary"]
    r.genre = v["genre"] or r.genre
    r.tags = v["tags"] or r.tags
    r.structured = v["structured"] or r.structured
    r.key_points = v.get("key_points") or []
    r.on_screen_text = v.get("on_screen_text") or []
    r.facts = [Fact(**f) for f in v["facts"]]
    r.tokens = dict(v["tokens"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config-local.yaml")
    ap.add_argument("--limit", type=int, default=0, help="0 = every reel")
    ap.add_argument("--redo", action="store_true", help="re-run reels that already have one")
    ap.add_argument("--promote", action="store_true",
                    help="also make the new local record the ACTIVE one when it is better")
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

    print(f"{len(paths)} reels, {len(todo)} to process"
          + (" (promoting better records to active)" if args.promote else ""))
    ok = failed = promoted = enriched = 0
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
        if args.promote:
            if _is_better(v, r):
                _archive_active(r)              # keep the old record as a variant
                _promote(v, r)
                promoted += 1
            elif _enrich(v, r):
                enriched += 1
        r.save(base.data_dir)
        ok += 1
        if i % 10 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            left = (len(todo) - i) * rate
            print(f"  [{i}/{len(todo)}] ok={ok} failed={failed} "
                  f"{rate:.1f}s/reel, ~{left/60:.0f} min left")
    print(f"done: {ok} ok, {promoted} promoted, {enriched} enriched, {failed} failed "
          f"in {(time.time()-t0)/60:.1f} min")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
