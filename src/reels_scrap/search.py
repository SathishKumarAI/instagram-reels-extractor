"""Local semantic search over the reel archive.

Embeds each reel (summary + structured fields + transcript) AND each individual
fact, with fastembed (ONNX, CPU, fully local — no cloud, no API key). Turns the
PDF/doc pile into a queryable knowledge base.

    reels-scrap index               # build/refresh the index
    reels-scrap search "caching"    # query
"""

from __future__ import annotations

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


def build_index(cfg: Config) -> int:
    """Embed every reel + fact in data_dir. Returns number of vectors indexed."""
    import numpy as np

    reels = [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]
    if not reels:
        log.warning("no reels to index")
        return 0

    texts: list[str] = []
    meta: list[dict] = []
    for r in reels:
        texts.append(_reel_document(r))
        meta.append({"reel_id": r.id, "title": r.title, "url": r.url,
                     "kind": "reel", "text": r.summary or r.title, "timestamp": None})
        for f in r.facts:
            texts.append(f.text)
            meta.append({"reel_id": r.id, "title": r.title, "url": r.url,
                         "kind": "fact", "text": f.text, "timestamp": f.timestamp})

    vecs = _embed(texts)
    np.savez_compressed(index_path(cfg), vectors=vecs)
    meta_path(cfg).write_text(json.dumps(meta, indent=2))
    log.info("indexed %d vectors from %d reels", len(meta), len(reels))
    return len(meta)


def search(cfg: Config, query: str, k: int = 8) -> list[dict]:
    """Return top-k matches: [{score, reel_id, title, url, kind, text, timestamp}]."""
    import numpy as np

    ip, mp = index_path(cfg), meta_path(cfg)
    if not ip.exists() or not mp.exists():
        raise FileNotFoundError("no index — run `reels-scrap index` first")

    vectors = np.load(ip)["vectors"]
    meta = json.loads(mp.read_text())
    qv = _embed([query])[0]
    scores = vectors @ qv  # cosine (all normalized)
    order = np.argsort(-scores)[:k]
    out = []
    for i in order:
        m = dict(meta[int(i)])
        m["score"] = float(scores[int(i)])
        out.append(m)
    return out
