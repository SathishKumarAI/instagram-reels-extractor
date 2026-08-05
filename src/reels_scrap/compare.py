"""Run two vision backends over the same reel and diff what they claim.

The question this answers is not "which summary reads better" — it is "what does
the cheap local model actually miss". So the unit of comparison is the **claim**:
facts one backend grounded in a frame and the other did not.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .models import Reel
from .observability import log

# a claim is "the same claim" when its words mostly overlap — models phrase the
# same on-screen line differently ("5 GitHub repos" vs "five GitHub repositories")
_MATCH_THRESHOLD = 0.5
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "and", "or",
    "in", "on", "at", "for", "with", "that", "this", "it", "as", "by", "from",
}


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2}


def _similar(a: str, b: str) -> float:
    """How likely two claim strings are the same claim. 1.0 = same, 0.0 = unrelated.

    Jaccard alone is wrong here: Claude writes `No. 1 is "Project Based Learning" at
    github.com/practical-tutorials/project-based-learning` where the local model
    writes `no. 1 PROJECT BASED LEARNING`. Same claim, one side just carries more
    detail — Jaccard scores that 0.3 and calls it a disagreement. Containment (how
    much of the SHORTER claim appears in the longer one) catches it.
    """
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 1.0 if wa == wb else 0.0
    inter = len(wa & wb)
    jaccard = inter / len(wa | wb)
    shorter = min(len(wa), len(wb))
    containment = inter / shorter
    # containment needs a floor, or "python" vs "python tutorial for beginners"
    # would count as the same claim
    if shorter >= 2 and containment >= 0.7:
        return max(jaccard, containment)
    return jaccard


def diff_facts(a: list[dict], b: list[dict]) -> dict:
    """Greedy 1:1 match between two fact lists. Returns shared / only_a / only_b."""
    ta = [f.get("text", "") for f in a]
    tb = [f.get("text", "") for f in b]
    used_b: set[int] = set()
    shared, only_a = [], []
    for x in ta:
        best, best_score = -1, 0.0
        for j, y in enumerate(tb):
            if j in used_b:
                continue
            s = _similar(x, y)
            if s > best_score:
                best, best_score = j, s
        if best >= 0 and best_score >= _MATCH_THRESHOLD:
            used_b.add(best)
            shared.append({"a": x, "b": tb[best], "score": round(best_score, 2)})
        else:
            only_a.append(x)
    only_b = [y for j, y in enumerate(tb) if j not in used_b]
    return {"shared": shared, "only_a": only_a, "only_b": only_b}


def cfg_for_backend(backend: str, base_config: str = "config.yaml") -> Config:
    """Config to run one backend with.

    `local` needs `vision_local.base_url`, which only `config-local.yaml` carries —
    fall back to the base config if that file is gone.
    """
    if backend == "local":
        p = Path("config-local.yaml")
        if p.exists():
            cfg = Config.load(str(p))
            cfg.extract.vision_backend = "local"
            cfg.extract.vision_local_fallback = False   # a fallback would fake the result
            return cfg
    cfg = Config.load(base_config)
    cfg.extract.vision_backend = backend
    return cfg


def compare_reel(
    reel_id: str,
    backends: list[str],
    base_config: str = "config.yaml",
    store: bool = True,
) -> dict:
    """Run each backend over one reel, store the variants, return them + the diff."""
    from .extract.vision import run_variant

    base = Config.load(base_config)
    path = base.data_dir / f"{reel_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no reel {reel_id}")
    reel = Reel.load(path)

    results: dict[str, dict] = {}
    errors: dict[str, str] = {}
    for b in backends:
        try:
            results[b] = run_variant(reel, cfg_for_backend(b, base_config), b)
        except Exception as e:
            errors[b] = str(e)[:300]
            log.error("compare %s/%s failed: %s", reel_id, b, e)

    if store and results:
        # re-load: run_variant may have taken a while and the pipeline may have written
        reel = Reel.load(path)
        reel.variants = {**(reel.variants or {}), **results}
        reel.save(base.data_dir)

    diff = {}
    if len(results) == 2:
        (na, va), (nb, vb) = list(results.items())
        diff = {"a": na, "b": nb, **diff_facts(va["facts"], vb["facts"])}
    return {"reel_id": reel_id, "variants": results, "errors": errors, "diff": diff}


def scoreboard(cfg: Config) -> dict:
    """Aggregate every stored variant across the corpus, per backend.

    This is what decides the default backend — not a three-reel impression.
    """
    per: dict[str, dict] = {}
    reels_with_variants = 0
    disagreement: list[float] = []

    for p in sorted(cfg.data_dir.glob("*.json")):
        r = Reel.load(p)
        if not r.variants:
            continue
        reels_with_variants += 1
        for name, v in r.variants.items():
            d = per.setdefault(name, {
                "backend": name, "model": v.get("model", ""), "reels": 0,
                "facts": 0, "tags": 0, "summary_chars": 0, "seconds": 0.0,
                "cost_usd": 0.0, "structured_fields": 0,
            })
            d["reels"] += 1
            d["facts"] += len(v.get("facts") or [])
            d["tags"] += len(v.get("tags") or [])
            d["summary_chars"] += len(v.get("summary") or "")
            d["seconds"] += float(v.get("elapsed_s") or 0)
            d["cost_usd"] += float((v.get("tokens") or {}).get("cost_usd") or 0)
            d["structured_fields"] += len(v.get("structured") or {})
        if len(r.variants) == 2:
            (va, vb) = list(r.variants.values())
            dd = diff_facts(va.get("facts", []), vb.get("facts", []))
            total = len(dd["shared"]) + len(dd["only_a"]) + len(dd["only_b"])
            if total:
                disagreement.append((len(dd["only_a"]) + len(dd["only_b"])) / total)

    rows = []
    for d in per.values():
        n = max(1, d["reels"])
        rows.append({
            **d,
            "avg_facts": round(d["facts"] / n, 2),
            "avg_tags": round(d["tags"] / n, 2),
            "avg_summary_chars": round(d["summary_chars"] / n),
            "avg_seconds": round(d["seconds"] / n, 2),
            "avg_structured_fields": round(d["structured_fields"] / n, 2),
            "cost_usd": round(d["cost_usd"], 4),
        })
    rows.sort(key=lambda r: -r["avg_facts"])
    return {
        "reels_compared": reels_with_variants,
        "backends": rows,
        "avg_disagreement": round(sum(disagreement) / len(disagreement), 3) if disagreement else None,
    }
