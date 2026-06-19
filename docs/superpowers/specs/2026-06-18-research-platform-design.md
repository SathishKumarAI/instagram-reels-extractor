# Design Spec — Reels Research Platform

**Date:** 2026-06-18
**Status:** approved (design); implementation in phases
**Author:** Sathish Kumar (+ Claude)

## 1. Goal

Turn the existing `insta_reels_scrap` pipeline (reels → text → PDF/docs + local
semantic search) into a **local-first research platform**: a modern React +
shadcn UI over a FastAPI backend, with an aggregated **Knowledge Base** view and
a **Research Chat** (RAG, cited answers) over the scraped corpus. Built to scrape
**~100 reels/hour**, run mostly **local** (Docker), and migrate to **cloud**
later with minimal change. Ships with **replication prompts** so the whole
project can be regenerated from scratch.

## 2. Requirements (from the user)

| # | Requirement | Where addressed |
|---|-------------|-----------------|
| R1 | Knowledge page + chat Q&A | §5 knowledge, §6 chat, §7 frontend |
| R2 | React + shadcn modern UI | §7 |
| R3 | Vite + React + FastAPI stack | §4, §7 |
| R4 | Chat via Claude CLI (subscription, no key) | §6 |
| R5 | Modular code | §3, §4 |
| R6 | Replication prompts for future rebuild | §10 |
| R7 | ~100 reels/hour throughput | §8 |
| R8 | Local now, cloud later | §4, §8, §9 |
| R9 | Docker | §9 |
| R10 | Data saved to local dir; inputs & outputs in **separate** dirs | §3 |
| R11 | Easy flow, modular | §3, §4, §11 |
| R12 | Docs, prompts, tickets, worklogs maintained as we go | §10, §12 |

## 3. Directory layout — inputs vs outputs separated (R10)

A single `paths` module is the only place that knows the layout, so local↔cloud
is one config change.

```
data/                      # LOCAL store, gitignored, host-mounted in Docker
├─ input/                  # everything that comes IN
│  ├─ urls/                # *.txt url lists, collection dumps
│  ├─ media/               # downloaded mp4 / jpg / wav / <id>_frames/ per reel
│  ├─ cookies/             # exported cookies (optional)
│  └─ cache/               # whisper + fastembed model cache, IG session
└─ output/                 # everything DERIVED
   ├─ reels/               # per-reel structured JSON (the record of truth)
   ├─ markdown/            # rendered .md
   ├─ pdfs/                # rendered .pdf
   ├─ site/                # static mkdocs site (legacy/export)
   ├─ knowledge/           # knowledge.json + per-topic syntheses
   ├─ index/              # search_index.npz + search_index.json
   └─ logs/               # run.log, run_report.json, queue state
```

`config.yaml` gets `paths: { data_dir, input_dir, output_dir, ... }` with these
defaults; all modules resolve through `core/paths.py`.

## 4. Module architecture (R5, R11)

```
src/reels_scrap/
├─ core/        config.py · models.py · paths.py · observability.py · errors.py
├─ ingest/      base.py · ytdlp.py · instaloader_src.py · collection.py (was the script)
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

**Boundaries.** Each package has one job and a narrow interface:
- `ingest` returns `Reel` records + media on disk; knows nothing about extraction.
- `extract` enriches a `Reel` in place; pure functions per modality.
- `search`/`knowledge`/`chat` read `Reel` records + the index; never scrape.
- `api` is a thin HTTP layer; all logic lives in the modules it calls.
- `pipeline` orchestrates; it is the only place that knows about concurrency.

Backend↔frontend contract = the JSON schemas in `api/schemas.py` (Pydantic).

## 5. Knowledge Base (R1)

`knowledge/aggregate.py`: read all `output/reels/*.json`, group by `genre`
(then by shared hashtags/topic where present), collect each group's summaries +
provenance facts + source reel refs. Pure Python, deterministic, cheap.

`knowledge/synthesize.py` (optional, cached): one `claude -p` call per topic to
produce a short "what this topic covers" overview. Cached to
`output/knowledge/<topic>.json`; only regenerated when member reels change.
Default OFF (cost lever); enabled via config/flag.

Output: `GET /api/knowledge` → `{ topics: [{ name, genre, overview?, facts[],
reels[] }] }`.

## 6. Research Chat — RAG (R1, R4)

`chat/rag.py` flow:
1. embed question with fastembed (same model as the index)
2. retrieve top-k (default 8) from `search/query.py`
3. build a context block: each snippet tagged `[<reel_id>]` with title + fact/summary
4. `claude -p` with `chat/prompts.py` research prompt: *answer only from context,
   cite sources as `[reel_id]`, say "not in the archive" if unsupported*
5. parse answer; map `[reel_id]` cites back to reel metadata
6. return `{ answer, citations: [{reel_id, title, url, score, snippet}] }`

**Resilience:** Claude CLI failure (we hit this live — empty-stderr throttle) →
return retrieved sources with `answer=null` + `note="synthesis unavailable"`.
Same fallback philosophy as the vision-stage fix. No streaming in v1 (SSE later).

## 7. Frontend — Vite + React + shadcn (R2, R3)

`web/` — Vite + React + TS + Tailwind + shadcn/ui, Catppuccin Mocha, dark default.
- **Layout:** sidebar (Knowledge · Reels · Research), top search.
- **Knowledge Base:** topic cards → overview + key facts + source reel chips; filter bar → `/api/search`.
- **Reels:** responsive card grid (thumb, title, author, genre, stats) → detail
  panel (summary, facts table w/ timestamps, transcript, OCR, caption, embedded
  `<video>` from `/api/media`, PDF link).
- **Research Chat:** message thread; each answer renders cited source chips
  (deep-link to reel detail) + an expandable "retrieved snippets" section.
- Data via a typed `api` client (fetch). Dev proxy :5173→:8000; prod served by FastAPI.

## 8. Scaling to ~100 reels/hour (R7, R8)

~100/hr = 1 reel / 36s. Bottlenecks: **Claude vision** (quota + concurrency —
3 parallel `claude -p` calls already throttled to empty-stderr failures) and
**whisper** (CPU). Design:

- **Stage-decoupled pipeline** (`pipeline/`): ingest (IO-bound, high parallelism)
  feeds a queue; extract workers pull from it. Stages independent + idempotent.
- **Bounded concurrency per stage** (config): ingest workers (e.g. 8), whisper
  pool (≈ CPU cores), **vision concurrency 1–2** behind a **token-bucket rate
  limiter** (`ratelimit.py`) + exponential backoff on CLI failure.
- **Persistent, resumable queue** (`queue.py`): SQLite or JSONL of
  `{reel_id, stage, status, attempts}` under `output/logs/`. Survives restart;
  re-run resumes incomplete stages only (builds on existing resume-by-sidecar).
- **Per-stage retry** with backoff; failures recorded in `run_report.json`
  (provenance fix already in place).
- **Cloud-future:** swap queue backend (SQLite→Redis/RQ) and flip vision to the
  **Claude API** backend for real concurrency. Interfaces unchanged.

Config knobs: `batch.ingest_workers`, `batch.whisper_workers`,
`extract.vision_concurrency`, `extract.vision_rate_per_min`, `extract.vision_backend`.

## 9. Docker (R8, R9)

- `docker/Dockerfile.backend` — Python 3.12, ffmpeg (imageio), whisper, fastembed,
  fastapi/uvicorn. Runs `reels-scrap serve`.
- `docker/Dockerfile.web` — Node build → static, served by backend (single port) or nginx.
- `docker/docker-compose.yml` — backend + (optional) web; **bind-mount `./data`**
  so all input/output stays on the host (R10). Model cache persisted via
  `data/input/cache`.
- **Claude CLI in container:** CLI auth doesn't transfer cleanly into a container.
  Local: mount host `~/.claude` read-only OR run backend on host. **Cloud:** use
  `vision_backend: api` + `chat backend: api` with `ANTHROPIC_API_KEY`. Documented
  in `docs/DEPLOY.md`; default compose targets local with host claude mounted.

## 10. Replication prompts + docs (R6, R12)

`prompts/` — house prompt-skeleton style (role + XML context + numbered steps +
MUST/MUST NOT + output format), each regenerates one layer:
`00-architecture.md`, `01-ingest.md`, `02-extract.md`, `03-structure-render.md`,
`04-search-knowledge.md`, `05-chat-rag.md`, `06-api-backend.md`,
`07-frontend-shadcn.md`, `08-docker-scaling.md`, and master `REPLICATE.md` that
chains them. `docs/`: `ARCHITECTURE.md`, `USAGE.md`, `DEPLOY.md`, `SCALING.md`.

## 11. Easy flow (R11)

```
reels-scrap fetch-collection <url>     # input/urls/*.txt
reels-scrap run                        # ingest→extract→structure→render→index→knowledge
reels-scrap serve                      # FastAPI + React UI
```
One command per stage; `run` chains them; everything resumable.

## 12. Error handling / testing / scope

- **Errors:** empty index → 409; missing reel → 404; Claude CLI fail → graceful
  fallback (chat=sources only, vision=skip+record), all logged + in run_report.
- **Testing:** pytest + FastAPI TestClient on every endpoint with the Claude
  subprocess mocked; unit tests for RAG context builder, knowledge aggregation,
  paths, queue/resume; Vitest render tests for chat message + citations.
- **YAGNI v1:** no auth, no DB beyond JSON+SQLite-queue, no token streaming, no
  multi-user. Knowledge synthesis cached + opt-in.

## 13. Phased implementation (maps to tickets #2–#12)

1. **Foundation** — modular restructure + input/output dirs + paths (#2), collection→module (#3)
2. **Scale** — pipeline queue/workers/ratelimit (#4)
3. **Brains** — knowledge aggregation (#5), RAG chat (#6)
4. **Serve** — FastAPI backend (#7)
5. **UI** — React + shadcn (#8)
6. **Ops** — Docker (#9)
7. **Reproduce** — replication prompts (#10), docs/tickets/worklog (#11)
8. **Verify** — tests (#12)

Each phase: code → test → update TICKETS.md + WORKLOG.md → commit.
