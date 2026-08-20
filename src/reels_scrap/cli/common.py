"""Console, and the three helpers more than one command group needs.

Imported first by `cli/__init__`, so the stdout reconfigure below happens before
anything prints.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

from ..config import Config
from ..models import Reel

# Windows console/redirect defaults to cp1252 and dies on the ✓/✗ marks (and on any
# emoji in a caption). Do this before Console() is built so rich picks it up — it is
# what `PYTHONUTF8=1` was papering over.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

console = Console()


def load_reels(cfg: Config) -> list[Reel]:
    """Load previously-ingested reels from data_dir json sidecars."""
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


def open_in_browser(path: Path) -> None:
    import webbrowser

    webbrowser.open(path.resolve().as_uri())


def browser_spec(cfg: Config, override: str | None = None) -> str:
    """The browser (and profile) to read Instagram cookies from: `chrome` or
    `chrome:Default`.

    An explicit --browser wins, then an exported `auth.cookies_file` (the only
    path that works on Windows once Chrome 127+ encrypts cookies app-bound),
    then config `auth`. Naming the profile matters — without one yt-dlp picks the
    most-recently-used profile, which is often not the one logged into Instagram.
    """
    spec = override or cfg.auth.cookies_file
    if not spec:
        name = cfg.auth.cookies_from_browser or "chrome"
        spec = f"{name}:{cfg.auth.browser_profile}" if cfg.auth.browser_profile else name
    if spec.endswith(".txt"):
        # the yt-dlp download path reads cfg.auth directly, not this spec — point
        # it at the same file so enumerate and download use one set of cookies
        cfg.auth.cookies_file = spec
    return spec
