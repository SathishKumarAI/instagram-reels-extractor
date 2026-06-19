# Layer 00 — Architecture & Core

You are a Python platform architect. Your objective is to scaffold the
`insta_reels_scrap` repository: package layout, `pyproject.toml`, `config.yaml`,
and the `core/` package (config loader, the `Reel` data model, the
input/output `paths` module, errors, observability) that every other layer
builds on.

<context>
  <scope>
    This is the FOUNDATION layer. No ingest, extract, render, search, chat, api,
    or pipeline code yet — only the skeleton and `core/`. Every later layer
    imports from `core/`.
  </scope>
  <hard_requirement_paths>
    Inputs and outputs MUST live in separate directory trees, and exactly one
    module (`core/paths.py`) knows the layout so local↔cloud is one config change.

    data/
    ├─ input/   urls/  media/  cookies/  cache/
    └─ output/  reels/  markdown/  pdfs/  site/  knowledge/  index/  logs/
  </hard_requirement_paths>
  <core_model>
    The whole platform flows around one Pydantic v2 model, `Reel`, with nested
    `TranscriptSegment` and `Fact`. A `Fact` carries provenance (`timestamp`,
    `frame`) so any claim can be scrubbed back to the exact second/frame.
  </core_model>
</context>

## Instructions
1. **Repo scaffold.** Create:
   - `pyproject.toml` — project `reels-scrap`, Python `>=3.12`, `src/` layout,
     a `[project.scripts]` entry `reels-scrap = "reels_scrap.cli:app"`, and
     dependency groups: core (`pydantic>=2`, `pyyaml`, `typer`, `rich`), with
     later deps (yt-dlp, instaloader, faster-whisper, easyocr, imageio[ffmpeg],
     jinja2, weasyprint, mkdocs-material, fastembed, fastapi, uvicorn) added in
     their layers. Add a `[project.optional-dependencies] dev` with
     `pytest`, `pytest-cov`.
   - `.gitignore` (ignore `data/`, `.venv/`, `__pycache__/`, `web/node_modules/`,
     `web/dist/`, `*.egg-info/`).
   - `.env.example` (`ANTHROPIC_API_KEY=` for the API fallback only).
   - `README.md` stub and the package tree under `src/reels_scrap/` with the
     packages `core ingest extract structure render knowledge search chat api
     pipeline`, each an empty `__init__.py` for now except `core/`.
   - `tests/` package.
2. **`config.yaml`** at repo root. Mirror the existing toggles and add the new
   sections. Include at minimum:
   - `source: { type: urls|profile|hashtag|saved, urls_file, target, login,
     username, limit }`
   - `auth: { cookies_from_browser, cookies_file, browser_profile }`
   - `extract: { caption, transcript, ocr, vision, vision_backend: claude-cli,
     whisper_model: base, whisper_device: auto, whisper_language: en,
     vision_model: claude-sonnet-4-6, frame_every_sec: 2, vision_concurrency: 1,
     vision_rate_per_min: 20 }`
   - `batch: { ingest_workers: 8, whisper_workers: 4, workers: 3 }`
   - `output: { pdf: true, docs_site: true, combined_pdf: false }`
   - `knowledge: { synthesize: false, synthesis_model: claude-sonnet-4-6 }`
   - `search: { embed_model: BAAI/bge-small-en-v1.5, top_k: 8 }`
   - `chat: { backend: claude-cli, model: claude-sonnet-4-6, top_k: 8 }`
   - `paths: { data_dir: data, input_dir: data/input, output_dir: data/output }`
3. **`core/config.py`.** A `load_config(path="config.yaml") -> Config` that reads
   YAML into a typed Pydantic `Config` (nested models for each section above),
   applies defaults, and allows env-var override for `ANTHROPIC_API_KEY`. Expose
   a cached `get_config()` accessor.
4. **`core/paths.py`.** The single source of truth for the layout. Given a
   `Config`, expose properties/functions returning absolute `Path`s for every
   directory in the tree above (`input_urls`, `input_media`, `input_cookies`,
   `input_cache`, `output_reels`, `output_markdown`, `output_pdfs`,
   `output_site`, `output_knowledge`, `output_index`, `output_logs`) plus
   helpers: `reel_json(id)`, `reel_media_dir(id)`, `frames_dir(id)`. Add an
   `ensure_dirs()` that creates the whole tree. Every other module MUST resolve
   paths through this — nothing hard-codes `data/`.
5. **`core/models.py`.** Define `TranscriptSegment`, `Fact` (text, timestamp,
   frame), and `Reel` with: identity (id, url, author, title, timestamp);
   metadata (caption, hashtags, mentions, likes, views, comments, duration);
   media paths (video_path, thumbnail_path, audio_path, all relative to
   data_dir); extracted text (transcript[], transcript_text, ocr_text[], summary,
   genre, structured dict, facts[]); render paths (markdown_path, pdf_path); and
   `scraped_at`. Add `slug` property, `json_path(output_reels_dir)`, `save(dir)`,
   and `load(path)` classmethod (Pydantic JSON round-trip).
6. **`core/errors.py`.** Typed exceptions used across layers:
   `IngestError`, `ExtractError`, `VisionUnavailable`, `EmptyIndexError`,
   `ReelNotFound`, `SynthesisUnavailable`. Keep them simple subclasses of a base
   `ReelsScrapError`.
7. **`core/observability.py`.** A `get_logger(name)` (rich-formatted) and a
   `RunReport` helper that accumulates per-stage successes/failures/skips and
   writes `output/logs/run_report.json` + appends to `output/logs/run.log`.
8. **`cli.py` stub.** A Typer `app` with placeholder commands `run`, `serve`,
   `fetch-collection`, `index`, `search` that each print "not implemented yet"
   (real bodies arrive in later layers). Wire `ensure_dirs()` to run on startup.
9. **Tests.** `tests/test_paths.py` (input/output separation, every dir resolves
   under `data/`, `ensure_dirs` creates the tree) and `tests/test_models.py`
   (`Reel` save→load round-trip preserves facts with provenance).

## Constraints
- MUST use Pydantic v2 and the `src/` layout.
- MUST make `core/paths.py` the ONLY place that knows the directory layout.
- MUST keep input and output trees strictly separate; no derived artifact under
  `data/input/`, no raw download under `data/output/`.
- MUST keep `data/` gitignored.
- MUST NOT add ingest/extract/render/api logic here — stubs only outside `core/`.
- MUST NOT hard-code absolute machine paths; resolve relative to repo/config.

## Output format
Paste-ready files, each in its own fenced block headed by its path, in this
order: `pyproject.toml`, `.gitignore`, `.env.example`, `config.yaml`,
`src/reels_scrap/core/config.py`, `core/paths.py`, `core/models.py`,
`core/errors.py`, `core/observability.py`, `src/reels_scrap/cli.py`, the empty
`__init__.py` files (one block listing them), and the two test files. End with
the exact commands to install (`pip install -e ".[dev]"`) and run the tests.

Reason briefly in a `<thinking>` block first, then output the files.
