"""Does the caption actually reach the model — measured, not read off the prompt.

The bench said every local arm misses caption-derived claims (`#ad`, sponsor
handles, links). Two explanations fit that: the caption never arrives, or it
arrives and the model ignores it. Reading `_prompt_header` cannot tell them
apart, so this runs each reel TWICE on the same frames — once as-is, once with
the caption blanked — and counts caption-only markers in the output.

    marker = a #hashtag / @handle / URL that is in the caption and NOT in the
             transcript or the stored on-screen text, i.e. the model can only
             have got it from the caption.

Read the result like this:
    with ~= without ~= 0   -> the caption is ignored (or absent). Prompt problem.
    with  >  without       -> the caption arrives and is used; the gap is recall.
    without > 0            -> the marker leaked in from frames; tighten the metric.

    python scripts/ablate_caption.py [-c config-local.yaml] [--limit 12]

Costs nothing on the local backend (~8s/reel × 2 arms). Writes
output/bench/caption-ablation.json.
"""

from __future__ import annotations

import argparse
import json
import re
import time

from reels_scrap.config import Config
from reels_scrap.extract.vision import run_variant
from reels_scrap.models import Reel
from reels_scrap.observability import log

MARKER = re.compile(r"(?:#\w{3,}|@[\w.]{3,}|https?://\S+|\b[\w-]+\.(?:com|io|ai|dev|org|net)/\S*)")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def caption_only_markers(reel: Reel) -> list[str]:
    """Markers the model can ONLY have learned from the caption."""
    elsewhere = _norm(
        (reel.transcript_text or "") + " ".join(reel.on_screen_text or []) + (reel.title or "")
    )
    out: list[str] = []
    for m in MARKER.findall(reel.caption or ""):
        n = _norm(m)
        if len(n) >= 4 and n not in elsewhere and n not in {_norm(o) for o in out}:
            out.append(m)
    return out


def variant_text(v: dict) -> str:
    parts = [v.get("summary") or "", " ".join(v.get("key_points") or [])]
    parts += [f.get("text", "") for f in v.get("facts") or []]
    parts += list(v.get("on_screen_text") or []) + list(v.get("tags") or [])
    parts.append(json.dumps(v.get("structured") or {}, ensure_ascii=False))
    return _norm(" ".join(parts))


def hits(v: dict, markers: list[str]) -> list[str]:
    text = variant_text(v)
    return [m for m in markers if _norm(m) in text]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default="config-local.yaml")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--backend", default="")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    backend = args.backend or cfg.extract.vision_backend

    # only reels where the question is answerable: a video to sample frames from
    # AND at least one marker the caption alone carries
    cands: list[tuple[Reel, list[str]]] = []
    for p in sorted(cfg.data_dir.glob("*.json")):
        try:
            r = Reel.load(p)
        except Exception:
            continue
        if not (r.video_path and (cfg.data_dir / r.video_path).exists()):
            continue
        marks = caption_only_markers(r)
        if marks:
            cands.append((r, marks))
    cands.sort(key=lambda rm: -len(rm[1]))
    cands = cands[: args.limit]
    log.info("caption ablation: %d reels, backend=%s", len(cands), backend)

    rows = []
    for i, (reel, marks) in enumerate(cands, 1):
        blind = reel.model_copy(deep=True)
        blind.caption = ""
        row: dict = {"id": reel.id, "markers": marks}
        for arm, subject in (("with", reel), ("without", blind)):
            t0 = time.time()
            try:
                v = run_variant(subject, cfg, backend)
                row[arm] = {
                    "hits": hits(v, marks),
                    "facts": len(v.get("facts") or []),
                    "summary_chars": len(v.get("summary") or ""),
                    "sec": round(time.time() - t0, 1),
                }
            except Exception as ex:            # a failed arm is data, not an average
                row[arm] = {"error": str(ex)[:200]}
        log.info(
            "%d/%d %s: %d markers, with=%d without=%d",
            i, len(cands), reel.id, len(marks),
            len(row["with"].get("hits", [])), len(row["without"].get("hits", [])),
        )
        rows.append(row)

    ok = [r for r in rows if "hits" in r.get("with", {}) and "hits" in r.get("without", {})]
    total = sum(len(r["markers"]) for r in ok)
    with_hits = sum(len(r["with"]["hits"]) for r in ok)
    without_hits = sum(len(r["without"]["hits"]) for r in ok)
    summary = {
        "backend": backend,
        "reels": len(ok),
        "markers": total,
        "recall_with_caption": round(with_hits / total, 3) if total else 0.0,
        "recall_without_caption": round(without_hits / total, 3) if total else 0.0,
        "facts_with": round(sum(r["with"]["facts"] for r in ok) / len(ok), 2) if ok else 0,
        "facts_without": round(sum(r["without"]["facts"] for r in ok) / len(ok), 2) if ok else 0,
    }
    out = cfg.output_dir / "bench" / "caption-ablation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
