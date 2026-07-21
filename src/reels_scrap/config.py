"""Typed config loaded from config.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

SOURCE_TYPES = {"urls", "profile", "hashtag", "saved", "rss", "arxiv", "github"}
WHISPER_MODELS = {"tiny", "base", "small", "medium", "large-v2", "large-v3"}
WHISPER_DEVICES = {"auto", "cpu", "cuda"}


class SourceCfg(BaseModel):
    type: str = "urls"  # urls | profile | hashtag | saved
    urls_file: str = "reels.txt"
    target: str = ""
    login: bool = False
    username: str = ""
    limit: int = Field(default=50, ge=1, le=10000)
    resume: bool = True          # skip reels already downloaded (idempotent)
    request_timeout: float = Field(default=30.0, gt=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    sleep_between: float = Field(default=2.0, ge=0)  # politeness / anti rate-limit

    @model_validator(mode="after")
    def _check(self):
        if self.type not in SOURCE_TYPES:
            raise ValueError(f"source.type must be one of {sorted(SOURCE_TYPES)}, got {self.type!r}")
        if self.type in {"profile", "hashtag"} and not self.target:
            raise ValueError(f"source.type={self.type} requires source.target")
        if self.type == "saved" and not (self.login and self.username):
            raise ValueError("source.type=saved requires login=true + username")
        if self.login and not self.username:
            raise ValueError("source.login=true requires source.username")
        return self


class VisionLocalCfg(BaseModel):
    """Self-hosted, OpenAI-compatible vision endpoint (vLLM / Ollama / any /v1).

    Used when extract.vision_backend == "local". Runs on your own GPU box on the
    LAN — frames never leave your network. Default model is the open-weights
    Kimi-VL (moonshotai/Kimi-VL-A3B-Instruct), a compact multimodal VLM.
    """

    base_url: str = ""       # e.g. http://gpu-box:8000/v1  (empty until you wire the box)
    model: str = "moonshotai/Kimi-VL-A3B-Instruct"
    api_key: str = ""        # optional; vLLM usually needs none, Ollama none
    timeout: float = Field(default=120.0, ge=5)
    max_tokens: int = Field(default=900, ge=64, le=4096)


class ExtractCfg(BaseModel):
    caption: bool = True
    transcript: bool = True
    ocr: bool = False
    vision: bool = False
    whisper_model: str = "base"
    whisper_device: str = "auto"
    whisper_language: str = ""   # "" = auto-detect; set e.g. "en" to force a source language
    # Non-English reels: Whisper's built-in "translate" task emits clean English
    # regardless of the spoken language (auto-detected). ON by default so a Hindi/
    # Tamil/etc. reel yields readable English instead of a forced-English garble.
    # For English audio it's a near-identity transcription. Set false to keep the
    # raw source-language transcript verbatim.
    whisper_translate: bool = True
    vision_model: str = "claude-sonnet-4-6"
    # auto (api if ANTHROPIC_API_KEY else claude-cli) | claude-cli | api | local
    vision_backend: str = "auto"
    vision_local: VisionLocalCfg = Field(default_factory=VisionLocalCfg)
    # When a "local" vision call fails (endpoint down / malformed JSON after retries),
    # fall back to claude-cli so every reel still gets extracted. NOTE: fallback frames
    # DO leave the machine (egress to Claude). Set false for strict local-only.
    vision_local_fallback: bool = True
    frame_every_sec: int = Field(default=2, ge=1, le=30)
    # Frames sent to vision. Fewer = faster + cheaper (esp. via claude-cli, where each
    # frame is an agentic Read turn). 6 is a good quality/cost balance; 4 for speed.
    max_frames: int = Field(default=6, ge=1, le=16)
    # Downscale sampled frames to this max width (px). Image tokens scale with pixel
    # count, so 720 from a 1080-wide reel ≈ 2-3× fewer tokens with negligible quality
    # loss for genre/summary. 0 = keep native resolution.
    frame_max_width: int = Field(default=720, ge=0, le=1920)
    ocr_min_confidence: float = Field(default=0.45, ge=0, le=1)  # drop low-conf OCR junk
    # Scaling knobs: the vision LLM is the throughput bottleneck. Parallel
    # `claude -p` calls throttle (3-way already fails), so vision is gated to a
    # small concurrency with retry/backoff while transcript+OCR stay parallel.
    vision_concurrency: int = Field(default=1, ge=1, le=8)
    vision_max_retries: int = Field(default=3, ge=1, le=10)
    vision_retry_backoff: float = Field(default=5.0, ge=0)  # seconds, exponential

    @model_validator(mode="after")
    def _check(self):
        if self.whisper_model not in WHISPER_MODELS:
            raise ValueError(f"extract.whisper_model must be one of {sorted(WHISPER_MODELS)}")
        if self.whisper_device not in WHISPER_DEVICES:
            raise ValueError(f"extract.whisper_device must be one of {sorted(WHISPER_DEVICES)}")
        if self.vision_backend not in {"auto", "claude-cli", "api", "local"}:
            raise ValueError("extract.vision_backend must be 'auto', 'claude-cli', 'api' or 'local'")
        if self.vision_backend == "local" and not self.vision_local.base_url:
            raise ValueError(
                "extract.vision_backend='local' requires extract.vision_local.base_url "
                "(your OpenAI-compatible GPU endpoint, e.g. http://gpu-box:8000/v1)"
            )
        return self


class OutputCfg(BaseModel):
    pdf: bool = True
    docs_site: bool = True
    combined_pdf: bool = False


class BatchCfg(BaseModel):
    workers: int = Field(default=3, ge=1, le=16)  # parallel reels for extract+render


class PathsCfg(BaseModel):
    data_dir: str = "data"
    output_dir: str = "output"


BROWSERS = {"firefox", "chrome", "chromium", "brave", "edge", "vivaldi", "opera", "safari"}


class AuthCfg(BaseModel):
    """Auth for accessing PRIVATE reels you have access to (your account / accounts you follow).

    Pick ONE:
      - cookies_from_browser: pull IG login cookies live from a logged-in browser
        profile (e.g. "firefox"). Easiest; browser must be logged into Instagram.
      - cookies_file: path to an exported Netscape cookies.txt.
    Cookies are session credentials — treat as secret (gitignored).
    """

    cookies_from_browser: str = ""   # firefox | chrome | brave | edge | ...
    cookies_file: str = ""           # path to cookies.txt
    browser_profile: str = ""        # optional named browser profile

    @model_validator(mode="after")
    def _check(self):
        b = self.cookies_from_browser
        if b and b not in BROWSERS:
            raise ValueError(f"auth.cookies_from_browser must be one of {sorted(BROWSERS)}")
        return self

    @property
    def enabled(self) -> bool:
        return bool(self.cookies_from_browser or self.cookies_file)


class Config(BaseModel):
    source: SourceCfg = SourceCfg()
    auth: AuthCfg = AuthCfg()
    extract: ExtractCfg = ExtractCfg()
    output: OutputCfg = OutputCfg()
    batch: BatchCfg = BatchCfg()
    paths: PathsCfg = PathsCfg()

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text()) or {}
        return cls.model_validate(raw)

    @property
    def data_dir(self) -> Path:
        p = Path(self.paths.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_dir(self) -> Path:
        p = Path(self.paths.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _sub(self, parent: Path, name: str) -> Path:
        p = parent / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Derived output sub-dirs — one place that knows the layout, so the
    # local→cloud move is a single config change. `data_dir` holds INPUTS
    # (downloaded media + the per-reel JSON record); `output_dir` holds
    # everything DERIVED.
    @property
    def knowledge_dir(self) -> Path:
        return self._sub(self.output_dir, "knowledge")

    @property
    def index_dir(self) -> Path:
        return self._sub(self.output_dir, "index")

    @property
    def logs_dir(self) -> Path:
        return self._sub(self.output_dir, "logs")
