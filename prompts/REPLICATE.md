# Rebuild the Reels Research Platform — Master Prompt

You are a senior platform engineer. Your objective is to rebuild the
`insta_reels_scrap` research platform from scratch by executing the layered
prompts in this directory **in order**, so the result matches the approved
design spec.

<context>
  <what_this_is>
    A local-first research platform. It scrapes Instagram reels, turns each into
    structured text (transcript, OCR, AI visual summary, typed genre fields with
    timestamp provenance), renders Markdown + PDF + a static site, builds a local
    semantic search index, aggregates a Knowledge Base, answers cited research
    questions over the corpus (RAG), and exposes all of it through a FastAPI
    backend and a Vite + React + shadcn UI. Ships in Docker; designed for
    ~100 reels/hour and a later cloud migration with minimal change.
  </what_this_is>
  <source_of_truth>
    docs/superpowers/specs/2026-06-18-research-platform-design.md is the
    authoritative design. If a layer prompt and the spec disagree, the spec wins.
  </source_of_truth>
  <core_record>
    Everything flows around one Pydantic model, `Reel` (src/reels_scrap/core/
    models.py): identity (id, url, author, title), metadata (caption, hashtags,
    mentions, likes/views/comments, duration), media paths, extracted text
    (transcript segments + text, ocr_text, summary, genre, structured dict,
    facts[] each with text + timestamp + frame provenance), and render paths.
    Per-reel JSON in output/reels/<id>.json is the record of truth; every later
    stage reads it, never re-scrapes.
  </core_record>
</context>

## Tech stack
- **Backend / pipeline:** Python 3.12, Pydantic v2, Typer (CLI), yt-dlp,
  instaloader, faster-whisper, easyocr, imageio/ffmpeg, jinja2, weasyprint,
  mkdocs-material, fastembed, FastAPI + uvicorn, SQLite (queue).
- **AI:** Claude via the `claude -p` CLI by default (uses the user's
  subscription, no API key); API fallback via `ANTHROPIC_API_KEY`. Vision model
  default `claude-sonnet-4-6`; synthesis/chat via `claude -p`.
- **Frontend:** Vite + React + TypeScript + Tailwind + shadcn/ui, Catppuccin
  Mocha (dark default).
- **Ops:** Docker (Dockerfile.backend, Dockerfile.web, docker-compose), host
  bind-mount of `./data`.

## Directory layout — inputs vs outputs are separated (hard requirement)
A single `core/paths.py` is the only module that knows this layout, so
local↔cloud is one config change.

```
data/                      # LOCAL store, gitignored, host-mounted in Docker
├─ input/                  # everything that comes IN
│  ├─ urls/                # *.txt url lists, collection dumps
│  ├─ media/               # downloaded mp4 / jpg / wav / <id>_frames/ per reel
│  ├─ cookies/             # exported browser cookies (optional)
│  └─ cache/               # whisper + fastembed model cache, IG session
└─ output/                 # everything DERIVED
   ├─ reels/               # per-reel structured JSON (record of truth)
   ├─ markdown/            # rendered .md
   ├─ pdfs/                # rendered .pdf
   ├─ site/                # static mkdocs site
   ├─ knowledge/           # knowledge.json + per-topic syntheses
   ├─ index/              # search_index.npz + search_index.json
   └─ logs/               # run.log, run_report.json, queue state
```

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
web/                       # Vite + React + shadcn frontend
docker/                    # Dockerfile.backend · Dockerfile.web · docker-compose.yml
```

## Rebuild order — run each prompt as its own session, in this order
Each prompt is self-contained, regenerates exactly one layer, and ends with a
working, testable slice. After each, run that layer's tests and commit before
moving on.

1. **prompts/00-architecture.md** — repo scaffold, packages, `config.yaml`,
   `core/` (config, models, paths, errors, observability). *Foundation for all.*
2. **prompts/01-ingest.md** — yt-dlp public + instaloader private/profile/
   hashtag/saved + named-collection fetcher. Produces `Reel` records + media.
3. **prompts/02-extract.md** — frames, whisper transcript, easyocr, Claude
   vision, genre→typed fields with frame/timestamp provenance.
4. **prompts/03-structure-render.md** — jinja2 Markdown + weasyprint PDF +
   mkdocs-material site.
5. **prompts/04-search-knowledge.md** — fastembed local index + Knowledge Base
   aggregation with optional cached Claude synthesis.
6. **prompts/05-chat-rag.md** — RAG: embed → retrieve → cited context →
   `claude -p` → answer + citations, with retrieval fallback.
7. **prompts/06-api-backend.md** — FastAPI endpoints + media static + `serve`.
8. **prompts/07-frontend-shadcn.md** — Vite/React/shadcn UI (Knowledge, Reels,
   Research Chat).
9. **prompts/08-docker-scaling.md** — Docker images + compose + the
   stage-decoupled, resumable, rate-limited pipeline for ~100 reels/hr.

## Constraints
- MUST follow the spec's module boundaries: `ingest` returns records + media and
  knows nothing about extraction; `extract` enriches a `Reel` in place with pure
  per-modality functions; `search`/`knowledge`/`chat` only read records + index
  and never scrape; `api` is a thin HTTP layer; `pipeline` is the only place that
  knows about concurrency.
- MUST resolve every filesystem path through `core/paths.py`; no module
  hard-codes `data/` or `output/`.
- MUST keep each stage idempotent and resumable by sidecar JSON.
- MUST default Claude calls to the `claude -p` CLI backend; API is fallback.
- MUST degrade gracefully on Claude CLI failure (vision: skip + record; chat:
  return retrieved sources with `answer=null`).
- MUST NOT introduce auth, a server DB beyond JSON + a SQLite queue, token
  streaming, or multi-user — these are explicitly out of scope for v1.
- MUST run each layer's tests and commit before starting the next prompt.

## Output format
For each layer, follow that layer's own prompt. Across the whole rebuild, deliver
in this order: (1) the scaffold and `core/`, (2..9) each layer's files plus its
tests, each as paste-ready code. After all layers, the three "easy flow" commands
MUST work:

```
reels-scrap fetch-collection <url>     # writes input/urls/*.txt
reels-scrap run                        # ingest→extract→structure→render→index→knowledge
reels-scrap serve                      # FastAPI + built React UI on one port
```

Reason briefly in a `<thinking>` block before each layer, then produce that
layer's code.
