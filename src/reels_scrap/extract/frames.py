"""Shared helper: sample frames from a reel video via ffmpeg."""

from __future__ import annotations

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
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "ffmpeg not found. Install via `pip install imageio-ffmpeg` or `./setup.sh`."
        ) from e


def ensure_ffmpeg() -> None:
    ffmpeg_bin()  # raises if unavailable


def sample_frames(video: Path, out_dir: Path, every_sec: int = 2) -> list[Path]:
    """Extract 1 frame every `every_sec` seconds. Returns sorted frame paths."""
    ensure_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%04d.jpg"
    fps = f"1/{max(1, every_sec)}"
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        "-vf", f"fps={fps}",
        "-q:v", "3",
        str(pattern),
    ]
    subprocess.run(cmd, check=True)
    return sorted(out_dir.glob("frame_*.jpg"))


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
