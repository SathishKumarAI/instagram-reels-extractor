"""Enumerate a *named* Instagram saved collection into reel URLs.

The built-in `saved` source only pulls the default "All Posts" saved feed.
Named collections (e.g. .../saved/front-end/18095255279194694/) live behind a
private web endpoint that needs your logged-in session. This module reuses the
browser cookies you're already logged in with (via yt-dlp's cookie extractor,
which handles Linux keyring decryption) — no password, no browser automation.

    from reels_scrap.ingest.collection import fetch_collection
    urls = fetch_collection("https://www.instagram.com/<u>/saved/<name>/<id>/")
"""

from __future__ import annotations

import re
import time

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


def _ig_cookies(browser: str) -> dict[str, str]:
    """Pull instagram.com cookies from the browser via yt-dlp's extractor."""
    from yt_dlp.cookies import extract_cookies_from_browser

    jar = extract_cookies_from_browser(browser)
    cookies = {c.name: c.value for c in jar if "instagram.com" in (c.domain or "")}
    if "sessionid" not in cookies:
        raise RuntimeError(
            f"no Instagram 'sessionid' cookie in {browser}. "
            "Log into instagram.com in that browser first."
        )
    return cookies


def _shortcode(item: dict) -> str | None:
    """A collection item wraps the post under `media`; pull its shortcode."""
    m = item.get("media", item)
    return m.get("code")


def fetch_collection(
    url_or_id: str,
    browser: str = "chrome",
    limit: int = 200,
    sleep_between: float = 1.5,
) -> list[str]:
    """Return reel/post URLs in a named saved collection (de-duped, in order)."""
    import requests

    cid = collection_id(url_or_id)
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
    url = f"https://www.instagram.com/api/v1/feed/collection/{cid}/posts/"

    items: list[dict] = []
    max_id: str | None = None
    page = 0
    while True:
        params = {"max_id": max_id} if max_id else {}
        r = s.get(url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} from collection feed: {r.text[:300]}")
        data = r.json()
        batch = data.get("items", [])
        items.extend(batch)
        page += 1
        log.info("collection %s page %d: +%d (total %d)", cid, page, len(batch), len(items))
        if len(items) >= limit or not data.get("more_available"):
            break
        max_id = data.get("next_max_id")
        if not max_id:
            break
        time.sleep(sleep_between)

    urls: list[str] = []
    seen: set[str] = set()
    for it in items[:limit]:
        code = _shortcode(it)
        if code and code not in seen:
            seen.add(code)
            urls.append(f"https://www.instagram.com/reel/{code}/")
    log.info("collection %s: %d reels", cid, len(urls))
    return urls
