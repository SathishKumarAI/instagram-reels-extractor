# Worklog

## 2026-07-02 15:52 — Local consolidated docs + env fix + transcript quality

**Summary:** Shipped a local "collection → one self-contained HTML document"
feature (thumbnails embedded, links back to reels, per-collection + master index),
fixed the broken dev env, brought the dev server up, and fixed non-English
transcript garbling. Two commits on branch `feat/local-consolidated-docs`.

**Changes:**
- `render/consolidated.py` — new stdlib-only renderer (`render_doc`, `render_index`);
  genre-grouped cards with summary, structured fields, timestamped facts, ⚠ translated badge
- `collections.py` — per-collection membership manifests over the flat `data/` pool
- `docs.py` — orchestration (`build_collection_doc`, `build_master_index`, `rebuild_all`)
- `cli.py` — `reels-scrap collection <url>` (fetch→extract→doc→open) + `consolidate`
- `extract/transcript.py` + `models.py` + `config.py` — auto-detect language + Whisper
  translate task; record `transcript_language/_translated/_confidence`
- `config.yaml` — `whisper_language: en → ""`, add `whisper_translate: true`
- `pyproject.toml` — `[dev]` extras (pytest, ruff) + pytest config
- `scripts/` — `build_consolidated.py` (thin wrapper), `retranscribe.py` (transcript-only rerun)
- `tests/test_docs.py` — 8 new tests (parsing, render, doc/index build, badge); 18 total green
- `docs/BACKLOG.md` — new prioritized 11-item backlog (#1,#2,#4 done)

**Decisions:**
- Local output only — user explicitly did **not** want a claude.ai Artifact.
- Renderer consumes raw JSON dicts (not the pydantic model) so it runs without ML deps.
- `data/` stays a flat, deduped pool; collection membership lives in manifests, not folders.
- Lean install (server/search/tests) — skipped the torch/whisper/weasyprint chain to avoid a
  multi-GB pull; added faster-whisper on demand for the re-transcribe.
- Root cause of "empty venv": interpreter shebang pointed at the repo's pre-rename path
  (`insta_reels_scrap/`). Recreated with mise py3.12.
- Dev server on **:8010** (`:8000` already taken on this machine).

**Follow-ups:**
- [ ] Transcript accuracy is `whisper_model`-bound (base fumbles); bump to small/medium + rerun.
- [ ] Backlog next: #3 `collections` status table · #5 render/pipeline test coverage · #10 CI.
- [ ] Merge `feat/local-consolidated-docs` → main when ready.
- [ ] Extraction deps (easyocr/weasyprint/yt-dlp) still uninstalled — install before full pipeline runs.

## 2026-06-30 12:22 — Brainstorm: drop cloud vision LLM for free local digest

**Summary:** Investigated user idea to replace own Claude-vision summarizer with
Instagram/Meta's "free AI context" for reels. Research (incl. the Meta "Edits"
app) concluded **no such scrapable field exists**. Pivoted to a deterministic,
no-LLM local design (Approach A). Design approved-in-principle; spec doc not yet
written. No code changed this session.

**Findings (why the original idea is dead):**
- `accessibility_caption` (auto alt-text) is image-only — empty for reels.
- yt-dlp IG info dict exposes only `description` (creator caption); no AI/alt key.
- IG auto-captions render in-app only; not served as a subtitle/VTT track (yt-dlp #15874).
- No Meta AI reel-summary endpoint; app-UI only.
- "Edits" app AI (SAM object segmentation, Restyle, AI video gen, auto-captions,
  upcoming insights assistant) is all **authoring-side** — nothing attaches to the
  published reel as retrievable metadata.

**Decisions:**
- Approach **A** — deterministic local digest: new `extract/digest.py` fills
  `genre/summary/structured/facts` from caption + Whisper transcript + OCR via
  rules/regex. Facts keep frame timestamps (cheap provenance, no hallucination).
- Archive vision = **keep `vision.py`, unwire only** (flip `vision:false`,
  add `digest:true`; vision knobs stay as legacy, re-enable by toggle).
- Trade-off accepted: output only as rich as caption/on-screen/speech; no
  visual-semantic summary (the one thing a vision model uniquely sees).

**Follow-ups:**
- [ ] Write spec to `docs/superpowers/specs/2026-06-30-local-digest-design.md` + commit.
- [ ] User reviews spec, then writing-plans → implementation.

## 2026-06-18 16:55 — Research platform built end-to-end (12 tickets)

**Summary:** Built the full local-first research platform on top of the pipeline:
Knowledge Base + RAG Research Chat behind a React/shadcn UI and FastAPI backend,
scaled for ~100 reels/hr, Dockerized, with replication prompts. All 12 tickets
in `TICKETS.md` done. Branch `feat/research-platform`.

**Changes (by layer):**
- `core` — `Config` output sub-dir helpers (knowledge/index/logs); `llm.py`
  shared text helper (claude-cli + api) twin of vision; `ratelimit.py` vision
  semaphore + backoff retry.
- `ingest/collection.py` — named saved-collection fetcher (script delegates);
  `reels-scrap fetch-collection`.
- `knowledge/` — aggregate corpus into topics by genre + optional cached Claude
  synthesis; `reels-scrap knowledge`.
- `chat/` — RAG (embed→retrieve→cited Claude answer, retrieval fallback);
  `reels-scrap ask`.
- `api/` — FastAPI (reels, detail, knowledge, search, chat, media) + serves
  `web/dist`; `reels-scrap serve`.
- `web/` — Vite+React+TS+Tailwind+shadcn-style, Catppuccin Mocha: Knowledge,
  Reels (grid+detail drawer), Research Chat (cited).
- `docker/` — backend + nginx web images + compose bind-mounting ./data + ./output.
- `prompts/` — 10 rebuild-from-scratch prompt templates.
- `docs/` — ARCHITECTURE/USAGE/SCALING/DEPLOY (+ README, spec) all current.
- `tests/` — 9 pytest (api/rag/knowledge, offline-mocked) + 2 vitest.

**Decisions:**
- Additive modularization (new packages with narrow interfaces) instead of a
  risky big-bang restructure of the working pipeline.
- Scaling fix targeted the real bottleneck: gate vision to 1–2 concurrent +
  backoff (3-way `claude -p` throttled to empty-stderr failures). Durable queue
  deferred to the cloud phase, documented in SCALING.md.

**Verified:** recovery run took the 18-reel `front-end` collection from 6/18 to
**18/18 vision (0 errors)**; knowledge base now 5 topics over 23 reels (was 13
uncategorized). API+SPA serve single-port; `ask` returns grounded cited answers;
frontend build + all tests green.

**Follow-ups:** merge `feat/research-platform` + `fix/batch-edge-cases` to main;
optional `--synthesize` overviews; cloud queue + SSE streaming.

## 2026-06-18 14:40 — Research platform: spec + collection fetcher + tickets

**Summary:** Processed a private saved collection (`front-end`, 18 reels) and
kicked off a larger build: a local-first **research platform** (React + shadcn UI
+ FastAPI backend, Knowledge Base + RAG Research Chat) over the scraped corpus,
designed for ~100 reels/hr, Dockerized, cloud-ready. Brainstormed + wrote the spec.

**Changes:**
- `scripts/fetch_saved_collection.py` — NEW: enumerate a *named* IG saved
  collection (built-in `saved` only does the default feed) via the private
  `feed/collection/<id>/posts/` endpoint, reusing Chrome cookies (yt-dlp
  extractor, no password). Got 18 `front-end` reels → `reels.txt`.
- Ran the 18-reel batch: 18/18 ingested; 6 full AI vision, 12 vision failures
  (`claude CLI failed:` — 3-way parallel `claude -p` throttle). Recoverable via
  resume once the scalable pipeline lands.
- `docs/superpowers/specs/2026-06-18-research-platform-design.md` — NEW: full
  design spec (modular architecture, input/output dir split, scaling, Docker,
  RAG chat, replication prompts).
- `TICKETS.md` — NEW: 12-ticket build tracker.

**Decisions:**
- Stack: Vite + React + shadcn + FastAPI; chat via Claude CLI (subscription, no
  key) consistent with vision; data local with `data/input` vs `data/output`
  separated behind a single `core/paths` module for easy local→cloud swap.
- Scaling: stage-decoupled pipeline + persistent resumable queue + vision
  concurrency 1–2 behind a token-bucket (3 parallel already throttles).

**Follow-ups:** see `TICKETS.md` (#2–#12).

## 2026-06-18 13:26 — Multi-reel batch validation + 2 edge-case fixes

**Summary:** Ran the first true multi-reel batch (4 URLs, 3 workers), validating
the parallel path live. Found and fixed two real edge-case bugs; re-ran to
confirm. Committed on branch `fix/batch-edge-cases`.

**Changes:**
- `extract/frames.py` — new `has_audio_stream()` probe (ffmpeg `-i` → look for
  `Audio:` in stderr)
- `extract/transcript.py` — skip transcript cleanly on video-only reels instead
  of crashing
- `ingest/__init__.py`, `ingest/ytdlp.py`, `ingest/instaloader_src.py` — thread
  optional `failures` dict; route ingest errors through `log.error`
- `pipeline.py` — record dropped URLs in `run_report.json` as ingest errors
- `reels.txt` — 4 test URLs (1 control + 3 fresh public reels)
- `output/validation_results.md` — full validation report (untracked artifact)

**Bugs fixed (found via batch run):**
1. No-audio/video-only reel crashed transcript — ffmpeg `-vn` exits 234 →
   CalledProcessError. Now probed and skipped clean (like the no-speech path).
2. Failed/login-gated URL dropped silently — caught with `print()`+`continue`,
   no report/log entry. Now logged + recorded as `ingest: error` with reason.

**Verification:** 4-URL batch report went `total 3 → 4`; video-only
`DXZgeTJDDLD` processes fully (genre=news); login-gated `DZQq3aaEfzF` recorded
with "empty media response / use cookies" reason. 3 markdown + 3 PDFs + docs
site + 26-vector search index produced.

**Follow-ups:**
- [ ] Open PR / merge `fix/batch-edge-cases` into `main`
- [ ] Private-reel batch via `auth.cookies_from_browser` (would recover the
      login-gated URL)
- [ ] Earlier follow-ups still open: scene-aware frame sampling, knowledge-graph
      auto-linking, watch/daemon mode, test suite

## 2026-06-16 20:35 — Publish + polish; checkpoint for continuation

**Summary:** Pushed to GitHub (public), rewrote README, added MIT license, and
saved a resume memory. App left running on :8501.

**Changes:**
- GitHub: `SathishKumarAI/insta_reels_scrap` created, pushed, made **public**
- `README.md` — full rewrite: leads with structured-extraction/provenance/
  local-first value; documents UI, semantic search, cookie auth, batch perf
- `LICENSE` (MIT) + `license` metadata in `pyproject.toml`

**Resume here next session:**
- [ ] **Run a real multi-reel batch** — parallel path proven (4×1s→2s) but only
  run on 1 real URL (`DZJv2DUzGPQ`). Need 3-5 reel URLs from user.
- [ ] Then pick up earlier follow-ups (scene-aware sampling, knowledge-graph
  links, watch/daemon, tests) listed in the entry below.
- [ ] Remove synthetic `DEMO123` artifacts from `data/`/`output/` (rm is
  deny-listed — confirm first).
- Streamlit may still be running on http://localhost:8501.

---

## 2026-06-16 20:20 — Build reels→text→PDF→docs pipeline (greenfield)

**Summary:** Built `reels-scrap` end-to-end from an empty repo: an Instagram-reel
ETL that extracts caption/transcript/OCR/structured-vision per clip, renders a
professional PDF + linked mkdocs-material site, and exposes a Streamlit UI + CLI.
Verified live on a real private reel.

**Changes:**
- `src/reels_scrap/ingest/` — yt-dlp (public + browser-cookie auth for private),
  instaloader (profile/hashtag/saved); idempotent resume, rate-limit backoff
- `src/reels_scrap/extract/` — faster-whisper transcript (forced-lang
  anti-hallucination), easyocr (confidence-filtered), **structured Claude vision
  with provenance** (genre → typed fields + facts tied to frame/timestamp)
- `src/reels_scrap/render/` — weasyprint PDF (Catppuccin CSS) + mkdocs-material
  site with master index
- `src/reels_scrap/pipeline.py` — shared orchestration, bounded-parallel batch
  (thread-safe model loading), per-run JSON manifest + structured logging
- `src/reels_scrap/search.py` — local semantic search (fastembed ONNX) over
  reels + facts; CLI `index`/`search` + UI Search tab
- `app.py` — Streamlit UI (Extract + Search tabs); `cli.py` — typer CLI
- `config.py` — fail-fast pydantic validation for every section

**Decisions:**
- **Vision via Claude Code CLI** (`claude -p`, subscription) as default backend —
  no API key; Anthropic API optional. Subscription quota is the cost lever.
- **Structured extraction + provenance over prose** — anti-slop: output is typed
  data, every fact cites the frame/timestamp it came from.
- **Local-first** — Whisper, easyocr, fastembed all run on-device; static ffmpeg
  via pip (`imageio-ffmpeg`) so no sudo needed; `secretstorage` for Chrome cookies.
- **Public-default, login opt-in** — yt-dlp public path is default; private uses
  browser cookies; passwords never touch code (session/cookie files only).
- Skipped: cloud/Vercel (local heavy deps), prose summaries, generic chatbot.

**Follow-ups:**
- [ ] Scene-aware frame sampling (`select='gt(scene,0.4)'`) — fewer, sharper frames
- [ ] Knowledge-graph auto-linking between reels sharing entities
- [ ] Watch/daemon mode to auto-ingest new saved reels on a schedule
- [ ] Test suite (config validators, URL validation, render fixtures)
- [ ] Multi-reel batch live test (parallel path proven, not yet run on >1 real reel)
- [ ] Remove synthetic `DEMO123` artifacts from `data/`/`output/`
