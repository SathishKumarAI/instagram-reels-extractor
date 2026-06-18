# Architecture

> How the reels research platform is structured: the module map, what each package owns, how data flows from a reel URL to a cited chat answer, and the backend↔frontend JSON contract.

The platform turns Instagram reels into a **local-first research corpus**: ingest → extract → structure → render → index → knowledge → search → chat, served behind a FastAPI backend and a React/shadcn UI. Everything runs on-device by default; cloud is a config swap, not a rewrite.

This document describes the **shipped system** in `src/reels_scrap/` (design source: [`docs/superpowers/specs/2026-06-18-research-platform-design.md`](superpowers/specs/2026-06-18-research-platform-design.md)). The end-to-end pipeline, the FastAPI backend, the React UI, knowledge aggregation, and RAG chat are all built and working; the only genuinely future work is the durable distributed job queue and SSE token-streaming (both marked **Planned** where they come up).

## Build status at a glance

| Layer | State | Where |
|-------|-------|-------|
| Models, config (with derived-path properties) | Built | `models.py`, `config.py` |
| Ingest (yt-dlp, instaloader, saved collections) | Built | `ingest/` |
| Extract (frames, transcript, OCR, vision) | Built | `extract/` |
| Structure + render (markdown, PDF, site) | Built | `structure.py`, `render/` |
| Rate limiting (vision concurrency + backoff) | Built | `ratelimit.py` |
| Search (embed + index + query) | Built | `search.py` |
| Knowledge (aggregate + optional synthesis) | Built | `knowledge/` |
| Chat (RAG → cited answers) | Built | `chat/` |
| Shared text-LLM helper | Built | `llm.py` |
| `api/` FastAPI backend | Built | `api/app.py`, `schemas.py` |
| `web/` React + shadcn UI | Built | `web/` |
| Docker (backend + web + compose) | Built | `docker/` |
| Persistent/distributed job queue (SQLite→Redis) | **Planned** (cloud phase) | spec §8 |
| Token-streaming (SSE) chat | **Planned** | spec §6 |

## Module map

Layout under `src/reels_scrap/`. Each module/package has **one job and a narrow interface** — the boundaries below are the contract. Some stages are flat modules (`search.py`, `structure.py`, `pipeline.py`), others are packages (`ingest/`, `extract/`, `knowledge/`, `chat/`, `api/`); the boundaries are the same either way.

```
src/reels_scrap/
├─ config.py    Config (+ derived-path properties: knowledge_dir, index_dir, logs_dir)
├─ models.py    Reel · Fact · Knowledge data model
├─ observability.py   logging + run_report manifest
├─ ratelimit.py vision semaphore + with_retry (exponential backoff)
├─ llm.py       claude_text — shared text-LLM helper (claude-cli | api)
├─ ingest/      ytdlp.py · instaloader_src.py · collection.py
├─ extract/     frames.py · transcript.py · ocr.py · vision.py
├─ structure.py genre assignment + genre-typed fields + per-reel markdown
├─ render/      pdf.py · docs_site.py
├─ knowledge/   aggregate.py · synthesize.py
├─ search.py    embed (fastembed) · build/refresh index · top-k query
├─ chat/        rag.py · prompts.py
├─ pipeline.py  ThreadPoolExecutor orchestration of the stages
├─ api/         app.py · schemas.py
└─ cli.py       run · serve · fetch-collection · index · search · knowledge · ask · ...
```

| Module | Responsibility | Must NOT do |
|--------|----------------|-------------|
| `config` / `models` | Data model (`Reel`, `Fact`), config loading, and the derived-path properties (`knowledge_dir`, `index_dir`, `logs_dir`) — the one place that knows the layout. | Touch the network or do any stage work. |
| `ingest` | Download media + metadata (URLs, profile, hashtag, saved collections); return `Reel` records with media on disk. | Know anything about extraction. |
| `extract` | Enrich a `Reel` in place — frames, transcript (whisper), OCR (easyocr), vision (Claude). Pure functions per modality. | Scrape or render. |
| `structure` | Assign `genre`, build genre-typed `structured` fields, render per-reel markdown. | Call out to download or embed. |
| `render` | Turn a structured `Reel` into PDF and the static docs site. | Re-extract or re-fetch. |
| `knowledge` | Aggregate all reels into topics by genre (deterministic — facts + hashtags + reels); optional per-topic Claude synthesis (cached). | Scrape; mutate reel records. |
| `search` | Embed text (fastembed), build/refresh the index, answer top-k queries. | Scrape. |
| `chat` | RAG: embed → retrieve → build cited context → Claude answer → cited `Answer` (retrieval-only fallback on LLM failure). | Scrape; bypass `search`. |
| `llm` | Shared `claude_text` helper used by vision, synthesis, and chat (`claude-cli` default, `api` optional). | Hold stage logic. |
| `ratelimit` | Process-wide vision semaphore + exponential-backoff retry — the one place vision concurrency is bounded. | Do stage work itself. |
| `api` | Thin HTTP layer; Pydantic schemas = the wire contract; serves `web/dist` in prod. | Hold business logic — delegate to the modules. |
| `pipeline` | Orchestrate stages with a `ThreadPoolExecutor`, gated by the vision semaphore. | — |
| `cli` | Operator entry point: one command per stage; `run` chains them. | Reimplement stage logic. |

**The boundary that matters most:** `search`/`knowledge`/`chat` only ever **read** `Reel` records + the index — they never scrape. Vision concurrency lives behind `ratelimit.py`, so every stage stays a simple, testable function.

> **Concurrency today vs. cloud:** the pipeline runs a `ThreadPoolExecutor` (`batch.workers`) with vision gated by a process-wide semaphore + backoff in `ratelimit.py`. A full **persistent/distributed job queue** (SQLite→Redis) is the cloud-phase step — **Planned** (spec §8), not built.

## Data flow

```
                         ┌─────────────────────────────────────────────┐
                         │  pipeline.py (ThreadPoolExecutor, batch.workers)│
                         │  vision gated by ratelimit.py semaphore+backoff │
                         └─────────────────────────────────────────────┘
   URL list / collection           │ runs per-reel stages, resumable by sidecar
   reels.txt / fetch-collection    ▼
  ┌──────────┐
  │  ingest  │  yt-dlp / instaloader / saved collection → Reel + media on disk
  └────┬─────┘        media → data/<id>...
       ▼
  ┌──────────┐  frames · transcript(whisper) · ocr(easyocr) · vision(Claude)
  │ extract  │  ── vision behind ratelimit.py (semaphore, concurrency 1–2 + backoff)
  └────┬─────┘
       ▼
  ┌───────────┐  genre + genre-typed `structured` fields + provenance facts
  │ structure │
  └────┬──────┘
       ▼
  ┌──────────┐  per-reel markdown / PDF / static site
  │  render  │  ──► output/markdown · output/pdfs · output/site
  └────┬─────┘
       ▼
  ┌──────────┐  ┌────────────┐
  │  search  │  │ knowledge  │  read-only consumers of Reel records + index
  │  index   │  │ aggregate  │
  └────┬─────┘  └─────┬──────┘
       │  output/index/*       output/knowledge/*.json
       ▼              ▼
  ┌─────────────────────────────────────────────┐
  │  api (FastAPI)  ── reels · knowledge · search │
  │                   · chat (RAG) · media        │
  └───────────────────────┬─────────────────────┘
                          │  JSON over HTTP (api/schemas.py)
                          ▼
  ┌─────────────────────────────────────────────┐
  │  web (Vite + React + shadcn)                 │
  │  Knowledge · Reels · Research Chat           │
  └─────────────────────────────────────────────┘
```

The **record of truth** is the per-reel JSON record under `data/`. Every downstream stage (render, search, knowledge, chat) is rebuildable from those records — re-running a later stage never requires re-scraping.

## Directory layout — inputs vs outputs

The layout is split two ways: **`data/`** holds everything that comes IN (downloaded media + the per-reel JSON record), and **`output/`** holds everything DERIVED (markdown, PDFs, site, knowledge, index, logs). The derived sub-dirs are resolved by **properties on `Config`** (`knowledge_dir`, `index_dir`, `logs_dir`) — the one place that knows the layout, so flipping local↔cloud is a single config change. Both roots are gitignored and bind-mounted in Docker.

```
data/                      # INPUTS, gitignored, bind-mounted in Docker
├─ <id>.json               # per-reel structured JSON — the record of truth
├─ <id>...                 # downloaded mp4 / jpg / wav / <id>_frames/ per reel
└─ cache/                  # whisper + fastembed model cache, IG session

output/                    # everything DERIVED (rebuildable), bind-mounted
├─ markdown/               # rendered .md
├─ pdfs/                   # rendered .pdf
├─ site/                   # static mkdocs site
├─ knowledge/              # knowledge.json + per-topic syntheses
├─ index/                  # search_index.npz + search_index.json
└─ logs/                   # run.log, run_report.json
```

> **Why split inputs/outputs (R10):** inputs are expensive/irreplaceable (scraped media, sessions, cookies); outputs are cheap and regenerable. Separating them means you can wipe `output/` to force a clean rebuild without re-downloading, and back up `data/` independently.

`config.yaml` carries `paths: { data_dir, output_dir }`; the derived sub-dirs hang off `Config`'s `*_dir` properties rather than being hardcoded across modules.

## Backend↔frontend JSON contract

The contract **is** the Pydantic schemas in `api/schemas.py` (spec §4) — one source of truth, shared by the FastAPI responses and the typed `web/` `api` client. All endpoints are live in `api/app.py`.

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /api/health` | `{ status: "ok" }` | liveness check |
| `GET /api/reels` | `[ReelSummary]` — card-grid fields | card grid |
| `GET /api/reels/{id}` | full record: `summary`, `structured`, `facts[]` (with `timestamp`/`frame`), `transcript`, `ocr`, `caption`, `media_url`, `pdf_url` | detail drawer |
| `GET /api/knowledge` | `{ topics: [{ name, genre, overview?, facts[], reels[] }] }` | `overview` present only if synthesis enabled |
| `GET /api/search?q=&k=` | `[{ reel_id, title, url, score, kind, snippet, timestamp? }]` | empty index → **409** |
| `POST /api/chat` | `{ answer, citations: [{ reel_id, title, url, score, snippet }] }` | on Claude failure → `answer=null`, `note` set, citations still returned |
| `GET /api/media/{id}/{kind}` | binary video / thumbnail stream | `kind` selects the media variant; backs the embedded `<video>` |

The backend serves the built `web/dist` bundle at `/` in production (single port); in dev, CORS is open to the Vite server on `:5173`.

Error contract (spec §12): empty index → `409`, missing reel → `404`, Claude CLI failure → **graceful fallback** (chat returns sources only; vision skips + records), all logged to `output/logs/run.log` and `run_report.json`.

> **Why null-answer over 500:** a throttled Claude CLI is a *recoverable* condition, not a server fault. Returning the retrieved sources lets the UI still show evidence and lets the user retry — same fallback philosophy as the vision stage (spec §6, §12).

The `Reel` model (`models.py`) is the shared shape behind most of these — see [the model source](../src/reels_scrap/models.py) for the authoritative field list (`Fact` carries `timestamp` + `frame` for provenance).

## See also

- [USAGE.md](USAGE.md) — install + every CLI command
- [SCALING.md](SCALING.md) — how the pipeline reaches ~100 reels/hour
- [DEPLOY.md](DEPLOY.md) — Docker + local→cloud migration
- [Design spec](superpowers/specs/2026-06-18-research-platform-design.md) — source of truth
