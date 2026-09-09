# Usage

> Every command, every config knob, and the symptom table. The whole platform is one
> CLI plus a config file; the command you will actually run most days is `sync`.

## Install

**Windows** — [`scripts/setup-windows.ps1`](../scripts/setup-windows.ps1) does the whole
thing (venv, deps, web build, git hooks, local model, tests). Afterwards, every command
takes this shape:

```powershell
$env:PYTHONUTF8=1
.venv-win\Scripts\python.exe -m reels_scrap.cli <command>
```

Use `.venv-win`, not `.venv` — the latter is a Linux venv from the old box. `PYTHONUTF8`
is not optional: a few file reads still lack an explicit encoding, and Windows defaults
to cp1252, which cannot read this project's own JSON back.

**Linux / macOS** — the console script works directly:

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[cpu]"        # torch-free: transcript + vision + pdf + docs + dev
reels-scrap --help
```

> First transcript/search run downloads local models once (Whisper, fastembed ~130 MB).
> `pip install -e .` alone is lean by design — see the
> [extras table](SYNC.md#environments--two-track-gated-by-extras).

**Vision needs a backend.** Either the Claude Code CLI (`claude` on `PATH`, logged in —
no API key) or a local Ollama endpoint (`config-local.yaml`). `ANTHROPIC_API_KEY` +
`vision_backend: api` is the third option; see [DEPLOY.md](DEPLOY.md).

## The everyday flow

```bash
reels-scrap add-source "https://www.instagram.com/<you>/saved/<name>/<id>/"   # once per collection
reels-scrap sync -c config-local.yaml                                        # every run
reels-scrap serve                                                            # read it
```

Sync is idempotent and incremental: re-run any time, nothing already downloaded is
fetched again, failures dead-letter with a reason. Sessions come from
[INSTAGRAM-ACCESS.md](INSTAGRAM-ACCESS.md).

## Commands

All take `--config / -c` (default `config.yaml`).

### Sources and sync — what you use

| Command | What it does | Example |
|---|---|---|
| `sync` | Poll every enabled source, dedup against the pool, ingest only new reels, refresh docs + index + state. | `sync -c config-local.yaml` |
| `sync --only <name>` | Limit to named source(s); repeatable. | `sync --only saved-all` |
| `sync --retry-failed` | Re-attempt dead-lettered **ingest** failures. | `sync -c config.yaml --retry-failed` |
| `sync --backend <b>` | Override the vision backend for one run: `claude-cli` \| `api` \| `local`. | `sync --backend local` |
| `sync --claude-only` | Skip CPU whisper + OCR, vision only — much faster. `--full` flips back. | `sync --claude-only` |
| `add-source <url>` | Register a source in `sources.json`. | `add-source <url> --name topic-research --type collection` |
| `list-sources` | Show what is registered and enabled. | `list-sources` |
| `discover` | Propose reels from creators you already save and your top tags. Opt-in, budgeted, stops on the first 429. | `discover --browser cookies.txt --max-requests 40` |
| `login <user>` | Create a local instaloader session. Password and 2FA stay on your machine. | `login myhandle` |

### Pipeline stages — when you need one in isolation

| Command | What it does | Example |
|---|---|---|
| `run` | Full pipeline for the configured source: ingest → extract → structure → render. Resumable. | `run -c config.yaml` |
| `ingest-cmd` | Download media + metadata only. | `ingest-cmd` |
| `extract-cmd` | Re-run extractors on already-ingested reels — no re-download. | `extract-cmd -c config-local.yaml` |
| `extract-cmd --missing-vision` | **The repair pass.** Only reels with no summary and a video on disk. | `extract-cmd -c config-local.yaml --missing-vision` |
| `render-cmd` | Re-render markdown + PDF + site from existing records. | `render-cmd` |
| `index` | Build/refresh the semantic index (incremental; `--full` forces a rebuild). | `index` |
| `knowledge` | Rebuild the aggregated Knowledge Base; `--synthesize` adds cached Claude topic overviews. | `knowledge --synthesize` |

> **Why separate stage commands:** every stage reads and writes the same per-reel JSON,
> so you can re-run `extract-cmd` after changing a prompt without re-downloading, or
> `render-cmd` after editing a template — without paying for vision again.

**`--retry-failed` does not cover a failed vision.** That reel is downloaded, so `sync`
no longer counts it as new and will never revisit it; it stays summary-less until
`extract-cmd --missing-vision` looks for it.

### Reading the archive

| Command | What it does | Example |
|---|---|---|
| `search "<query>"` | Semantic search across summaries, structured fields, transcripts and facts. | `search "system design caching" -k 8` |
| `ask "<question>"` | RAG answer with citations, from the CLI. | `ask "what did I save about pickleball dinks"` |
| `serve` | FastAPI backend + built UI on one port (`--host`/`--port`/`--reload`). Binds `127.0.0.1`. | `serve -p 8000` |
| `collection <url>` | Saved collection → fetch, extract new, build a self-contained HTML doc, open it. Idempotent. | `collection <url>` |
| `fetch-collection <url>` | Enumerate a collection into reel URLs (`--out`, default `reels.txt`). | `fetch-collection <url> -b chrome` |
| `consolidate` | Rebuild every collection document + index from already-extracted data. | `consolidate` |

### Research

| Command | What it does | Example |
|---|---|---|
| `models list` | Installed vs available local vision models. Touches no network. | `models list` |
| `models pull <name>` | Explicit pull + rebuild at 32k context. Never automatic. | `models pull qwen3vl-8b` |
| `bench sample -n 30 --seed 0` | One fixed, genre-stratified sample, reused by every arm. | |
| `bench run --profile <p>` | Resumable, one model resident at a time; failures become error rows. | |
| `bench report` | Metrics + the written why-they-differ pass → `docs/research/BENCH-<date>.md`. | |

### Exit codes

Load-bearing — the scheduled sync distinguishes them.

| Code | Means |
|---|---|
| `0` | done |
| `1` | nothing to do (no enabled sources, no reels ingested) |
| `2` | invalid flag or missing config for the chosen backend |
| `3` | GPU busy before the run, or contended during it |

## Where inputs and outputs land

| Kind | Path | Notes |
|---|---|---|
| Source registry | `sources.json` | **gitignored** — names your private collections |
| URL list | `reels.txt` | one reel URL per line, when `source.type: urls` |
| Per-reel record (truth) | `data/<id>.json` | everything else is rebuildable from here |
| Downloaded media | `data/<id>…` | mp4 / jpg / wav / `<id>_frames/` |
| Model + session cache | `data/cache/` | whisper, fastembed, IG session |
| Markdown | `output/markdown/<id>.md` | genre, structured fields, provenance table |
| PDF | `output/pdfs/<id>.pdf` | per-reel |
| Static site | `output/site/index.html` | mkdocs master index |
| Collection docs | `output/collections/<slug>.html` | self-contained, thumbnails embedded |
| Knowledge | `output/knowledge/knowledge.json` + `<topic>.json` | aggregated topics |
| Search index | `output/index/search_index.{npz,json}` | local, incremental |
| Logs + manifest | `output/logs/run.log`, `run_report.json` | per-reel, per-stage; `run.log` rotates 5 MB × 3 |

> **Inputs and outputs are deliberately separated:** wipe `output/` to force a clean
> rebuild without re-downloading anything. Derived sub-dirs hang off `Config`'s
> `knowledge_dir` / `index_dir` / `logs_dir` properties — see
> [ARCHITECTURE.md](ARCHITECTURE.md#directory-layout--inputs-vs-outputs).

## Config reference

Defaults below are `config.yaml`'s. The other profiles differ where noted in
[../README.md](../README.md#config-profiles).

### `source` — what to pull

| Key | Default | Meaning |
|---|---|---|
| `type` | `urls` | `urls` \| `profile` \| `hashtag` \| `saved` |
| `urls_file` | `reels.txt` | one reel URL per line (when `type=urls`) |
| `target` | `""` | profile handle (no `@`) or hashtag (no `#`) |
| `login` | `false` | use a logged-in instaloader session |
| `username` | `""` | IG username when `login=true` |
| `limit` | `50` | max reels for profile/hashtag/saved |

`sync` reads `sources.json` instead of this block — `source` applies to `run`,
`ingest-cmd` and the single-source commands.

### `auth` — private reel access

| Key | Default | Meaning |
|---|---|---|
| `cookies_from_browser` | `chrome` | `firefox` \| `chrome` \| `brave` \| `edge` — Linux/macOS only |
| `cookies_file` | `""` | path to an exported Netscape `cookies.txt` — **the Windows path** |
| `browser_profile` | `Default` | name it; otherwise yt-dlp picks the most-recently-used profile |

Full comparison and the security rules: [INSTAGRAM-ACCESS.md](INSTAGRAM-ACCESS.md).

### `extract` — which extractors run

| Key | Default | Meaning |
|---|---|---|
| `caption` | `true` | caption + hashtags + mentions + stats (free, from metadata) |
| `transcript` | `true` | spoken audio → text, faster-whisper (local, CTranslate2 — not torch) |
| `ocr` | `false` | on-screen text via easyocr; needs torch. Up to `OCR_LINES = 15` lines reach the prompt when on |
| `vision` | `true` | genre + typed fields + provenance facts |
| `vision_backend` | `claude-cli` | `claude-cli` \| `api` \| `local` \| `auto` |
| `vision_local.base_url` | — | OpenAI-compatible endpoint, e.g. `http://127.0.0.1:11434/v1` |
| `vision_local.model` | — | e.g. `reels-vision` (built by `scripts/ollama-vision.Modelfile`) |
| `vision_local.timeout` | `240` | seconds; 6 frames at 720px on a 7B q8 |
| `vision_local.max_tokens` | `4000` | measured: 1500 truncated 1 reel in 12 mid-JSON, and every retry failed identically |
| `vision_local_fallback` | `true` | `false` = strict local, never egress; failures dead-letter |
| `whisper_model` | `large-v3` | `tiny` \| `base` \| `small` \| `medium` \| `large-v3` |
| `whisper_device` | `auto` | `auto` \| `cpu` \| `cuda` |
| `whisper_language` | `""` | `""` = auto-detect; `en` forces English (less hallucination on music) |
| `whisper_translate` | `true` | translate non-English speech to English |
| `vision_model` | `claude-sonnet-4-6` | the Claude path only; `tokens.model` records what actually ran |
| `frame_every_sec` | `2` | sample one frame every N seconds |
| `max_frames` | `6` | cap frames sent to vision |
| `frame_max_width` | `720` | measured: 1440 loses to 720 on every metric |
| `vision_concurrency` | `1` | local: 3 in flight at 32k ctx pushes a 9.4 GB model off a 16 GB card |
| `vision_max_retries` | `3` | retries per reel |
| `vision_retry_backoff` | `5.0` | seconds, exponential (5, 10, 20…) |

### `batch`, `output`, `paths`

| Key | Default | Meaning |
|---|---|---|
| `batch.workers` | `3` | parallel reels through extract + render (1 = sequential). Ingest stays sequential on purpose |
| `output.pdf` | `true` | per-reel PDF |
| `output.docs_site` | `true` | mkdocs-material site |
| `output.combined_pdf` | `false` | one merged PDF with bookmarks |
| `paths.data_dir` | `data` | inputs root |
| `paths.output_dir` | `output` | derived artifacts root |

> Vision is gated separately from `batch.workers` by a process-wide semaphore, so
> raising workers never floods the throttle-prone vision stage. See
> [SCALING.md](SCALING.md).

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `Exceeded 30 redirects` on every source | dead session (the file's own expiry date is not evidence) | re-export `cookies.txt` — [INSTAGRAM-ACCESS.md](INSTAGRAM-ACCESS.md#when-it-expires) |
| `gpu busy:` and exit 3 | a foreign model holds the card | `ollama ps`, wait, or `REELS_IGNORE_GPU=1` |
| every reel times out at 240 s | contention pushed layers to CPU | `ollama ps` must say `100% GPU` |
| reels with no summary never re-run | vision failed; they are not "new" | `extract-cmd --missing-vision` |
| `no JSON object in model output`, repeatedly | token budget ran out mid-JSON | raise `vision_local.max_tokens` |
| `search` returns nothing / 409 | index not built | `reels-scrap index` |
| multilingual garbage in transcript | whisper auto-detect on music | `whisper_language: en` |
| cookie import fails on Linux | browser open, or no keyring | close the browser; ensure `secretstorage` |
| `UnicodeDecodeError` / cp1252 | Windows default encoding | prefix `PYTHONUTF8=1` |
| profile/hashtag crawl rate-limited | large IG crawl | lower `source.limit`; ingest is sequential by design |

## See also

- [SYNC.md](SYNC.md) — the dedup model and the environment tracks
- [ARCHITECTURE.md](ARCHITECTURE.md) — module map + data flow
- [SCALING.md](SCALING.md) — reaching ~100 reels/hour
- [DEPLOY.md](DEPLOY.md) — Docker + cloud migration
