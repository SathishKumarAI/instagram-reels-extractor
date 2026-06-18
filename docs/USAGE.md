# Usage

> Install the platform, run the easy three-command flow, and tune everything through `config.yaml` — all local, no API key required.

The whole platform is driven by one CLI (`reels-scrap`) plus a config file. The happy path is three commands: **fetch a collection → run the pipeline → serve the UI**.

## Install

No sudo needed — a static ffmpeg ships via pip.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .
```

> First transcript/OCR/search run downloads local models one time (Whisper ~150 MB, easyocr, fastembed ~130 MB). `./setup.sh` is optional (system ffmpeg/tesseract via dnf).

**Vision needs the Claude CLI.** Vision and chat default to `claude-cli` (your subscription, no key). Make sure `claude` is on your `PATH` and logged in. To use the Anthropic API instead, set the backend to `api` and export `ANTHROPIC_API_KEY` (see [DEPLOY.md](DEPLOY.md)).

## The easy flow

```bash
reels-scrap fetch-collection <url>     # named saved collection → reels.txt
reels-scrap run                        # ingest → … → index → knowledge
reels-scrap serve                      # FastAPI backend + React UI on one port
```

One command per stage; `run` chains them; everything is resumable — re-running `run` only redoes incomplete stages (resume-by-sidecar).

> **Beyond the easy flow:** `reels-scrap knowledge` rebuilds the aggregated Knowledge Base (add `--synthesize` for cached Claude topic overviews), and `reels-scrap ask "<question>"` runs the RAG research chat from the CLI (cited answers). `serve` exposes both through the web UI.

## CLI commands

All commands take `--config / -c` (default `config.yaml`).

| Command | What it does | Example |
|---------|--------------|---------|
| `run` | Full pipeline: ingest → extract → structure → render → index → knowledge. Resumable. | `reels-scrap run -c config.yaml` |
| `fetch-collection <url>` | Enumerate a named saved collection into reel URLs (browser cookies, no password), one per line to `--out` (default `reels.txt`). | `reels-scrap fetch-collection https://... -b chrome` |
| `serve` | Launch the FastAPI backend + React UI on one port (`--host`/`--port`/`--reload`). | `reels-scrap serve -p 8000` |
| `knowledge` | Rebuild the aggregated Knowledge Base; `--synthesize` adds cached Claude topic overviews. | `reels-scrap knowledge --synthesize` |
| `ask "<question>"` | RAG research chat from the CLI — cited answer + sources (`-k` for retrieval depth). | `reels-scrap ask "system design caching" -k 8` |
| `ingest-cmd` | Download media + metadata only. | `reels-scrap ingest-cmd` |
| `extract-cmd` | Re-run extractors on already-ingested reels (no re-download). | `reels-scrap extract-cmd` |
| `render-cmd` | Re-render markdown + PDF + site from existing reel data. | `reels-scrap render-cmd` |
| `index` | Build/refresh the local semantic index over all reels. | `reels-scrap index` |
| `search "<query>"` | Semantic search across the archive (`-k` for result count). | `reels-scrap search "system design caching" -k 8` |
| `login <username>` | Create a local Instagram session (instaloader). Password/2FA stay on your machine. | `reels-scrap login myhandle` |

> **Why separate stage commands:** each stage reads/writes the per-reel JSON record, so you can re-run `extract-cmd` after tweaking `whisper_model` without re-downloading, or `render-cmd` after editing a template — without paying for vision again.

## Where inputs and outputs land

| Kind | Path | Notes |
|------|------|-------|
| URL list | `reels.txt` | what you feed in (one reel URL per line) |
| Per-reel record (truth) | `data/<id>.json` | rebuildable everything-from-here |
| Downloaded media | `data/<id>...` | mp4 / jpg / wav / `<id>_frames/` |
| Model + session cache | `data/cache/` | whisper, fastembed, IG session |
| Markdown | `output/markdown/<id>.md` | genre, structured fields, provenance table |
| PDF | `output/pdfs/<id>.pdf` | per-reel professional PDF |
| Static site | `output/site/index.html` | mkdocs master index → every reel + PDF |
| Knowledge | `output/knowledge/knowledge.json` + `<topic>.json` | aggregated topics |
| Search index | `output/index/search_index.{npz,json}` | local semantic index |
| Logs + manifest | `output/logs/run.log`, `run_report.json` | per-reel, per-stage success/error |

> **Inputs (`data/`) and outputs (`output/`) are deliberately separated** so you can wipe `output/` to force a clean rebuild without re-downloading anything. The derived sub-dirs hang off `Config`'s `knowledge_dir` / `index_dir` / `logs_dir` properties — see [ARCHITECTURE.md](ARCHITECTURE.md#directory-layout--inputs-vs-outputs).

## config.yaml knobs

The config toggles every stage. Full reference:

### `source` — what to pull

| Key | Default | Meaning |
|-----|---------|---------|
| `type` | `urls` | `urls` \| `profile` \| `hashtag` \| `saved` |
| `urls_file` | `reels.txt` | one reel URL per line (when `type=urls`) |
| `target` | `""` | profile handle (no `@`) or hashtag (no `#`) |
| `login` | `false` | use a logged-in IG session (ToS risk, rate limits) |
| `username` | `""` | IG username when `login=true` |
| `limit` | `50` | max reels for profile/hashtag/saved |

### `auth` — private reel access

| Key | Default | Meaning |
|-----|---------|---------|
| `cookies_from_browser` | `chrome` | `firefox` \| `chrome` \| `brave` \| `edge` — must be logged into IG |
| `cookies_file` | `""` | OR a path to exported `cookies.txt` |
| `browser_profile` | `""` | optional named browser profile |

> On Linux, Chrome cookie import needs `secretstorage` (bundled) and the **browser closed** while running.

### `extract` — which extractors run

| Key | Default | Meaning |
|-----|---------|---------|
| `caption` | `true` | caption + hashtags + mentions + stats (free, from metadata) |
| `transcript` | `true` | spoken audio → text via faster-whisper (local) |
| `ocr` | `true` | on-screen text via easyocr on sampled frames |
| `vision` | `true` | AI visual summary + genre-typed fields |
| `vision_backend` | `claude-cli` | `claude-cli` (subscription, no key) \| `api` |
| `whisper_model` | `base` | `tiny` \| `base` \| `small` \| `medium` \| `large-v3` |
| `whisper_device` | `auto` | `auto` \| `cpu` \| `cuda` |
| `whisper_language` | `en` | `""` = auto-detect; `en` forces English (less hallucination) |
| `vision_model` | `claude-sonnet-4-6` | `claude-opus-4-8` for max quality |
| `frame_every_sec` | `2` | sample 1 frame every N seconds for OCR/vision |
| `vision_concurrency` | `1` | parallel `claude -p` vision calls (semaphore-bounded; keep at 1–2 on the CLI) |
| `vision_max_retries` | `3` | retry a throttled vision call this many times before giving up |
| `vision_retry_backoff` | `5.0` | seconds, exponential — wait grows by `2^n` between retries |

> Force English (`whisper_language: en`) to stop multilingual hallucination on music/text reels.

### `batch` — concurrency

| Key | Default | Meaning |
|-----|---------|---------|
| `workers` | `3` | parallel reels for extract + render (1 = sequential) |

> Vision is gated separately by `extract.vision_concurrency` (a process-wide semaphore) so raising `batch.workers` never floods the throttle-prone Claude CLI. See [SCALING.md](SCALING.md) for how the two interact.

### `output` — what to render

| Key | Default | Meaning |
|-----|---------|---------|
| `pdf` | `true` | per-reel PDF |
| `docs_site` | `true` | mkdocs-material site (page-per-reel + master index) |
| `combined_pdf` | `false` | also emit one merged PDF with bookmarks |

### `paths` — where data lives

| Key | Default | Meaning |
|-----|---------|---------|
| `data_dir` | `data` | inputs root — downloaded media + per-reel JSON records |
| `output_dir` | `output` | derived artifacts root — markdown, PDFs, site, knowledge, index, logs |

> The derived sub-dirs (`knowledge/`, `index/`, `logs/`) are resolved by `Config`'s `*_dir` properties under `output_dir` — the one place the layout lives.

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| `search` returns nothing / 409 | Index not built | Run `reels-scrap index` first |
| Vision empty / silent failure | 3+ parallel `claude -p` calls get throttled (empty stderr) | Lower concurrency; pipeline backs off automatically — see [SCALING.md](SCALING.md) |
| Multilingual garbage in transcript | Whisper auto-detect on music | Set `whisper_language: en` |
| Cookie import fails on Linux | Browser open / no keyring | Close the browser; ensure `secretstorage` |
| Profile/hashtag crawl rate-limited | Large IG crawl | Lower `source.limit`; ingest stays sequential by design |

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — module map + data flow
- [SCALING.md](SCALING.md) — reaching ~100 reels/hour
- [DEPLOY.md](DEPLOY.md) — Docker + cloud migration
