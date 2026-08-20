"""Frame cache keys on the sampling spec, not on "a jpg exists".

The old cache reused whatever was on disk, so `frame_max_width: 1440` was inert
for every reel already sampled at 720 — a resolution experiment would have
measured "no effect" and been wrong about why.
"""
from __future__ import annotations

import json

import pytest

from reels_scrap.extract import frames as F


@pytest.fixture
def fake_ffmpeg(monkeypatch, tmp_path):
    """Stand in for ffmpeg: record each call, write the frames it would produce."""
    calls: list[list[str]] = []

    def run(cmd, **kw):
        calls.append(cmd)
        out = next(c for c in cmd if c.endswith("frame_%04d.jpg"))
        base = out.replace("frame_%04d.jpg", "")
        n = 2 if "fps=1/2" in " ".join(cmd) else 1   # coarser sampling -> fewer frames
        for i in range(1, n + 1):
            (tmp_path / f"frames/frame_{i:04d}.jpg").write_bytes(b"jpeg")
        assert base  # the pattern is a real path
        return type("P", (), {"returncode": 0})()

    monkeypatch.setattr(F, "ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(F, "ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(F.subprocess, "run", run)
    (tmp_path / "frames").mkdir()
    return calls


def test_same_spec_reuses_frames(fake_ffmpeg, tmp_path):
    out = tmp_path / "frames"
    F.sample_frames(tmp_path / "v.mp4", out, every_sec=2, max_width=720)
    F.sample_frames(tmp_path / "v.mp4", out, every_sec=2, max_width=720)
    assert len(fake_ffmpeg) == 1                      # second call was a cache hit
    assert json.loads((out / F.SPEC_FILE).read_text())["max_width"] == 720


def test_a_wider_frame_request_resamples(fake_ffmpeg, tmp_path):
    out = tmp_path / "frames"
    F.sample_frames(tmp_path / "v.mp4", out, every_sec=2, max_width=720)
    F.sample_frames(tmp_path / "v.mp4", out, every_sec=2, max_width=1440)
    assert len(fake_ffmpeg) == 2
    assert "scale='min(1440,iw)':-2" in " ".join(fake_ffmpeg[1])
    assert json.loads((out / F.SPEC_FILE).read_text())["max_width"] == 1440


def test_a_different_interval_resamples_and_drops_stale_frames(fake_ffmpeg, tmp_path):
    out = tmp_path / "frames"
    F.sample_frames(tmp_path / "v.mp4", out, every_sec=2, max_width=720)   # 2 frames
    got = F.sample_frames(tmp_path / "v.mp4", out, every_sec=8, max_width=720)  # 1 frame
    assert len(fake_ffmpeg) == 2
    # the second, coarser pass must not inherit frame_0002 from the first
    assert [p.name for p in got] == ["frame_0001.jpg"]
