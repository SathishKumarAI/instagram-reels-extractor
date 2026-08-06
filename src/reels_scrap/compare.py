"""Run two vision backends over the same reel and diff what they claim.

The question this answers is not "which summary reads better" — it is "what does
the cheap local model actually miss". So the unit of comparison is the **claim**:
facts one backend grounded in a frame and the other did not.
"""

from __future__ import annotations

import re

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
    # Reporting boilerplate. Local models narrate where they read a claim —
    # "Frame 2 displays the on-screen text 'ISOMETRIC HOLD'" — and Claude states it
    # outright. Counting those words made the same claim look like two: measured
    # 0.24 on a pair that is plainly identical. This is scoring the narration, not
    # the claim, and it penalised exactly the models that follow our own
    # "ground each fact in a frame" instruction.
    "frame", "frames", "shows", "show", "showing", "shown", "displays", "display",
    "displayed", "features", "featuring", "depicts", "contains", "indicates",
    "indicating", "appears", "visible", "screen", "onscreen", "text", "image",
    "video", "reel", "clip", "caption", "seen", "reads", "states", "says",
}
# "Frame 3:" / "In frame 3," / "Frame 3 shows that" — strip the pointer, keep the claim
_FRAME_PREFIX = re.compile(
    r"^(?:in\s+)?frames?\s*#?\d+\s*(?:\([^)]*\))?\s*[:,\-–]?\s*"
    r"(?:the\s+)?(?:shows?|displays?|features?|depicts?|contains?)?\s*(?:that\s+)?",
    re.I,
)


def _words(text: str) -> set[str]:
    text = _FRAME_PREFIX.sub("", text.strip())
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2}


# a quoted string, or a run of two-plus SHOUTED words — how both models render an
# on-screen label they have both read
_QUOTED = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{6,80})[\"'“”‘’]")
_SHOUTED = re.compile(r"\b([A-Z][A-Z0-9&/.-]{1,}(?:\s+[A-Z][A-Z0-9&/.-]{1,})+)\b")


def _phrases(text: str) -> set[str]:
    """Distinctive multi-word labels a claim quotes, normalised for comparison."""
    out = set()
    for m in list(_QUOTED.findall(text)) + list(_SHOUTED.findall(text)):
        key = " ".join(w for w in _WORD_RE.findall(m.lower()) if len(w) > 2)
        if key.count(" ") >= 1:          # single words are not distinctive enough
            out.add(key)
    return out


def _similar(a: str, b: str) -> float:
    """How likely two claim strings are the same claim. 1.0 = same, 0.0 = unrelated.

    Jaccard alone is wrong here: Claude writes `No. 1 is "Project Based Learning" at
    github.com/practical-tutorials/project-based-learning` where the local model
    writes `no. 1 PROJECT BASED LEARNING`. Same claim, one side just carries more
    detail — Jaccard scores that 0.3 and calls it a disagreement. Containment (how
    much of the SHORTER claim appears in the longer one) catches it.
    """
    # Two claims quoting the same on-screen label are the same claim, however
    # differently they are dressed: `"RDL ISOMETRIC HOLD", hinging over a bench` vs
    # `the label 'RDL ISOMETRIC HOLD' for Romanian deadlifts`. Word overlap alone
    # scores that 0.23 because each side adds its own detail.
    shared_phrase = _phrases(a) & _phrases(b)

    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 1.0 if wa == wb else 0.0
    if shared_phrase:
        return 0.8
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
    """Config to run one backend — now one named profile. See `profiles.py`.

    Kept under the old name because the CLI, the sync endpoint and this module's
    own callers were written when a backend was all there was.
    """
    from .profiles import resolve_profile

    return resolve_profile(backend, base_config)


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


def agreement(cfg: Config, reference: str = "claude-cli",
              reel_ids: list[str] | None = None) -> dict[str, dict]:
    """Per profile: how its claims line up with a reference arm's, on shared reels.

    Only reels where BOTH arms produced a variant count — comparing a model on the
    reels it managed against a reference on all of them would flatter the weaker
    model, which is the exact error this bench exists to avoid.
    """
    out: dict[str, dict] = {}
    wanted = set(reel_ids) if reel_ids else None

    for p in sorted(cfg.data_dir.glob("*.json")):
        if wanted is not None and p.stem not in wanted:
            continue
        variants = (Reel.load(p).variants or {})
        ref = variants.get(reference)
        if not ref:
            continue
        for name, v in variants.items():
            if name == reference:
                continue
            d = diff_facts(ref.get("facts", []), v.get("facts", []))
            e = out.setdefault(name, {"profile": name, "reels": 0, "shared": 0,
                                      "only_reference": 0, "only_candidate": 0})
            e["reels"] += 1
            e["shared"] += len(d["shared"])
            e["only_reference"] += len(d["only_a"])
            e["only_candidate"] += len(d["only_b"])

    for e in out.values():
        total = e["shared"] + e["only_reference"] + e["only_candidate"]
        e["reference"] = reference
        e["agreement"] = round(e["shared"] / total, 3) if total else None
        e["missed_per_reel"] = round(e["only_reference"] / e["reels"], 2) if e["reels"] else None
        e["added_per_reel"] = round(e["only_candidate"] / e["reels"], 2) if e["reels"] else None
    return out


def disagreement_examples(cfg: Config, reference: str = "claude-cli",
                          limit: int = 40, reel_ids: list[str] | None = None) -> list[dict]:
    """Real disagreeing claims, spread across profiles — the input to the analysis.

    Claim text only: no frames, no caption, no account handle leaves the machine.
    """
    per_profile: dict[str, list[dict]] = {}
    wanted = set(reel_ids) if reel_ids else None

    for p in sorted(cfg.data_dir.glob("*.json")):
        if wanted is not None and p.stem not in wanted:
            continue
        variants = (Reel.load(p).variants or {})
        ref = variants.get(reference)
        if not ref:
            continue
        for name, v in variants.items():
            if name == reference:
                continue
            d = diff_facts(ref.get("facts", []), v.get("facts", []))
            if not d["only_a"] and not d["only_b"]:
                continue
            per_profile.setdefault(name, []).append({
                "model": name,
                "reference_summary": (ref.get("summary") or "")[:400],
                "candidate_summary": (v.get("summary") or "")[:400],
                "only_reference": d["only_a"][:6],
                "only_candidate": d["only_b"][:6],
            })

    # round-robin so one prolific model cannot crowd the others out of the sample
    out: list[dict] = []
    queues = [iter(v) for v in per_profile.values()]
    while queues and len(out) < limit:
        for q in list(queues):
            try:
                out.append(next(q))
            except StopIteration:
                queues.remove(q)
            if len(out) >= limit:
                break
    return out


def scoreboard(cfg: Config, reel_ids: list[str] | None = None) -> dict:
    """Aggregate every stored variant, per backend.

    This is what decides the default backend — not a three-reel impression.
    Pass `reel_ids` to score one fixed sample: without it the corpus-wide backfill
    (641 reels of `local`) sits in the same table as a 30-reel arm, and the two
    columns are not measuring the same thing.
    """
    per: dict[str, dict] = {}
    reels_with_variants = 0
    disagreement: list[float] = []
    wanted = set(reel_ids) if reel_ids else None

    for p in sorted(cfg.data_dir.glob("*.json")):
        if wanted is not None and p.stem not in wanted:
            continue
        r = Reel.load(p)
        if not r.variants:
            continue
        reels_with_variants += 1
        for name, v in r.variants.items():
            d = per.setdefault(name, {
                "backend": name, "model": v.get("model", ""), "reels": 0,
                "facts": 0, "tags": 0, "summary_chars": 0, "seconds": 0.0,
                "cost_usd": 0.0, "structured_fields": 0,
                "empty": 0, "salvaged": 0,
            })
            d["reels"] += 1
            # a variant that parsed but carries no claim is a failure wearing a
            # success's clothes; averaging it in silently flatters the model
            if not (v.get("facts") or []):
                d["empty"] += 1
            if (v.get("tokens") or {}).get("salvaged"):
                d["salvaged"] += 1
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
            # what one reel costs on this model — the number you actually decide on.
            # See docs/research/COSTS.md for what each backend's figure means.
            "cost_per_reel": round(d["cost_usd"] / n, 4),
            "empty_rate": round(d["empty"] / n, 3),
        })
    rows.sort(key=lambda r: -r["avg_facts"])
    return {
        "reels_compared": reels_with_variants,
        "backends": rows,
        "avg_disagreement": round(sum(disagreement) / len(disagreement), 3) if disagreement else None,
    }
