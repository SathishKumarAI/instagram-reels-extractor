"""Local semantic search over the reel archive.

Embeds each reel (summary + structured fields + transcript) AND each individual
fact, with fastembed (ONNX, CPU, fully local — no cloud, no API key). Turns the
PDF/doc pile into a queryable knowledge base.

    reels-scrap index               # build/refresh the index
    reels-scrap search "caching"    # query
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import Config
from .models import Reel
from .observability import log

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # small, fast, good quality, ~130MB ONNX
_EMBEDDER = None


def _embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from fastembed import TextEmbedding

        _EMBEDDER = TextEmbedding(MODEL_NAME)
    return _EMBEDDER


def _embed(texts: list[str]):
    import numpy as np

    vecs = np.array(list(_embedder().embed(texts)), dtype="float32")
    # L2-normalize so dot product == cosine similarity
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def _reel_document(r: Reel) -> str:
    parts = [r.title, r.genre, r.summary]
    for k, v in (r.structured or {}).items():
        if isinstance(v, (list, tuple)):
            parts.append(f"{k}: " + "; ".join(str(x) for x in v))
        elif v:
            parts.append(f"{k}: {v}")
    if r.transcript_text:
        parts.append(r.transcript_text)
    return "\n".join(p for p in parts if p)


def index_path(cfg: Config) -> Path:
    return cfg.output_dir / "search_index.npz"


def meta_path(cfg: Config) -> Path:
    return cfg.output_dir / "search_index.json"


def _rows(r: Reel) -> tuple[list[str], list[dict]]:
    """The (text, meta) pairs one reel contributes: its document plus one per fact.

    Each row carries `doc_hash` — a digest of everything this reel contributes to
    the index. Reuse keys on that, not on file mtime: a reel's json is rewritten
    whenever anything changes (a `variant` from the Compare tab, an annotation,
    an `author_handle` backfill), and none of that alters the indexed text. On an
    mtime key, a 665-reel variant backfill would force 665 pointless re-embeds.
    """
    texts = [_reel_document(r)]
    meta: list[dict] = [{"reel_id": r.id, "title": r.title, "url": r.url,
                         "kind": "reel", "text": r.summary or r.title, "timestamp": None}]
    for f in r.facts:
        texts.append(f.text)
        meta.append({"reel_id": r.id, "title": r.title, "url": r.url,
                     "kind": "fact", "text": f.text, "timestamp": f.timestamp})
    h = hashlib.sha1("\x00".join(texts).encode("utf-8")).hexdigest()[:16]
    for m in meta:
        m["doc_hash"] = h
    return texts, meta


def build_index(cfg: Config, full: bool = False) -> int:
    """Embed reels into the search index. Returns the number of vectors indexed.

    Incremental by default: reels whose json is older than the index keep their
    existing vectors, so a sync that added 7 reels embeds 7 reels — not 673. Pass
    `full=True` (or `reels-scrap index --full`) after changing the embedding model
    or the document shape, which invalidates every stored vector.
    """
    import numpy as np

    paths = sorted(cfg.data_dir.glob("*.json"))
    if not paths:
        log.warning("no reels to index")
        return 0

    ip, mp = index_path(cfg), meta_path(cfg)
    old: dict[str, tuple] = {}             # reel_id -> (doc_hash, vectors, meta rows)
    if not full and ip.exists() and mp.exists():
        try:
            old_vecs = np.load(ip)["vectors"]
            old_meta = json.loads(mp.read_text(encoding="utf-8"))
            if len(old_meta) == len(old_vecs):
                by_reel: dict[str, list[int]] = {}
                for i, m in enumerate(old_meta):
                    by_reel.setdefault(m["reel_id"], []).append(i)
                for rid, idxs in by_reel.items():
                    h = old_meta[idxs[0]].get("doc_hash")
                    if h:                  # rows written before hashing existed → re-embed
                        old[rid] = (h, old_vecs[idxs], [old_meta[i] for i in idxs])
        except Exception as e:
            log.warning("index reuse skipped (%s) — rebuilding in full", e)
            old = {}

    reuse: dict[str, tuple] = {}
    new_texts: list[str] = []
    new_meta: list[dict] = []
    order: list[str] = []                  # reel ids in final index order
    for p in paths:
        rid = p.stem
        order.append(rid)
        texts, meta = _rows(Reel.load(p))  # cheap: JSON load + hash, no embedding
        prev = old.get(rid)
        if prev and prev[0] == meta[0]["doc_hash"]:
            reuse[rid] = (prev[1], prev[2])
            continue
        new_texts.extend(texts)
        new_meta.extend(meta)

    new_vecs = _embed(new_texts) if new_texts else None

    vec_chunks, meta_out, cursor = [], [], 0
    for rid in order:
        if rid in reuse:
            v, m = reuse[rid]
            vec_chunks.append(v)
            meta_out.extend(m)
        else:
            n = sum(1 for m in new_meta[cursor:] if m["reel_id"] == rid)
            vec_chunks.append(new_vecs[cursor:cursor + n])
            meta_out.extend(new_meta[cursor:cursor + n])
            cursor += n

    vecs = np.vstack(vec_chunks)
    np.savez_compressed(ip, vectors=vecs)
    mp.write_text(json.dumps(meta_out, indent=2), encoding="utf-8")
    log.info("indexed %d vectors from %d reels (%d re-embedded, %d reused)",
             len(meta_out), len(order), len(order) - len(reuse), len(reuse))
    return len(meta_out)


def search(cfg: Config, query: str, k: int = 8) -> list[dict]:
    """Return top-k matches: [{score, reel_id, title, url, kind, text, timestamp}]."""
    import numpy as np

    ip, mp = index_path(cfg), meta_path(cfg)
    if not ip.exists() or not mp.exists():
        raise FileNotFoundError("no index — run `reels-scrap index` first")

    vectors = np.load(ip)["vectors"]
    meta = json.loads(mp.read_text(encoding="utf-8"))
    qv = _embed([query])[0]
    scores = vectors @ qv  # cosine (all normalized)
    order = np.argsort(-scores)[:k]
    out = []
    for i in order:
        m = dict(meta[int(i)])
        m["score"] = float(scores[int(i)])
        out.append(m)
    return out
