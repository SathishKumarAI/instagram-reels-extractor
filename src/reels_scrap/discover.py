"""Propose reels worth saving, instead of waiting for you to find them.

Signals, in descending signal-to-noise:
  1. new posts from authors you have already saved 2+ times
  2. hashtag feeds for the tags your collections actually use

Candidates are scored **locally** (fastembed) against the centroid of each
collection, and nothing is downloaded until you accept — a candidate costs one
JSON row, an accepted reel costs a video plus a vision call.

Instagram rate-limits hard and a single profile source already trips `HTTP 429`.
So every request goes through `Budget`: a hard request cap, a minimum gap between
calls, and a kill-switch that ends the run on the first 429 rather than digging
the hole deeper. Discovery reads more of Instagram than you do by hand — keep it
opt-in, keep the cap visible, never parallelise.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import Config
from .models import Reel
from .observability import log
from .sources import RateLimited, load_sources, pool_ids

STORE = "discover.json"
NEW, ACCEPTED, REJECTED, SNOOZED = "new", "accepted", "rejected", "snoozed"


@dataclass
class Budget:
    """Hard ceiling on how much of Instagram one run may touch."""

    max_requests: int = 40
    min_interval: float = 3.0
    used: int = 0
    _last: float = 0.0
    stopped: str = ""

    def take(self) -> None:
        if self.stopped:
            raise RateLimited(self.stopped)
        if self.used >= self.max_requests:
            self.stopped = f"request budget spent ({self.max_requests})"
            raise RateLimited(self.stopped)
        gap = time.time() - self._last
        if self._last and gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self.used += 1
        self._last = time.time()

    def kill(self, why: str) -> None:
        """First 429 ends the whole run — resume tomorrow, not in 5 seconds."""
        self.stopped = why
        log.warning("[discover] stopping run: %s", why)


@dataclass
class Candidate:
    id: str                    # shortcode
    url: str
    caption: str = ""
    author: str = ""
    thumbnail_url: str = ""
    source: str = ""           # "author:handle" | "hashtag:tag"
    collection: str = ""       # best-matching collection
    score: float = 0.0
    why: str = ""
    state: str = NEW
    found_on: str = ""
    extra: dict = field(default_factory=dict)


# ── store ────────────────────────────────────────────────────────────────────
def store_path(cfg: Config) -> Path:
    return cfg.output_dir / STORE


def load_candidates(cfg: Config) -> dict[str, Candidate]:
    p = store_path(cfg)
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {k: Candidate(**v) for k, v in raw.items()}


def save_candidates(cfg: Config, rows: dict[str, Candidate]) -> Path:
    p = store_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({k: v.__dict__ for k, v in rows.items()}, indent=2),
                 encoding="utf-8")
    return p


def set_state(cfg: Config, cand_id: str, state: str) -> Candidate:
    rows = load_candidates(cfg)
    if cand_id not in rows:
        raise KeyError(cand_id)
    rows[cand_id].state = state
    save_candidates(cfg, rows)
    return rows[cand_id]


# ── harvest ──────────────────────────────────────────────────────────────────
def _session(browser: str):
    import requests

    from .ingest.collection import IG_APP_ID, UA, _ig_cookies

    c = _ig_cookies(browser)
    s = requests.Session()
    s.cookies.update(c)
    s.headers.update({"User-Agent": UA, "X-IG-App-ID": IG_APP_ID,
                      "X-CSRFToken": c.get("csrftoken", ""),
                      "X-Requested-With": "XMLHttpRequest",
                      "Referer": "https://www.instagram.com/"})
    return s


def _items_to_candidates(items, source: str, today: str) -> list[Candidate]:
    out = []
    for it in items:
        m = it.get("media", it)
        if m.get("media_type") != 2:          # videos only — same rule as enumerate
            continue
        code = m.get("code")
        if not code:
            continue
        cap = ((m.get("caption") or {}) or {}).get("text", "") if isinstance(m.get("caption"), dict) else ""
        user = (m.get("user") or {}).get("username", "")
        thumb = ""
        try:
            thumb = m["image_versions2"]["candidates"][0]["url"]
        except (KeyError, IndexError, TypeError):
            pass
        out.append(Candidate(
            id=code, url=f"https://www.instagram.com/reel/{code}/",
            caption=cap[:600], author=user, thumbnail_url=thumb,
            source=source, found_on=today,
        ))
    return out


def top_authors(cfg: Config, min_saves: int = 2, limit: int = 8) -> list[tuple[str, int]]:
    """@handles you have saved at least `min_saves` reels from, most-saved first.

    Only `author_handle` counts. `author` is the display name ("Alan Salgado
    Espino - Knee Rehabilitation Specialist") and IG's API has no idea what to do
    with it — feeding it to the profile endpoint burns budget for nothing. Records
    ingested before `author_handle` existed simply do not vote.
    """
    counts: dict[str, int] = {}
    for p in cfg.data_dir.glob("*.json"):
        try:
            r = Reel.load(p)
        except Exception:
            continue
        handle = (getattr(r, "author_handle", "") or "").strip().lstrip("@")
        if handle:
            counts[handle] = counts.get(handle, 0) + 1
    return sorted(
        ((h, n) for h, n in counts.items() if n >= min_saves),
        key=lambda kv: -kv[1],
    )[:limit]


def harvest_author(s, handle: str, budget: Budget, today: str, per: int = 12) -> list[Candidate]:
    budget.take()
    r = s.get("https://www.instagram.com/api/v1/users/web_profile_info/",
              params={"username": handle}, timeout=30)
    if r.status_code == 429:
        budget.kill(f"429 on profile lookup ({handle})")
        return []
    if r.status_code != 200:
        log.warning("[discover] author %s: HTTP %s", handle, r.status_code)
        return []
    try:
        uid = r.json()["data"]["user"]["id"]
    except (KeyError, ValueError):
        return []

    budget.take()
    fr = s.get(f"https://www.instagram.com/api/v1/feed/user/{uid}/",
               params={"count": per}, timeout=30)
    if fr.status_code == 429:
        budget.kill(f"429 on author feed ({handle})")
        return []
    if fr.status_code != 200:
        return []
    return _items_to_candidates(fr.json().get("items", []), f"author:{handle}", today)


def harvest_hashtag(s, tag: str, budget: Budget, today: str, per: int = 12) -> list[Candidate]:
    """Recent posts for one hashtag.

    `/tags/web_info/` looks like the obvious endpoint and returns 200, but its
    `recent.sections` is empty — it is tag metadata only. `/tags/<tag>/sections/`
    (POST) is the one that carries media.
    """
    budget.take()
    r = s.post(f"https://www.instagram.com/api/v1/tags/{tag}/sections/", timeout=30)
    if r.status_code == 429:
        budget.kill(f"429 on hashtag ({tag})")
        return []
    if r.status_code != 200:
        log.warning("[discover] hashtag %s: HTTP %s", tag, r.status_code)
        return []
    try:
        sections = r.json().get("sections") or []
    except ValueError:
        return []
    medias = []
    for sec in sections:
        medias.extend((sec.get("layout_content") or {}).get("medias") or [])
    return _items_to_candidates(medias[:per], f"hashtag:{tag}", today)


# hashtags that describe reach, not subject — following them returns noise
_JUNK_TAGS = {
    "fyp", "fypシ", "viral", "trending", "explore", "explorepage", "reels", "reel",
    "instagram", "instagood", "foryou", "foryoupage", "video", "like", "follow",
}


def top_tags(cfg: Config, limit: int = 6) -> list[str]:
    """The real Instagram hashtags your saved reels carry, most common first.

    Caption hashtags — not our generated `tags`. Ours are slugs (`open-source`,
    `claude-code`); Instagram has no hyphens, so those 404 the hashtag endpoint.
    Creators write `#opensource`, and that is a tag you can actually follow.
    """
    counts: dict[str, int] = {}
    for p in cfg.data_dir.glob("*.json"):
        try:
            r = Reel.load(p)
        except Exception:
            continue
        for h in r.hashtags or []:
            t = h.lstrip("#").lower().strip()
            if t and t.isalnum() and t not in _JUNK_TAGS and len(t) > 2:
                counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


# ── scoring ──────────────────────────────────────────────────────────────────
def collection_centroids(cfg: Config):
    """Mean embedding per collection, from the reels already in it."""
    import numpy as np

    from .collections import list_manifests
    from .search import _embed, _reel_document

    docs: dict[str, list[str]] = {}
    for m in list_manifests(cfg.output_dir):
        for rid in m.reel_ids:
            p = cfg.data_dir / f"{rid}.json"
            if not p.exists():
                continue
            try:
                docs.setdefault(m.slug, []).append(_reel_document(Reel.load(p)))
            except Exception:
                continue
    names, vecs = [], []
    for name, texts in docs.items():
        if len(texts) < 3:            # too few reels to describe a taste
            continue
        v = _embed(texts).mean(axis=0)
        n = np.linalg.norm(v)
        if n:
            names.append(name)
            vecs.append(v / n)
    return names, (np.vstack(vecs) if vecs else None)


def score_candidates(cfg: Config, cands: list[Candidate]) -> list[Candidate]:
    """Attach the best-matching collection + cosine score to each candidate."""
    import numpy as np

    from .search import _embed

    if not cands:
        return []
    names, mat = collection_centroids(cfg)
    if mat is None:
        log.warning("[discover] no collection centroids yet — leaving scores at 0")
        return cands
    texts = [f"{c.caption}\n{c.author}" for c in cands]
    vecs = _embed(texts)
    sims = vecs @ mat.T
    for i, c in enumerate(cands):
        j = int(np.argmax(sims[i]))
        c.collection = names[j]
        c.score = round(float(sims[i][j]), 3)
        c.why = f"closest to {names[j]} · via {c.source}"
    return cands


# ── the run ──────────────────────────────────────────────────────────────────
def discover(
    cfg: Config,
    browser: str = "chrome",
    max_requests: int = 40,
    authors: int = 6,
    hashtags: int = 4,
    min_score: float = 0.35,
    sources_file: str = "sources.json",
) -> dict:
    """One discovery pass. Returns a summary; candidates land in the store."""
    today = date.today().isoformat()
    budget = Budget(max_requests=max_requests)
    known = pool_ids(cfg.data_dir)
    rows = load_candidates(cfg)
    seen_ids = set(rows) | known          # never re-propose, never propose what we have

    s = _session(browser)
    fresh: list[Candidate] = []
    known_authors = top_authors(cfg, limit=authors)
    if not known_authors:
        log.info("[discover] no @handles in the corpus yet (records predate "
                 "author_handle) — hashtags only this run")
    try:
        for handle, n in known_authors:
            log.info("[discover] author %s (%d saved)", handle, n)
            fresh += [c for c in harvest_author(s, handle, budget, today) if c.id not in seen_ids]
        for tag in top_tags(cfg, limit=hashtags):
            log.info("[discover] hashtag #%s", tag)
            fresh += [c for c in harvest_hashtag(s, tag, budget, today) if c.id not in seen_ids]
    except RateLimited as e:
        log.warning("[discover] halted early: %s", e)

    # dedup within the run, then score
    uniq: dict[str, Candidate] = {}
    for c in fresh:
        uniq.setdefault(c.id, c)
    scored = [c for c in score_candidates(cfg, list(uniq.values())) if c.score >= min_score]
    scored.sort(key=lambda c: -c.score)

    for c in scored:
        rows[c.id] = c
    save_candidates(cfg, rows)

    summary = {
        "found": len(uniq),
        "kept": len(scored),
        "requests_used": budget.used,
        "request_budget": budget.max_requests,
        "stopped_early": budget.stopped,
        "pending": sum(1 for c in rows.values() if c.state == NEW),
    }
    log.info("[discover] %s", summary)
    return summary


def accept(cfg: Config, cand_id: str, sources_file: str = "sources.json") -> dict:
    """Mark accepted and queue the reel for the next sync via a urls source."""
    c = set_state(cfg, cand_id, ACCEPTED)
    urls_file = Path("reels-discovered.txt")
    existing = set(urls_file.read_text(encoding="utf-8").split()) if urls_file.exists() else set()
    if c.url not in existing:
        with urls_file.open("a", encoding="utf-8") as f:
            f.write(c.url + "\n")

    # register the queue as a source once, so a normal `sync` picks it up
    from .sources import add_source

    if not any(s.name == "discovered" for s in load_sources(sources_file)):
        add_source(str(urls_file), name="discovered", type="urls", path=sources_file)
    return {"id": cand_id, "queued": str(urls_file), "url": c.url}
