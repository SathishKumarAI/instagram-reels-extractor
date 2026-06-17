"""Opt-in ingest via instaloader: profile / hashtag / saved. May need login.

WARNING: Automated scraping violates Instagram ToS. Logged-in use risks account
bans and aggressive rate limits. Use sparingly, prefer your own content.

Engineering notes (resilience):
- Session is loaded from instaloader's own store (created via `instaloader --login`);
  passwords NEVER pass through this code or config.
- Idempotent: reels whose JSON sidecar already exists are skipped when resume=True.
- Rate-limit aware: instaloader's built-in RateController + polite inter-reel sleep,
  with exponential backoff on transient connection/429 errors.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config
from ..models import Reel

HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@([\w.]+)")


def _post_to_reel(post) -> Reel:
    caption = post.caption or ""
    rid = post.shortcode
    return Reel(
        id=rid,
        url=f"https://www.instagram.com/reel/{rid}/",
        author=post.owner_username,
        title=(caption.splitlines()[0][:120] if caption else rid),
        timestamp=post.date_utc.replace(tzinfo=timezone.utc),
        caption=caption,
        hashtags=HASHTAG_RE.findall(caption),
        mentions=MENTION_RE.findall(caption),
        likes=post.likes,
        comments=post.comments,
        views=getattr(post, "video_view_count", None),
        duration=getattr(post, "video_duration", None),
        video_path=f"{rid}.mp4",
        scraped_at=datetime.now(tz=timezone.utc),
    )


def _build_loader(cfg: Config):
    import instaloader

    data_dir = cfg.data_dir
    L = instaloader.Instaloader(
        dirname_pattern=str(data_dir),
        filename_pattern="{shortcode}",
        download_comments=False,
        save_metadata=False,
        download_geotags=False,
        post_metadata_txt_pattern="",
        request_timeout=cfg.source.request_timeout,
        max_connection_attempts=cfg.source.max_attempts,
        quiet=True,
    )

    if cfg.source.login:
        if not cfg.source.username:
            raise SystemExit("login=true requires source.username in config.yaml")
        try:
            L.load_session_from_file(cfg.source.username)
            print(f"  ✓ loaded session for {cfg.source.username}")
        except FileNotFoundError:
            raise SystemExit(
                f"\nNo saved Instagram session for {cfg.source.username!r}.\n"
                f"Create one locally (password/2FA stays on your machine):\n"
                f"  instaloader --login {cfg.source.username}\n"
                f"then re-run. Passwords are NEVER read from config or this code.\n"
            )
    return L


def _iter_posts(L, cfg: Config):
    import instaloader

    stype = cfg.source.type
    if stype == "profile":
        return instaloader.Profile.from_username(L.context, cfg.source.target).get_posts()
    if stype == "hashtag":
        return instaloader.Hashtag.from_name(L.context, cfg.source.target).get_posts()
    if stype == "saved":
        if not (cfg.source.login and cfg.source.username):
            raise SystemExit("source.type=saved requires login=true + username.")
        return instaloader.Profile.from_username(
            L.context, cfg.source.username
        ).get_saved_posts()
    raise ValueError(stype)


def ingest_instaloader(cfg: Config) -> list[Reel]:
    from instaloader.exceptions import (
        ConnectionException,
        TooManyRequestsException,
    )

    print(
        "  ! instaloader path — Instagram ToS compliance is YOUR responsibility. "
        "Rate-limited + polite sleeps enabled."
    )
    data_dir = cfg.data_dir
    L = _build_loader(cfg)

    reels: list[Reel] = []
    count = 0
    backoff = cfg.source.sleep_between

    for post in _iter_posts(L, cfg):
        if not getattr(post, "is_video", False):
            continue

        sidecar = data_dir / f"{post.shortcode}.json"
        if cfg.source.resume and sidecar.exists():
            reels.append(Reel.load(sidecar))
            count += 1
            print(f"  ↩ skip (cached) {post.shortcode}")
            if count >= cfg.source.limit:
                break
            continue

        # download with exponential backoff on rate limit / connection errors
        for attempt in range(1, cfg.source.max_attempts + 1):
            try:
                L.download_post(post, target=Path(data_dir).name)
                break
            except TooManyRequestsException:
                wait = backoff * (2 ** (attempt - 1))
                print(f"  ⏳ 429 rate-limited, sleeping {wait:.0f}s (attempt {attempt})")
                time.sleep(wait)
            except ConnectionException as e:
                wait = backoff * (2 ** (attempt - 1))
                print(f"  ⚠ conn error ({e}); retry in {wait:.0f}s (attempt {attempt})")
                time.sleep(wait)
            except Exception as e:  # noqa: BLE001
                print(f"  ! failed {post.shortcode}: {e}")
                break
        else:
            print(f"  ! gave up on {post.shortcode} after {cfg.source.max_attempts} attempts")
            continue

        reel = _post_to_reel(post)
        for ext in ("jpg", "png"):
            t = data_dir / f"{reel.id}.{ext}"
            if t.exists():
                reel.thumbnail_path = t.name
                break
        reel.save(data_dir)
        reels.append(reel)
        count += 1
        if count >= cfg.source.limit:
            break

        time.sleep(cfg.source.sleep_between)  # politeness between reels

    return reels
