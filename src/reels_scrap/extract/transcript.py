"""Audio -> text via faster-whisper (local, no API cost)."""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..models import Reel, TranscriptSegment
from .frames import extract_audio, has_audio_stream

import threading

_MODEL_CACHE: dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def _get_model(name: str, device: str):
    key = f"{name}:{device}"
    with _MODEL_LOCK:  # serialize load; avoids double-load race under workers
        if key not in _MODEL_CACHE:
            from faster_whisper import WhisperModel

            compute = "int8" if device in {"cpu", "auto"} else "float16"
            dev = "cpu" if device == "auto" else device
            _MODEL_CACHE[key] = WhisperModel(name, device=dev, compute_type=compute)
    return _MODEL_CACHE[key]


def add_transcript(reel: Reel, cfg: Config) -> Reel:
    if not reel.video_path:
        return reel
    data_dir = cfg.data_dir
    video = data_dir / reel.video_path
    if not video.exists():
        return reel

    audio = data_dir / f"{reel.id}.wav"
    if not audio.exists():
        if not has_audio_stream(video):
            from ..observability import log

            log.info("%s: no audio stream (video-only reel) — skipping transcript", reel.id)
            return reel
        extract_audio(video, audio)
    reel.audio_path = audio.name

    model = _get_model(cfg.extract.whisper_model, cfg.extract.whisper_device)
    lang = cfg.extract.whisper_language or None  # None = auto-detect
    segments, info = model.transcribe(
        str(audio),
        language=lang,
        vad_filter=True,                  # drop non-speech (music/silence)
        condition_on_previous_text=False,  # stop hallucination loops
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,           # drop low-confidence garbage segments
        temperature=0.0,
    )

    segs: list[TranscriptSegment] = []
    parts: list[str] = []
    for s in segments:
        text = s.text.strip()
        # drop low-confidence / no-speech segments (anti-hallucination)
        if not text:
            continue
        if getattr(s, "no_speech_prob", 0) > 0.6 and getattr(s, "avg_logprob", 0) < -0.8:
            continue
        segs.append(TranscriptSegment(start=s.start, end=s.end, text=text))
        parts.append(text)
    reel.transcript = segs
    reel.transcript_text = " ".join(parts)
    if not reel.transcript_text:
        from ..observability import log

        log.info("%s: no clear speech detected (music/silent reel?) — try OCR/vision",
                 reel.id)
    return reel
