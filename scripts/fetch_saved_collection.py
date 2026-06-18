#!/usr/bin/env python3
"""Enumerate an Instagram *named* saved collection into reel URLs.

The pipeline's `saved` source only pulls the default "All Posts" saved feed.
Named collections (e.g. .../saved/front-end/18095255279194694/) live behind a
private web endpoint that needs your logged-in session. This script reuses the
Chrome cookies you're already logged in with (via yt-dlp's cookie extractor,
which handles Linux decryption) — no password, no browser automation.

Usage:
    python scripts/fetch_saved_collection.py \
        "https://www.instagram.com/<user>/saved/<name>/<collection_id>/" \
        [--out reels.txt] [--limit 200] [--browser chrome] [--print-only]

Output: one reel/post URL per line, written to --out (default reels.txt) and
echoed to stdout. Feed that straight into `reels-scrap run`.
"""

from __future__ import annotations

import argparse
import re
import sys
import time

import requests

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
        sys.exit(f"could not find a collection id in: {url_or_id!r}")
    return m.group(1)


def ig_cookies(browser: str) -> dict[str, str]:
    """Pull instagram.com cookies from the browser via yt-dlp's extractor."""
    from yt_dlp.cookies import extract_cookies_from_browser

    jar = extract_cookies_from_browser(browser)
    cookies = {c.name: c.value for c in jar if "instagram.com" in (c.domain or "")}
    if "sessionid" not in cookies:
        sys.exit(
            f"no Instagram 'sessionid' cookie in {browser}. "
            "Log into instagram.com in that browser first."
        )
    return cookies


def fetch(collection: str, cookies: dict[str, str], limit: int) -> list[dict]:
    """Page through the collection feed; return raw media dicts."""
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
    url = f"https://www.instagram.com/api/v1/feed/collection/{collection}/posts/"
    items: list[dict] = []
    max_id: str | None = None
    page = 0
    while True:
        params = {"max_id": max_id} if max_id else {}
        r = s.get(url, params=params, timeout=30)
        if r.status_code != 200:
            sys.exit(f"HTTP {r.status_code} from collection feed: {r.text[:300]}")
        data = r.json()
        batch = data.get("items", [])
        items.extend(batch)
        page += 1
        print(f"  page {page}: +{len(batch)} (total {len(items)})", file=sys.stderr)
        if len(items) >= limit or not data.get("more_available"):
            break
        max_id = data.get("next_max_id")
        if not max_id:
            break
        time.sleep(1.5)  # politeness
    return items[:limit]


def shortcode(media: dict) -> str | None:
    """A collection item wraps the post under `media`; pull its shortcode."""
    m = media.get("media", media)
    return m.get("code")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("collection", help="saved-collection URL or numeric id")
    ap.add_argument("--out", default="reels.txt", help="output file (default reels.txt)")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--browser", default="chrome")
    ap.add_argument(
        "--print-only", action="store_true", help="don't write --out, just print URLs"
    )
    args = ap.parse_args()

    cid = collection_id(args.collection)
    print(f"collection id: {cid}", file=sys.stderr)
    cookies = ig_cookies(args.browser)
    items = fetch(cid, cookies, args.limit)

    urls: list[str] = []
    for it in items:
        code = shortcode(it)
        if code:
            urls.append(f"https://www.instagram.com/reel/{code}/")
    # de-dup, preserve order
    seen: set[str] = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    print(f"found {len(urls)} reels/posts", file=sys.stderr)
    if not args.print_only:
        with open(args.out, "w") as f:
            f.write("\n".join(urls) + ("\n" if urls else ""))
        print(f"wrote {len(urls)} URLs -> {args.out}", file=sys.stderr)
    print("\n".join(urls))


if __name__ == "__main__":
    main()
