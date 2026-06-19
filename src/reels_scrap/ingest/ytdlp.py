"""Public ingest via yt-dlp. No login required."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config
from ..models import Reel

HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@([\w.]+)")


def _reel_id_from_url(url: str) -> str:
    m = re.search(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-20:]


def _to_reel(info: dict, data_dir: Path) -> Reel:
    rid = info.get("id") or _reel_id_from_url(info.get("webpage_url", ""))
    caption = info.get("description") or info.get("title") or ""
    ts = info.get("timestamp")
    when = (
        datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
    )
    # locate downloaded file
    video = info.get("requested_downloads", [{}])[0].get("filepath") if info.get(
        "requested_downloads"
    ) else info.get("_filename")
    video_path = None
    if video:
        vp = Path(video)
        video_path = str(vp.relative_to(data_dir)) if vp.is_absolute() and data_dir in vp.parents else video

    return Reel(
        id=rid,
        url=info.get("webpage_url") or info.get("original_url") or "",
        author=info.get("uploader") or info.get("channel") or "",
        title=(caption.splitlines()[0][:120] if caption else rid),
        timestamp=when,
        caption=caption,
        hashtags=HASHTAG_RE.findall(caption),
        mentions=MENTION_RE.findall(caption),
        likes=info.get("like_count"),
        views=info.get("view_count"),
        comments=info.get("comment_count"),
        duration=info.get("duration"),
        video_path=video_path,
        thumbnail_path=None,
        scraped_at=datetime.now(tz=timezone.utc),
    )


def ingest_urls(
    cfg: Config, failures: dict[str, tuple[str, str]] | None = None
) -> list[Reel]:
    import yt_dlp

    from ..observability import log
    from . import read_urls_file

    urls = read_urls_file(cfg.source.urls_file)[: cfg.source.limit]
    data_dir = cfg.data_dir
    reels: list[Reel] = []

    ydl_opts = {
        "outtmpl": str(data_dir / "%(id)s.%(ext)s"),
        "writethumbnail": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "writeinfojson": False,
        "retries": cfg.source.max_attempts,
        "fragment_retries": cfg.source.max_attempts,
        "sleep_interval_requests": cfg.source.sleep_between,
    }

    # private-reel access: authenticate yt-dlp with your IG session cookies
    auth = cfg.auth
    if auth.cookies_file:
        ydl_opts["cookiefile"] = auth.cookies_file
        print(f"  ✓ using cookies file for private access: {auth.cookies_file}")
    elif auth.cookies_from_browser:
        profile = auth.browser_profile or None
        # yt-dlp expects a tuple: (browser, profile, keyring, container)
        ydl_opts["cookiesfrombrowser"] = (auth.cookies_from_browser, profile, None, None)
        print(f"  ✓ using {auth.cookies_from_browser} cookies for private access")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            # idempotent resume: skip if sidecar already exists
            rid_guess = _reel_id_from_url(url)
            cached = data_dir / f"{rid_guess}.json"
            if cfg.source.resume and cached.exists():
                reels.append(Reel.load(cached))
                print(f"  ↩ skip (cached) {rid_guess}")
                continue
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:  # noqa: BLE001
                log.error("ingest failed %s: %s", url, e)
                if failures is not None:
                    failures[rid_guess] = (url, str(e))
                continue
            reel = _to_reel(info, data_dir)
            # find thumbnail written next to video
            for ext in ("jpg", "png", "webp"):
                t = data_dir / f"{reel.id}.{ext}"
                if t.exists():
                    reel.thumbnail_path = t.name
                    break
            # normalize video path to filename in data_dir
            for f in data_dir.glob(f"{reel.id}.*"):
                if f.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}:
                    reel.video_path = f.name
                    break
            reel.save(data_dir)
            reels.append(reel)
    return reels
