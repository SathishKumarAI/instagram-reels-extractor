"""Shared helper: sample frames from a reel video via ffmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    """Resolve ffmpeg: system PATH first, else the pip static binary."""
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(
            "ffmpeg not found. Install via `pip install imageio-ffmpeg` or `./setup.sh`."
        ) from e


def ensure_ffmpeg() -> None:
    ffmpeg_bin()  # raises if unavailable


SPEC_FILE = ".frames.json"


def _spec(out_dir: Path) -> dict:
    p = out_dir / SPEC_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def sample_frames(video: Path, out_dir: Path, every_sec: int = 2,
                  force: bool = False, max_width: int = 0) -> list[Path]:
    """Extract 1 frame every `every_sec` seconds. Returns sorted frame paths.

    Cached, but **keyed on the sampling spec** — `every_sec` and `max_width` are
    written to `.frames.json` beside the frames and re-sampled when they change.
    Keying on existence alone made both settings inert for any reel already on
    disk: raising `frame_max_width` from 720 changed nothing for 755 reels, and an
    experiment on frame resolution would have measured "no effect" and been wrong.

    `max_width` > 0 downscales frames to that width (keeping aspect) — fewer pixels
    means fewer vision image tokens, at negligible quality cost for genre/summary.
    """
    ensure_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    want = {"every_sec": int(every_sec), "max_width": int(max_width or 0)}
    cached = sorted(out_dir.glob("frame_*.jpg"))
    if cached and not force and _spec(out_dir) == want:
        return cached
    for stale in cached:            # a coarser spec yields fewer frames; leftovers
        stale.unlink(missing_ok=True)   # from the old one would be silently mixed in
    pattern = out_dir / "frame_%04d.jpg"
    fps = f"1/{max(1, every_sec)}"
    vf = f"fps={fps}"
    if max_width and max_width > 0:
        # scale down only if wider than max_width; -2 keeps even height + aspect
        vf += f",scale='min({max_width},iw)':-2"
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        "-vf", vf,
        "-q:v", "3",
        str(pattern),
    ]
    subprocess.run(cmd, check=True)
    (out_dir / SPEC_FILE).write_text(json.dumps(want), encoding="utf-8")
    return sorted(out_dir.glob("frame_*.jpg"))


def has_audio_stream(video: Path) -> bool:
    """True if the video carries at least one audio stream.

    Video-only reels (no audio track) are valid; probing here lets the
    transcript stage skip them cleanly instead of crashing on ffmpeg's
    "Output file does not contain any stream" (exit 234).
    """
    ensure_ffmpeg()
    # ffmpeg has no probe-only mode; -i to a null muxer prints stream info to stderr.
    cmd = [ffmpeg_bin(), "-hide_banner", "-i", str(video)]
    out = subprocess.run(cmd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    return "Audio:" in out


def extract_audio(video: Path, out_path: Path) -> Path:
    """Extract mono 16kHz wav for whisper."""
    ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        "-ac", "1", "-ar", "16000", "-vn",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path
