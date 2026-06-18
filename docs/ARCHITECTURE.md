# Architecture

> How the reels research platform is structured: the module map, what each package owns, how data flows from a reel URL to a cited chat answer, and the backend↔frontend JSON contract.

The platform turns Instagram reels into a **local-first research corpus**: ingest → extract → structure → render → index → knowledge → search → chat, served behind a FastAPI backend and a React/shadcn UI. Everything runs on-device by default; cloud is a config swap, not a rewrite.

This document describes the **target design** from [`docs/superpowers/specs/2026-06-18-research-platform-design.md`](superpowers/specs/2026-06-18-research-platform-design.md). The codebase is being implemented in phases — features not yet in `src/reels_scrap/` are marked **Planned**.

## Build status at a glance

| Layer | State | Where |
|-------|-------|-------|
| Core models, config | Built | `models.py`, `config.py` |
| Ingest (yt-dlp, instaloader) | Built | `ingest/` |
| Extract (frames, transcript, OCR, vision) | Built | `extract/` |
| Structure + render (markdown, PDF, site) | Built | `structure.py`, `render/` |
| Search (embed + index + query) | Built (flat module) | `search.py` |
| `core/` package (paths, observability, errors) | **Planned** (split out) | spec §3–4 |
| `pipeline/` queue + workers + ratelimit | **Planned** | spec §8 |
| `knowledge/` aggregate + synthesize | **Planned** | spec §5 |
| `chat/` RAG | **Planned** | spec §6 |
| `api/` FastAPI backend | **Planned** | spec §4, §7 |
| `web/` React + shadcn UI | **Planned** | spec §7 |

> **Why phased docs:** the design is approved end-to-end, but shipping is staged (spec §13, tickets #2–#12). Marking Planned keeps these docs honest while still describing the whole system.

## Module map

Target layout under `src/reels_scrap/`. Each package has **one job and a narrow interface** — the boundaries below are the contract.

```
src/reels_scrap/
├─ core/        config.py · models.py · paths.py · observability.py · errors.py
├─ ingest/      base.py · ytdlp.py · instaloader_src.py · collection.py
├─ extract/     frames.py · transcript.py · ocr.py · vision.py
├─ structure/   genres.py · markdown.py
├─ render/      pdf.py · docs_site.py
├─ knowledge/   aggregate.py · synthesize.py
├─ search/      embed.py · index.py · query.py
├─ chat/        rag.py · prompts.py
├─ api/         app.py · routers/{reels,knowledge,search,chat,media}.py · schemas.py
├─ pipeline/    orchestrator.py · queue.py · workers.py · ratelimit.py
└─ cli.py       run · serve · fetch-collection · index · search · ...
```

| Package | Responsibility | Must NOT do |
|---------|----------------|-------------|
| `core` | Data model (`Reel`, `Fact`), config loading, the single `paths` module, logging, typed errors. | Touch the network or do any stage work. |
| `ingest` | Download media + metadata; return `Reel` records with media on disk. | Know anything about extraction. |
| `extract` | Enrich a `Reel` in place — frames, transcript (whisper), OCR (easyocr), vision (Claude). Pure functions per modality. | Scrape or render. |
| `structure` | Assign `genre`, build genre-typed `structured` fields, render per-reel markdown. | Call out to download or embed. |
| `render` | Turn a structured `Reel` into PDF and the static docs site. | Re-extract or re-fetch. |
| `knowledge` | Aggregate all reels into topics (deterministic); optional per-topic synthesis (cached). | Scrape; mutate reel records. |
| `search` | Embed text (fastembed), build/refresh the index, answer top-k queries. | Scrape. |
| `chat` | RAG: retrieve → build cited context → Claude answer → map citations. | Scrape; bypass `search`. |
| `api` | Thin HTTP layer; Pydantic schemas = the wire contract. | Hold business logic — delegate to the modules. |
| `pipeline` | Orchestrate stages, the persistent queue, bounded concurrency, rate limiting, retries. | Be the *only* place that knows about concurrency (by design). |
| `cli` | Operator entry point: one command per stage; `run` chains them. | Reimplement stage logic. |

**The boundary that matters most:** `search`/`knowledge`/`chat` only ever **read** `Reel` records + the index — they never scrape. `pipeline` is the only place concurrency lives, so every stage stays a simple, testable function.

> **Current code vs. target:** today `search`, `structure`, `pipeline`, and `observability` are flat modules (`search.py`, `pipeline.py`, …) rather than packages, and `paths.py`/`errors.py`/`core/` don't exist yet. The split is ticket #2. Behaviour is the same; the import paths change.

## Data flow

```
                         ┌─────────────────────────────────────────────┐
                         │              pipeline/orchestrator           │
                         │   (only place that knows about concurrency)  │
                         └─────────────────────────────────────────────┘
   URL list / collection           │ enqueues per-reel, per-stage work
   data/input/urls/*.txt           ▼
        │              ┌──────────────────────┐   persistent, resumable
        ▼              │  pipeline/queue       │◄── output/logs/ (SQLite|JSONL)
  ┌──────────┐        └──────────────────────┘
  │  ingest  │  yt-dlp / instaloader → Reel + media on disk
  └────┬─────┘        media → data/input/media/<id>...
       ▼
  ┌──────────┐  frames · transcript(whisper) · ocr(easyocr) · vision(Claude)
  │ extract  │  ── vision behind ratelimit (token bucket, concurrency 1–2)
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

The **record of truth** is the per-reel JSON in `output/reels/`. Every downstream stage (render, search, knowledge, chat) is rebuildable from those records — re-running a later stage never requires re-scraping.

## Directory layout — inputs vs outputs

A single `core/paths.py` module is the **only** place that knows the layout, so flipping local↔cloud is one config change (spec §3). Everything under `data/` is gitignored and host-mounted in Docker.

```
data/                      # LOCAL store, gitignored, bind-mounted in Docker
├─ input/                  # everything that comes IN
│  ├─ urls/                # *.txt URL lists, collection dumps
│  ├─ media/               # downloaded mp4 / jpg / wav / <id>_frames/ per reel
│  ├─ cookies/             # exported cookies (optional, private reels)
│  └─ cache/               # whisper + fastembed model cache, IG session
└─ output/                 # everything DERIVED (rebuildable)
   ├─ reels/               # per-reel structured JSON — the record of truth
   ├─ markdown/            # rendered .md
   ├─ pdfs/                # rendered .pdf
   ├─ site/                # static mkdocs site (legacy/export)
   ├─ knowledge/           # knowledge.json + per-topic syntheses
   ├─ index/              # search_index.npz + search_index.json
   └─ logs/               # run.log, run_report.json, queue state
```

> **Why split input/output (R10):** inputs are expensive/irreplaceable (scraped media, sessions, cookies); outputs are cheap and regenerable. Separating them means you can wipe `output/` to force a clean rebuild without re-downloading, and back up `input/` independently.

`config.yaml` carries `paths: { data_dir, input_dir, output_dir, ... }`; all modules resolve paths through `core/paths.py` rather than hardcoding.

> **Current code note:** today config exposes `paths: { data_dir, output_dir }` and reel JSON + index land directly under `data/` and `output/` (flat), not the `input/output` split above. The split is ticket #2.

## Backend↔frontend JSON contract

The contract **is** the Pydantic schemas in `api/schemas.py` (spec §4) — one source of truth, shared by the FastAPI responses and the typed `web/` `api` client. All endpoints are **Planned** (ticket #7).

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /api/reels` | `[ReelCard]` — `{ id, title, author, genre, thumbnail_url, stats }` | card grid |
| `GET /api/reels/{id}` | `ReelDetail` — full record: `summary`, `structured`, `facts[]` (with `timestamp`/`frame`), `transcript`, `ocr`, `caption`, `media_url`, `pdf_url` | detail panel |
| `GET /api/knowledge` | `{ topics: [{ name, genre, overview?, facts[], reels[] }] }` | `overview` present only if synthesis enabled |
| `GET /api/search?q=&k=` | `[{ reel_id, title, url, score, kind, snippet, timestamp? }]` | empty index → **409** |
| `POST /api/chat` | `{ answer, citations: [{ reel_id, title, url, score, snippet }] }` | on Claude failure → `answer=null`, `note="synthesis unavailable"`, citations still returned |
| `GET /api/media/{id}` | binary video/thumbnail stream | backs the embedded `<video>` |

Error contract (spec §12): empty index → `409`, missing reel → `404`, Claude CLI failure → **graceful fallback** (chat returns sources only; vision skips + records), all logged to `output/logs/run.log` and `run_report.json`.

> **Why null-answer over 500:** a throttled Claude CLI is a *recoverable* condition, not a server fault. Returning the retrieved sources lets the UI still show evidence and lets the user retry — same fallback philosophy as the vision stage (spec §6, §12).

The `Reel` model (`core/models.py`) is the shared shape behind most of these — see [the model source](../src/reels_scrap/models.py) for the authoritative field list (`Fact` carries `timestamp` + `frame` for provenance).

## See also

- [USAGE.md](USAGE.md) — install + every CLI command
- [SCALING.md](SCALING.md) — how the pipeline reaches ~100 reels/hour
- [DEPLOY.md](DEPLOY.md) — Docker + local→cloud migration
- [Design spec](superpowers/specs/2026-06-18-research-platform-design.md) — source of truth
