# Project Summary — insta_reels_scrap → Reels Research Platform

**One-page source of truth.** What it is, how it's built, every command, every
module, the data layout, what was done in the 2026-06-18 session, decisions,
scaling, deploy, tests, and follow-ups.

---

## 1. What it is

A **local-first pipeline + research platform** that turns Instagram reels into
structured, searchable knowledge.

```
ingest ─► extract ─► structure ─► render ─► search ─► knowledge ─► chat ─► UI
download   transcript  genre +     PDF +     semantic  topics by    RAG     React
+metadata  OCR/vision  provenance  docs site (local)   genre        cited   shadcn
                       facts                                         answers
```

- **Structured, not slop** — vision returns typed fields per genre (product →
  `{name,price,link,claims}`, tutorial → `{tools,commands,steps}`).
- **Provenance on every fact** — each fact carries the frame + timestamp it came
  from; scrub the reel to verify. Hallucination-resistant.
- **No API key needed** — vision + chat run through the **Claude Code CLI**
  (your subscription). Anthropic API is an optional backend.
- **Fully local** — whisper (transcript), easyocr (on-screen text), fastembed
  (search embeddings) all run on-device. Data never leaves the machine.

Repo: `SathishKumarAI/insta_reels_scrap` (public, MIT). Built greenfield
2026-06-16; research platform added 2026-06-18.

---

## 2. Module map (`src/reels_scrap/`)

| Module | Job |
|--------|-----|
| `config.py` | typed config from `config.yaml`; output sub-dir helpers (`knowledge_dir`, `index_dir`, `logs_dir`) |
| `models.py` | `Reel` (flows through every stage) + `Fact` (text + timestamp + frame) + `TranscriptSegment` |
| `observability.py` | logging + per-run `RunReport` → `run_report.json` |
| `ingest/ytdlp.py` | public reels via yt-dlp (+ browser cookies for private) |
| `ingest/instaloader_src.py` | profile / hashtag / saved (login) |
| `ingest/collection.py` | **named saved-collection fetcher** (private feed + browser cookies) |
| `extract/frames.py` | ffmpeg frame sampling + audio extract + `has_audio_stream()` probe |
| `extract/transcript.py` | faster-whisper; skips video-only reels cleanly |
| `extract/ocr.py` | easyocr, confidence-filtered |
| `extract/vision.py` | Claude structured vision (genre + fields + provenance facts) |
| `structure.py` | render markdown (jinja2) from a Reel |
| `render/pdf.py` | per-reel + combined PDF (weasyprint) |
| `render/docs_site.py` | mkdocs-material static site |
| `search.py` | fastembed local embeddings index over reels + facts; query |
| `knowledge/aggregate.py` | group reels by genre → topics (facts, hashtags, reels); cached |
| `knowledge/synthesize.py` | optional per-topic Claude overview (off by default) |
| `chat/rag.py` | RAG: retrieve → cited Claude answer → `Answer{answer,citations,note}` |
| `chat/prompts.py` | research prompt builder (cite `[id]`, "Not in the archive") |
| `llm.py` | shared text-LLM helper (claude-cli default, api fallback) |
| `ratelimit.py` | process-wide vision semaphore + exponential-backoff retry |
| `api/app.py` | FastAPI app + endpoints; serves `web/dist` single-port |
| `api/schemas.py` | Pydantic = backend↔frontend contract |
| `pipeline.py` | orchestration: ingest → extract+render (ThreadPoolExecutor) → site → index |
| `cli.py` | typer CLI (see §4) |

**Frontend** (`web/`, Vite + React + TS + Tailwind + shadcn-style, Catppuccin Mocha):
`views/KnowledgePage.tsx`, `views/ReelsPage.tsx` (grid + detail drawer),
`views/ResearchChat.tsx` (cited), `lib/api.ts` (typed client), `components/ui/*`.

---

## 3. Data layout — inputs vs outputs

```
data/                         # INPUTS (gitignored, host-mounted in Docker)
  <id>.mp4 / .jpg / .wav      # downloaded media
  <id>_frames/                # sampled frames
  <id>.json                   # per-reel structured record (the source of truth)
output/                       # DERIVED (gitignored)
  markdown/  pdfs/  site/      # rendered docs
  knowledge/knowledge.json     # aggregated topics (cached)
  index/  (search_index.*)      # semantic index
  logs/    run.log, run_report.json
```

`config.yaml` `paths:` defines `data_dir` + `output_dir`; `Config.*_dir`
properties derive the sub-dirs — one place that knows the layout, so local→cloud
is a single config change.

---

## 4. Commands

```bash
# install
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e .

# pipeline
reels-scrap fetch-collection "<saved-collection-url>"   # → reels.txt (browser cookies)
reels-scrap run                                          # full pipeline
reels-scrap ingest-cmd | extract-cmd | render-cmd        # individual stages
reels-scrap index                                        # rebuild semantic index
reels-scrap knowledge [--synthesize]                     # rebuild Knowledge Base
reels-scrap login USER                                   # instaloader session

# research
reels-scrap search "query"                               # semantic search
reels-scrap ask "research question"                      # RAG answer + citations (CLI)
reels-scrap serve                                         # React UI + API → :8000

# frontend (once)
cd web && npm install && npm run build

# docker
docker compose -f docker/docker-compose.yml up --build    # API+UI on :8000
```

**API endpoints:** `GET /api/health`, `/api/reels`, `/api/reels/{id}`,
`/api/knowledge`, `/api/search?q=&k=`, `POST /api/chat`, `GET /api/media/{id}/{kind}`.

---

## 5. Config knobs (`config.yaml`)

| Section | Key | Default | Note |
|---------|-----|---------|------|
| source | `type` | urls | urls / profile / hashtag / saved |
| auth | `cookies_from_browser` | "" | chrome/firefox/… for private reels |
| extract | `transcript/ocr/vision` | varies | toggle each modality |
| extract | `vision_backend` | claude-cli | claude-cli (no key) / api |
| extract | `vision_model` | claude-sonnet-4-6 | opus for max quality |
| extract | `vision_concurrency` | 1 | parallel claude vision calls (3+ throttles) |
| extract | `vision_max_retries` | 3 | retry throttled vision calls |
| extract | `vision_retry_backoff` | 5.0 | seconds, exponential |
| batch | `workers` | 3 | parallel reels through extract+render |
| output | `pdf/docs_site/combined_pdf` | — | render toggles |
| paths | `data_dir/output_dir` | data/output | input vs derived split |

---

## 6. This session (2026-06-18)

**Phase A — batch validation + 2 bug fixes** (branch `fix/batch-edge-cases`):
- Validated multi-reel batch on 4 URLs. Found + fixed:
  1. **No-audio reel crashed transcript** (ffmpeg `-vn` exit 234) → `has_audio_stream()` probe, skip clean.
  2. **Failed/login-gated URL dropped silently** → logged + recorded in `run_report.json`.

**Phase B — research platform** (branch `feat/research-platform`, 8 commits, 12 tickets):
- Spec → `docs/superpowers/specs/2026-06-18-research-platform-design.md`.
- Built: collection fetcher, knowledge layer, RAG chat, FastAPI backend, React/shadcn
  UI, Docker, scaling guard, replication prompts, docs, tests.
- **Recovery run:** the 18-reel `front-end` saved collection went **6/18 → 18/18
  vision (0 errors)** after the concurrency fix. Knowledge base: **5 topics
  (product 9, educational 6, tutorial 6, news 1) over 23 reels** (was 13 uncategorized).

---

## 7. Key decisions (the why)

- **Vision via Claude CLI** by default — uses subscription, no API key; API is fallback.
- **Structured + provenance** output, not prose summaries — queryable + verifiable.
- **Additive modularization** — new packages with narrow interfaces instead of a
  risky big-bang restructure of the working pipeline.
- **Scaling = fix the real bottleneck:** parallel `claude -p` vision calls throttle
  (3-way → empty-stderr failures). Gate to `vision_concurrency=1` + backoff;
  transcript/OCR stay parallel. Full **persistent/distributed queue deferred to the
  cloud phase** (documented, not built).
- **Chat resilience** — if synthesis fails, return retrieved sources with a note
  (mirrors the vision skip-on-failure policy).
- **Local-first, cloud-ready** — swap queue backend + flip vision/chat to API; one
  config change for paths.

---

## 8. Scaling (~100 reels/hr) — see `docs/SCALING.md`

- Bottleneck = vision LLM + whisper (CPU). Ingest is IO-bound + parallel.
- Built: bounded `batch.workers`; vision semaphore (1–2) + backoff; idempotent +
  resumable (skip cached sidecars); per-stage retry; provenance in `run_report.json`.
- **Planned (cloud):** durable distributed queue (SQLite→Redis), vision via API for
  real concurrency, SSE token-streaming chat.

---

## 9. Deploy — see `docs/DEPLOY.md`

- `docker/Dockerfile.backend` (pipeline + FastAPI, ffmpeg via pip), optional
  `Dockerfile.web` (nginx), `docker-compose.yml`.
- Compose **bind-mounts `./data` + `./output`** → everything stays local.
- Claude CLI auth mounted from host (`~/.claude:ro`); cloud path = `vision_backend:
  api` + `ANTHROPIC_API_KEY`.

---

## 10. Tests

- **Backend** (`tests/`, pytest + TestClient, offline — search + Claude mocked):
  api (health/reels/404/knowledge/search-409/chat), RAG (citations, LLM-fallback,
  empty archive), knowledge aggregation. **9 passed.**
- **Frontend** (`web/src/__tests__`, vitest): ResearchChat render + `fmtNum`. **2 passed.**

---

## 11. Replication

`prompts/` — 10 house-style prompt templates to rebuild the whole project from
scratch: `REPLICATE.md` (master) + `00-architecture` … `08-docker-scaling`.

---

## 12. Status & follow-ups

**Done:** all 12 platform tickets (`TICKETS.md`) + 2 batch bug fixes.

**Branches not yet merged to main:** `fix/batch-edge-cases`, `feat/research-platform`.

**Open follow-ups:**
- [ ] Merge both branches / open PRs.
- [ ] Build `web/` before `serve` in prod (`npm install && npm run build`).
- [ ] Optional per-topic synthesis (`reels-scrap knowledge --synthesize`).
- [ ] Cloud phase: durable queue, vision-via-API concurrency, SSE chat.
- [ ] Earlier ideas: scene-aware frame sampling, knowledge-graph auto-linking,
      watch/daemon mode.
- [ ] Synthetic `DEMO123` artifacts still in data/ (1 uncategorized topic); `rm`
      is deny-listed — ask before removing.

**Doc index:** `README.md` · `SUMMARY.md` (this) · `TICKETS.md` ·
`docs/{ARCHITECTURE,USAGE,SCALING,DEPLOY}.md` · `docs/WORKLOG.md` ·
`docs/superpowers/specs/2026-06-18-research-platform-design.md` · `prompts/`
