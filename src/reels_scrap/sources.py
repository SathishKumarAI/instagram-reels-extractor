"""Incremental multi-source reel poller (data-engineering layer).

Turns a declarative list of Instagram sources (`sources.json`) into an
idempotent, incremental sync:

    every run  ->  fetch the *current* reels of each source
               ->  diff against what's already in the flat data/ pool
               ->  download ONLY the new ones (no duplicates, ever)
               ->  refresh that source's manifest + consolidated doc
               ->  record per-source run state for observability

Design (why it's a data-engineering shape, not just a loop):

* **Natural primary key.** A reel's shortcode is its id; `data/<id>.json` is
  the single source of truth. Dedup is a set-diff against that pool, so the
  same reel saved in two collections is downloaded once and never re-fetched.
* **Idempotent + incremental.** Re-running with nothing newly saved does zero
  network downloads — the diff is empty. Only the delta since last run flows
  through the pipeline (which already resumes/skips existing ids).
* **Shared pool, per-source membership.** `data/` stays flat; each source keeps
  a membership manifest (collections.py) so a doc can be rebuilt per source.
* **State watermark.** `output/sources_state.json` records, per source, the last
  run date, current/new counts, and cumulative-seen ids — a run ledger you can
  diff over time without re-deriving from the pool.

Registry entry (sources.json):

    {"sources": [
      {"name": "phd-opportunities", "type": "collection",
       "url": ".../saved/phd-opportunities/18354529171213909/",
       "enabled": true, "limit": 200}
    ]}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .collections import Manifest, parse_collection_url, save_manifest, slugify
from .config import Config
from .observability import log

DEFAULT_SOURCES_FILE = "sources.json"
STATE_FILENAME = "sources_state.json"


# ── registry ────────────────────────────────────────────────────────────────
@dataclass
class Source:
    """One pollable Instagram source."""

    name: str
    url: str
    type: str = "collection"  # collection | saved | urls
    enabled: bool = True
    limit: int = 200

    @property
    def slug(self) -> str:
        # slug follows the (disambiguated) name so two collections sharing a URL
        # name — e.g. two saved lists both called "ai" — get distinct docs/manifests.
        return slugify(self.name)


def load_sources(path: str | Path = DEFAULT_SOURCES_FILE) -> list[Source]:
    p = Path(path)
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    return [Source(**s) for s in raw.get("sources", [])]


def save_sources(sources: list[Source], path: str | Path = DEFAULT_SOURCES_FILE) -> Path:
    p = Path(path)
    p.write_text(json.dumps({"sources": [asdict(s) for s in sources]}, indent=2) + "\n")
    return p


def add_source(url: str, name: str | None = None, type: str = "collection",
               path: str | Path = DEFAULT_SOURCES_FILE) -> Source:
    """Add a source to the registry (idempotent on url). Returns the entry.

    Names must be unique (they key the run-state + doc slug). If the derived name
    collides with an existing *different* URL, a numeric suffix is appended so two
    same-named collections (e.g. two saved lists called "ai") stay distinct.
    """
    sources = load_sources(path)
    for s in sources:
        if s.url == url:
            return s  # idempotent on URL

    base = name
    if not base:
        try:
            base = parse_collection_url(url)[0]
        except ValueError:
            base = slugify(url)
    taken = {s.name for s in sources}
    unique = base
    n = 2
    while unique in taken:
        unique = f"{base}-{n}"
        n += 1

    src = Source(name=unique, url=url, type=type)
    sources.append(src)
    save_sources(sources, path)
    return src


# ── dedup pool ──────────────────────────────────────────────────────────────
def pool_ids(data_dir: Path) -> set[str]:
    """Reel ids already downloaded — the dedup key set."""
    return {p.stem for p in data_dir.glob("*.json")}


def _reel_ids_from_urls(urls: list[str]) -> list[str]:
    return [u.rstrip("/").rsplit("/", 1)[-1] for u in urls]


def _profile_username(url: str) -> str:
    """Pull the handle from a profile URL: .../instagram.com/_tech_guff_/ -> _tech_guff_."""
    import re

    m = re.search(r"instagram\.com/([^/?#]+)", url)
    return (m.group(1) if m else url).strip("/@")


def _enumerate_profile(username: str, limit: int, browser: str = "chrome") -> list[str]:
    """List a public profile's video-reel URLs via the web API + your browser session.

    Anonymous access is 403-blocked by IG, so this reuses your logged-in cookies (the
    same approach as saved collections). Scraping another account is a ToS gray area —
    use sparingly. Raises on network/blocked responses; the caller records it as error.
    """
    import time

    import requests

    from .ingest.collection import IG_APP_ID, UA, _ig_cookies

    cookies = _ig_cookies(browser)
    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update({
        "User-Agent": UA, "X-IG-App-ID": IG_APP_ID,
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.instagram.com/",
    })
    # 1. resolve username -> numeric user id
    r = s.get("https://www.instagram.com/api/v1/users/web_profile_info/",
              params={"username": username}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"profile lookup HTTP {r.status_code} for {username!r}")
    uid = r.json()["data"]["user"]["id"]

    # 2. page the user feed, keep video reels only
    urls: list[str] = []
    seen: set[str] = set()
    max_id: str | None = None
    while len(urls) < limit:
        params = {"count": 33}
        if max_id:
            params["max_id"] = max_id
        fr = s.get(f"https://www.instagram.com/api/v1/feed/user/{uid}/", params=params, timeout=30)
        if fr.status_code != 200:
            raise RuntimeError(f"profile feed HTTP {fr.status_code} for {username!r}")
        data = fr.json()
        for it in data.get("items", []):
            m = it.get("media", it)
            code = m.get("code")
            if code and code not in seen and m.get("media_type") == 2:  # 2 = video
                seen.add(code)
                urls.append(f"https://www.instagram.com/reel/{code}/")
        if not data.get("more_available") or not data.get("next_max_id"):
            break
        max_id = data["next_max_id"]
        time.sleep(1.0)
    return urls[:limit]


def enumerate_source(src: Source, browser: str = "chrome") -> list[str]:
    """Current reel URLs for a source, newest-first (as IG returns them)."""
    if src.type in {"collection", "saved"}:
        from .ingest.collection import fetch_collection

        return fetch_collection(src.url, browser=browser, limit=src.limit)
    if src.type == "profile":
        return _enumerate_profile(_profile_username(src.url), src.limit, browser=browser)
    if src.type == "urls":
        from .ingest import read_urls_file

        return read_urls_file(src.url)
    raise ValueError(f"unsupported source.type: {src.type!r}")


# ── run state ───────────────────────────────────────────────────────────────
def _state_path(output_dir: Path) -> Path:
    return Path(output_dir) / STATE_FILENAME


def load_state(output_dir: Path) -> dict:
    p = _state_path(output_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(output_dir: Path, state: dict) -> Path:
    p = _state_path(output_dir)
    p.write_text(json.dumps(state, indent=2) + "\n")
    return p


# ── result ──────────────────────────────────────────────────────────────────
@dataclass
class SourceResult:
    name: str
    slug: str
    current: int = 0      # reels in the source right now
    new: int = 0          # not previously in the pool
    ingested: int = 0     # actually downloaded this run
    skipped: int = 0      # already in pool (deduped)
    doc: str = ""
    error: str = ""
    new_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)  # ingested-this-run → dead-letter


# ── text sources (RSS / arXiv / GitHub) ──────────────────────────────────────
def poll_text_source(
    cfg: Config,
    src: Source,
    build_docs: bool = True,
    run_date: str | None = None,
    dead: set[str] | None = None,
) -> SourceResult:
    """Sync one TEXT source: fetch records → dedup → structure text → manifest+doc.

    No yt-dlp, no frame vision — records carry their own text and route to
    `extract.text_summary`. Shares the reel dedup / manifest / dead-letter shape.
    """
    from .docs import build_collection_doc
    from .extract import extract_all
    from .ingest.feeds import fetch_feed_records

    dead = dead or set()
    res = SourceResult(name=src.name, slug=src.slug)
    try:
        records = fetch_feed_records(src)
    except Exception as e:  # noqa: BLE001
        res.error = str(e)
        log.error("text source %s fetch failed: %s", src.name, e)
        return res

    all_ids = [r.id for r in records]
    res.current = len(all_ids)
    seen = pool_ids(cfg.data_dir) | dead
    new = [r for r in records if r.id not in seen]
    res.new = len(new)
    res.skipped = res.current - res.new
    res.new_ids = [r.id for r in new]

    for r in new:
        r.save(cfg.data_dir)                 # persist the record first
        try:
            extract_all(r, cfg)              # text structuring (re-saves with fields)
            res.ingested += 1
        except Exception as ex:              # noqa: BLE001
            log.error("text extract failed %s: %s", r.id, ex)
            res.failed_ids.append(r.id)

    m = Manifest(
        slug=src.slug, title=src.name.replace("-", " ").title(), id="",
        url=src.url, reel_ids=all_ids, updated=run_date or date.today().isoformat(),
    )
    save_manifest(cfg.output_dir, m)
    if build_docs:
        doc, _ = build_collection_doc(cfg, m)
        res.doc = str(doc)
    return res


# ── the poll ────────────────────────────────────────────────────────────────
def poll_source(
    cfg: Config,
    src: Source,
    config_path: str,
    browser: str = "chrome",
    build_docs: bool = True,
    run_date: str | None = None,
    dead: set[str] | None = None,
) -> SourceResult:
    """Sync one source: enumerate → dedup → ingest new → refresh manifest+doc.

    `dead` is the source's dead-letter set (ids that previously failed to ingest,
    e.g. photo-only posts a *reels* extractor can't download). They're excluded
    from the "new" diff so a run doesn't re-attempt them forever — clear with
    `sync --retry-failed`. Ids that fail this run are added to `res.failed_ids`.
    """
    from .ingest.feeds import TEXT_TYPES

    # text sources take a wholly different path (no download / no frame vision)
    if src.type in TEXT_TYPES:
        return poll_text_source(cfg, src, build_docs=build_docs,
                                run_date=run_date, dead=dead)

    from .docs import build_collection_doc
    from .pipeline import run_pipeline

    dead = dead or set()
    res = SourceResult(name=src.name, slug=src.slug)
    try:
        urls = enumerate_source(src, browser=browser)
    except Exception as e:  # noqa: BLE001
        res.error = str(e)
        log.error("source %s enumerate failed: %s", src.name, e)
        return res

    all_ids = _reel_ids_from_urls(urls)
    res.current = len(all_ids)
    existing = pool_ids(cfg.data_dir)
    # dedup: already downloaded OR known-dead → not "new"
    seen = existing | dead

    new_pairs = [(i, u) for i, u in zip(all_ids, urls) if i not in seen]
    res.new = len(new_pairs)
    res.skipped = res.current - res.new
    res.new_ids = [i for i, _ in new_pairs]

    if new_pairs:
        # feed ONLY the new URLs through the pipeline (resume double-guards dedup)
        urls_file = cfg.data_dir / f".sync-{src.slug}.txt"
        urls_file.write_text("\n".join(u for _, u in new_pairs) + "\n")
        cfg.source.type = "urls"
        cfg.source.urls_file = str(urls_file)
        cfg.source.resume = True
        reels, _ = run_pipeline(cfg, config_path,
                                progress=lambda s, c, t, m: log.info("[%s] %s", s, m))
        # count what actually landed; anything that didn't → dead-letter
        landed = pool_ids(cfg.data_dir)
        res.ingested = sum(1 for i, _ in new_pairs if i in landed)
        res.failed_ids = [i for i, _ in new_pairs if i not in landed]

    # refresh membership manifest (full current list) + doc, even if nothing new
    slug, cid = (src.slug, "")
    try:
        slug, cid = parse_collection_url(src.url)
    except ValueError:
        pass
    m = Manifest(
        slug=src.slug,
        title=src.name.replace("-", " ").title(),
        id=cid,
        url=src.url,
        reel_ids=all_ids,
        updated=run_date or date.today().isoformat(),
    )
    save_manifest(cfg.output_dir, m)
    if build_docs:
        doc, _ = build_collection_doc(cfg, m)
        res.doc = str(doc)
    return res


def poll_all(
    cfg: Config,
    config_path: str,
    sources_file: str | Path = DEFAULT_SOURCES_FILE,
    browser: str = "chrome",
    build_docs: bool = True,
    run_date: str | None = None,
    retry_failed: bool = False,
    only: list[str] | None = None,
) -> list[SourceResult]:
    """Sync every enabled source, then rebuild the master index. Records state.

    `retry_failed` clears each source's dead-letter set so previously-failed ids
    (e.g. transient rate-limits) are attempted again this run.
    `only` limits the run to sources whose name is in the list (still must be enabled).
    """
    from .docs import build_master_index

    sources = [s for s in load_sources(sources_file) if s.enabled]
    if only:
        want = set(only)
        sources = [s for s in sources if s.name in want]
    if not sources:
        return []

    run_date = run_date or date.today().isoformat()
    state = load_state(cfg.output_dir)
    results: list[SourceResult] = []
    for src in sources:
        prev = state.get(src.name, {})
        dead = set() if retry_failed else set(prev.get("failed_ids", []))

        res = poll_source(cfg, src, config_path, browser=browser,
                          build_docs=build_docs, run_date=run_date, dead=dead)
        results.append(res)

        seen = set(prev.get("cumulative_seen", []))
        seen.update(res.new_ids)
        # dead-letter carries forward, plus anything that failed this run
        all_dead = (set() if retry_failed else set(prev.get("failed_ids", [])))
        all_dead.update(res.failed_ids)
        state[src.name] = {
            "last_run": run_date,
            "runs": prev.get("runs", 0) + 1,
            "last_current": res.current,
            "last_new": res.new,
            "last_ingested": res.ingested,
            "cumulative_seen": sorted(seen),
            "failed_ids": sorted(all_dead),
            "error": res.error,
        }

    if build_docs:
        build_master_index(cfg)
    save_state(cfg.output_dir, state)
    return results
