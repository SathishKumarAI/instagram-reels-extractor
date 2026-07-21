"""Text-source adapters: RSS/Atom, arXiv, GitHub releases → Reel records.

Unlike the reel path (yt-dlp download → frame vision), text sources yield full
records at fetch time. Each adapter returns a list of `Reel` with the article
text in `caption` and NO `video_path`, so extraction routes to the text
structurer (`extract.text_summary`) instead of frame vision — cheaper, no egress
of images, works fully local. Records plug into the same dedup / docs / search /
knowledge stack.

Stdlib + requests only (no feedparser dependency).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from ..models import Reel
from ..observability import log

UA = {"User-Agent": "reels-scrap/1.0 (+text-source adapter)"}
TEXT_TYPES = {"rss", "arxiv", "github"}

# XML namespaces seen in Atom / arXiv / RSS feeds
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _id_for(kind: str, url: str) -> str:
    """Stable, filesystem-safe, dedup-friendly id for a text record."""
    return f"{kind[:2]}_{hashlib.sha1(url.encode()).hexdigest()[:14]}"


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # strip HTML tags
    return re.sub(r"\s+", " ", text).strip()


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _record(kind: str, url: str, title: str, text: str, author: str,
            published: str | None) -> Reel:
    return Reel(
        id=_id_for(kind, url),
        url=url,
        title=_clean(title)[:300] or url,
        author=_clean(author),
        caption=_clean(text),            # the body the structurer reads
        timestamp=_parse_dt(published),
        # no video_path → extraction routes to text_summary, not vision
    )


# ── RSS / Atom ────────────────────────────────────────────────────────────────
def _fetch_rss(url: str, limit: int) -> list[Reel]:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out: list[Reel] = []
    # RSS 2.0: <channel><item>
    for it in root.findall(".//item"):
        link = (it.findtext("link") or "").strip()
        if not link:
            continue
        body = (it.findtext("content:encoded", namespaces=_NS)
                or it.findtext("description") or "")
        out.append(_record("rss", link, it.findtext("title") or "", body,
                           it.findtext("dc:creator", namespaces=_NS) or "",
                           it.findtext("pubDate")))
        if len(out) >= limit:
            return out
    # Atom: <feed><entry>
    for e in root.findall("atom:entry", _NS) or root.findall(".//{*}entry"):
        link_el = e.find("atom:link", _NS)
        link = (link_el.get("href") if link_el is not None else "") or ""
        if not link:
            continue
        body = (e.findtext("atom:content", namespaces=_NS)
                or e.findtext("atom:summary", namespaces=_NS) or "")
        author = e.findtext("atom:author/atom:name", namespaces=_NS) or ""
        out.append(_record("rss", link, e.findtext("atom:title", namespaces=_NS) or "",
                           body, author, e.findtext("atom:published", namespaces=_NS)
                           or e.findtext("atom:updated", namespaces=_NS)))
        if len(out) >= limit:
            break
    return out


# ── arXiv ─────────────────────────────────────────────────────────────────────
def _fetch_arxiv(url_or_cat: str, limit: int) -> list[Reel]:
    """url_or_cat: a full arXiv API query URL, or a bare category like 'cs.AI'."""
    if url_or_cat.startswith("http"):
        api = url_or_cat
    else:
        api = ("http://export.arxiv.org/api/query?"
               f"search_query=cat:{url_or_cat}&sortBy=submittedDate&sortOrder=descending"
               f"&max_results={limit}")
    r = requests.get(api, headers=UA, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out: list[Reel] = []
    for e in root.findall("atom:entry", _NS):
        link = e.findtext("atom:id", namespaces=_NS) or ""
        authors = ", ".join(a.findtext("atom:name", namespaces=_NS) or ""
                            for a in e.findall("atom:author", _NS))
        out.append(_record("arxiv", link, e.findtext("atom:title", namespaces=_NS) or "",
                           e.findtext("atom:summary", namespaces=_NS) or "",
                           authors, e.findtext("atom:published", namespaces=_NS)))
        if len(out) >= limit:
            break
    return out


# ── GitHub releases ───────────────────────────────────────────────────────────
def _fetch_github(url: str, limit: int) -> list[Reel]:
    """Releases of a repo (https://github.com/owner/repo) as records."""
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", url)
    if not m:
        raise ValueError(f"not a github repo url: {url!r}")
    owner, repo = m.group(1), m.group(2).removesuffix(".git")
    api = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={min(limit, 100)}"
    r = requests.get(api, headers={**UA, "Accept": "application/vnd.github+json"}, timeout=30)
    r.raise_for_status()
    out: list[Reel] = []
    for rel in r.json():
        out.append(_record("github", rel.get("html_url") or url,
                           f"{repo} {rel.get('tag_name', '')}: {rel.get('name', '')}",
                           rel.get("body") or "", owner, rel.get("published_at")))
        if len(out) >= limit:
            break
    return out


def fetch_feed_records(src, limit: int | None = None) -> list[Reel]:
    """Dispatch a text source to its adapter. `src` is a Source (has type/url/limit)."""
    n = limit or getattr(src, "limit", 50) or 50
    if src.type == "rss":
        recs = _fetch_rss(src.url, n)
    elif src.type == "arxiv":
        recs = _fetch_arxiv(src.url, n)
    elif src.type == "github":
        recs = _fetch_github(src.url, n)
    else:
        raise ValueError(f"not a text source type: {src.type!r}")
    log.info("feed %s (%s): %d records", getattr(src, "name", "?"), src.type, len(recs))
    return recs
