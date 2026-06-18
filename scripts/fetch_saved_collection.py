#!/usr/bin/env python3
"""Thin CLI wrapper around reels_scrap.ingest.collection.fetch_collection.

Prefer the integrated command:  reels-scrap fetch-collection <url>
This script stays for standalone use.

    python scripts/fetch_saved_collection.py "<collection-url-or-id>" \
        [--out reels.txt] [--limit 200] [--browser chrome] [--print-only]
"""

from __future__ import annotations

import argparse
import sys

from reels_scrap.ingest.collection import fetch_collection


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("collection", help="saved-collection URL or numeric id")
    ap.add_argument("--out", default="reels.txt")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--browser", default="chrome")
    ap.add_argument("--print-only", action="store_true")
    args = ap.parse_args()

    urls = fetch_collection(args.collection, browser=args.browser, limit=args.limit)
    print(f"found {len(urls)} reels/posts", file=sys.stderr)
    if not args.print_only:
        with open(args.out, "w") as f:
            f.write("\n".join(urls) + ("\n" if urls else ""))
        print(f"wrote {len(urls)} URLs -> {args.out}", file=sys.stderr)
    print("\n".join(urls))


if __name__ == "__main__":
    main()
