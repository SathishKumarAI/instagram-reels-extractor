"""Audio -> text via faster-whisper (local, no API cost)."""

from __future__ import annotations

import contextlib
import os
import threading

from ..config import Config
from ..models import Reel, TranscriptSegment
from ..observability import log
from .frames import extract_audio, has_audio_stream

_MODEL_CACHE: dict[str, object] = {}
_MODEL_LOCK = threading.Lock()


def _enable_cuda_dlls() -> None:
    """Put the pip-installed cuDNN/cuBLAS DLLs where CTranslate2 can find them.

    Windows only. `nvidia-cudnn-cu12` / `nvidia-cublas-cu12` ship the DLLs inside
    site-packages, but CTranslate2 loads them by bare name — without this it fails
    with `Library cublas64_12.dll is not found` even though the file is right there.
    `os.add_dll_directory` alone is not enough; the PATH entry is what works.
    """
    import site
    import sys

    if not sys.platform.startswith("win"):
        return
    roots = [p for p in (site.getsitepackages() or []) if p]
    dirs = [
        os.path.join(root, "nvidia", pkg, "bin")
        for root in roots
        for pkg in ("cudnn", "cublas")
    ]
    dirs = [d for d in dirs if os.path.isdir(d)]
    if not dirs:
        return
    os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
    for d in dirs:
        with contextlib.suppress(OSError):
            os.add_dll_directory(d)


def _resolve_device(device: str) -> tuple[str, str]:
    """(device, compute_type). `auto` prefers CUDA — it is 12x faster here."""
    if device in {"auto", "cuda"}:
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda", "float16"
        except Exception:
            pass
        if device == "cuda":
            log.warning("whisper_device=cuda but no CUDA device is visible — using CPU")
    return "cpu", "int8"


def _get_model(name: str, device: str):
    """Batched pipeline on GPU, plain model on CPU.

    Measured on an RTX 5070 Ti, 62s of audio, large-v3:
      sequential 38.5s (1.6x realtime) · batched(8) 4.9s (**12.6x**)
    distil-large-v3 hits 41x but drops ~24% of the words and is English-only, which
    loses the non-English reels entirely. Batched large-v3 is the right trade.
    """
    key = f"{name}:{device}"
    with _MODEL_LOCK:  # serialize load; avoids double-load race under workers
        if key not in _MODEL_CACHE:
            _enable_cuda_dlls()
            from faster_whisper import BatchedInferencePipeline, WhisperModel

            dev, compute = _resolve_device(device)
            log.info("whisper: loading %s on %s (%s)", name, dev, compute)
            model = WhisperModel(name, device=dev, compute_type=compute)
            _MODEL_CACHE[key] = BatchedInferencePipeline(model=model) if dev == "cuda" else model
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
    # Task choice: with translate ON we let Whisper auto-detect the spoken language
    # and emit English (forcing a source language here is what garbles non-English
    # reels). With translate OFF we honour an explicit whisper_language, else detect.
    if cfg.extract.whisper_translate:
        task, lang = "translate", None
    else:
        task, lang = "transcribe", (cfg.extract.whisper_language or None)
    kw = {}
    if type(model).__name__ == "BatchedInferencePipeline":
        kw["batch_size"] = cfg.extract.whisper_batch_size
    segments, info = model.transcribe(
        str(audio),
        task=task,
        language=lang,
        **kw,
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

    # Provenance/quality: what language was spoken, how sure Whisper was, and
    # whether the text we kept was translated (so downstream doesn't over-trust it).
    detected = getattr(info, "language", "") or ""
    reel.transcript_language = detected
    reel.transcript_confidence = getattr(info, "language_probability", None)
    reel.transcript_translated = bool(
        cfg.extract.whisper_translate and detected and detected != "en"
    )
    if reel.transcript_translated:
        from ..observability import log

        log.info(
            "%s: transcript translated from %s (p=%.2f)",
            reel.id, detected, reel.transcript_confidence or 0.0,
        )
    if not reel.transcript_text:
        from ..observability import log

        log.info("%s: no clear speech detected (music/silent reel?) — try OCR/vision",
                 reel.id)
    return reel
