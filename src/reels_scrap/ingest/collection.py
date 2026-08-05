"""Enumerate a *named* Instagram saved collection into reel URLs.

The built-in `saved` source only pulls the default "All Posts" saved feed.
Named collections (e.g. .../saved/front-end/10000000000000004/) live behind a
private web endpoint that needs your logged-in session. This module reuses the
browser cookies you're already logged in with (via yt-dlp's cookie extractor,
which handles Linux keyring decryption) — no password, no browser automation.

    from reels_scrap.ingest.collection import fetch_collection
    urls = fetch_collection("https://www.instagram.com/<u>/saved/<name>/<id>/")
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..observability import log

IG_APP_ID = "936619743392459"  # public web app id used by instagram.com
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def collection_id(url_or_id: str) -> str:
    """Accept a full saved-collection URL or a bare numeric id."""
    if url_or_id.isdigit():
        return url_or_id
    m = re.search(r"/saved/[^/]+/(\d+)", url_or_id)
    if not m:
        raise ValueError(f"could not find a collection id in: {url_or_id!r}")
    return m.group(1)


def _cookies_from_file(path: Path) -> dict[str, str]:
    """Parse a Netscape cookies.txt into {name: value} for instagram.com.

    Browser extensions prefix httpOnly rows with `#HttpOnly_` — sessionid is one
    of them, so those lines must be kept, not treated as comments.
    """
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.removeprefix("#HttpOnly_")
        if line.startswith("#") or not line.strip():
            continue
        f = line.split("\t")
        if len(f) >= 7 and "instagram.com" in f[0]:
            out[f[5]] = f[6]
    return out


def _ig_cookies(browser: str) -> dict[str, str]:
    """Pull instagram.com cookies from a browser profile or a cookies.txt path.

    Accepts `chrome`, `chrome:Profile Name`, or a path to an exported Netscape
    cookies.txt. Without a profile yt-dlp picks the most-recently-used one, which
    is often not the one logged into Instagram. On Windows, Chrome 127+ encrypts
    cookies app-bound and yt-dlp cannot decrypt them at all (yt-dlp #10927) — the
    cookies.txt path is the way out there.
    """
    p = Path(browser)
    if p.suffix == ".txt" or p.exists():
        cookies = _cookies_from_file(p)
        source = str(p)
    else:
        from yt_dlp.cookies import extract_cookies_from_browser

        name, _, profile = browser.partition(":")
        jar = extract_cookies_from_browser(name, profile or None)
        cookies = {c.name: c.value for c in jar if "instagram.com" in (c.domain or "")}
        source = browser
    if "sessionid" not in cookies:
        raise RuntimeError(
            f"no Instagram 'sessionid' cookie in {source}. "
            "Log into instagram.com in that browser first."
        )
    return cookies


def _shortcode(item: dict) -> str | None:
    """A collection item wraps the post under `media`; pull its shortcode.

    Skips posts with no video track. IG `media_type`: 1 = photo, 2 = video,
    8 = carousel. A photo or an all-photo carousel has nothing for yt-dlp to
    download — it used to reach the pipeline and dead-letter as "No video formats
    found!", once per post, on every run.
    """
    m = item.get("media", item)
    mt = m.get("media_type")
    if mt == 1:
        return None
    if mt == 8 and not any(
        c.get("media_type") == 2 for c in (m.get("carousel_media") or [])
    ):
        return None
    return m.get("code")


HANDLES_FILE = "handles.json"


def handles_path(output_dir: Path | str = "output") -> Path:
    return Path(output_dir) / HANDLES_FILE


def record_handles(new: dict[str, str], output_dir: Path | str = "output") -> Path:
    """Merge shortcode -> @handle into the side map (feeds give it away for free)."""
    p = handles_path(output_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    cur = {}
    if p.exists():
        try:
            cur = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            cur = {}
    cur.update(new)
    p.write_text(json.dumps(cur, indent=2, sort_keys=True), encoding="utf-8")
    return p


def apply_handles(cfg) -> int:
    """Fill `author_handle` on reels that predate the field. Returns how many."""
    from ..models import Reel

    p = handles_path(cfg.output_dir)
    if not p.exists():
        return 0
    try:
        handles = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for rid, handle in handles.items():
        f = cfg.data_dir / f"{rid}.json"
        if not f.exists():
            continue
        try:
            r = Reel.load(f)
        except Exception:
            continue
        if not r.author_handle and handle:
            r.author_handle = handle
            r.save(cfg.data_dir)
            n += 1
    if n:
        log.info("[handles] filled author_handle on %d reel(s)", n)
    return n


def session_ok(browser: str = "chrome") -> tuple[bool, str]:
    """Is the Instagram session usable right now? Returns (ok, human reason).

    Cheapest possible check — one authenticated call. An expired cookie otherwise
    surfaces as every source failing at once, which reads like a broken program
    rather than a 30-second re-export.
    """
    import requests

    try:
        cookies = _ig_cookies(browser)
    except Exception as e:
        return False, str(e)
    try:
        r = requests.get(
            "https://www.instagram.com/api/v1/feed/saved/posts/",
            headers={"User-Agent": UA, "X-IG-App-ID": IG_APP_ID,
                     "X-CSRFToken": cookies.get("csrftoken", ""),
                     "Referer": "https://www.instagram.com/"},
            cookies=cookies, timeout=20,
        )
    except Exception as e:
        return False, f"network error: {e}"
    if r.status_code == 200:
        return True, "session ok"
    if r.status_code in (401, 403):
        return False, f"session expired (HTTP {r.status_code}) — re-export {browser}"
    if r.status_code == 429:
        return False, "rate-limited (HTTP 429) — session may still be fine, retry later"
    return False, f"unexpected HTTP {r.status_code}"


def _fetch_feed(
    feed_url: str,
    label: str,
    browser: str,
    limit: int,
    sleep_between: float,
) -> list[str]:
    """Page a private IG feed endpoint into de-duped reel URLs, newest first."""
    import requests

    cookies = _ig_cookies(browser)

    s = requests.Session()
    s.cookies.update(cookies)
    s.headers.update(
        {
            "User-Agent": UA,
            "X-IG-App-ID": IG_APP_ID,
            "X-CSRFToken": cookies.get("csrftoken", ""),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Referer": "https://www.instagram.com/",
        }
    )
    items: list[dict] = []
    max_id: str | None = None
    page = 0
    while True:
        params = {"max_id": max_id} if max_id else {}
        r = s.get(feed_url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from collection feed: {r.text[:300]}")
        data = r.json()
        batch = data.get("items", [])
        items.extend(batch)
        page += 1
        log.info("collection %s page %d: +%d (total %d)", label, page, len(batch), len(items))
        if len(items) >= limit or not data.get("more_available"):
            break
        max_id = data.get("next_max_id")
        if not max_id:
            break
        time.sleep(sleep_between)

    urls: list[str] = []
    seen: set[str] = set()
    handles: dict[str, str] = {}
    for it in items[:limit]:
        code = _shortcode(it)
        if code and code not in seen:
            seen.add(code)
            urls.append(f"https://www.instagram.com/reel/{code}/")
            u = ((it.get("media", it).get("user")) or {}).get("username")
            if u:
                handles[code] = u
    # the feed already tells us each poster's @handle — record it here, or the only
    # way to learn it later is one profile request per reel (which IG will 429)
    if handles:
        record_handles(handles)
    log.info("collection %s: %d reels", label, len(urls))
    return urls


def fetch_collection(
    url_or_id: str,
    browser: str = "chrome",
    limit: int = 200,
    sleep_between: float = 1.5,
) -> list[str]:
    """Return reel/post URLs in a NAMED saved collection (de-duped, in order)."""
    cid = collection_id(url_or_id)
    return _fetch_feed(
        f"https://www.instagram.com/api/v1/feed/collection/{cid}/posts/",
        cid, browser, limit, sleep_between,
    )


def fetch_saved_feed(
    browser: str = "chrome",
    limit: int = 200,
    sleep_between: float = 1.5,
) -> list[str]:
    """Return reel URLs from the DEFAULT saved feed ("All Posts").

    A reel saved without picking a collection lands only here — it appears in no
    named collection, so a collection-only sync never sees it.
    """
    return _fetch_feed(
        "https://www.instagram.com/api/v1/feed/saved/posts/",
        "saved/all", browser, limit, sleep_between,
    )
