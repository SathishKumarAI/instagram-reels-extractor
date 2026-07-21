# Worklog

## 2026-07-11 23:30 — Finish extraction · UI (cards/Back/date/collection/Reader) · claude-only default · dual vision backend (local Kimi-VL) · backlogs

**Session span:** 2026-07-09 → 2026-07-11. Driven entirely from Claude Code.

**Summary:** Finished the extraction backlog on the existing archive, shipped four UI
improvements + a new text-only Reader view, made the pipeline **Claude-code-only by
default**, attempted a fresh sync (blocked by a Chrome cookie lock → wired a
`cookies.txt` path + auto-watcher), then designed and built a **selectable vision
backend** so the pipeline runs on Claude **or** a self-hosted open-weights model
(Kimi-VL) on the user's own GPU box — now set to **strictly local, no fallback**.
Closed with project + session backlogs.

**What we did (chronological):**
1. **"Run the pipeline, finish the work" (claude-only).** Assessed the archive:
   149/184 reels fully extracted. Ran `scripts/backfill_vision.py -c config-claude.yaml`
   (claude-cli vision, sequential per [[claude-cli-no-parallel]]): **33 reels, $11.05,
   0 failures** → 182/184 extracted (2 skipped = `DEMO123` fixture + a video-less
   carousel). Auto-rebuilt docs + search index (**1,470 vectors**).
2. **UI — bigger cards.** Reels grid → 3-col, `h-56` thumbs, center-origin hover
   scale + shadow + inner image zoom (`ReelsPage.tsx`).
3. **UI — Back bar on every page.** `TopBar` in `App.tsx`: `navigate(-1)`, falls
   back to Home when landed directly; explicit Home link. Hidden on Home.
4. **UI — date sort + filter.** Added `timestamp` to `ReelSummary` (schema +
   `_summary` + api.ts); Newest/Oldest sorts, "past week/month/…" filter, date on
   each card. Restarted the API for the schema change.
5. **Config → Claude-code-only default.** `config.yaml`: `transcript:false`,
   `ocr:false`, `vision_backend:claude-cli`. **No code deleted** — whisper/OCR
   modules intact, flip flags to re-enable. Updated [[no-gpu-extraction]].
6. **UI — collection filter.** Reels carried no collection link; membership lived
   only in `output/collections/*.json`. Added `collections` to `ReelSummary` (joined
   from manifests in `list_reels`), new "All collections" dropdown. 155/189 reels
   tagged: internships 94 / front-end 51 / phd-opportunities 10.
7. **UI — Reader (thesis) view.** New `ReaderPage.tsx` + `/reader` route: sortable/
   filterable left index (heading + sub-heading), right long-form paper (abstract →
   key-points → details → transcript → caption → links), **text-only, no video**;
   pulls + dedups every URL from caption/summary.
8. **Sync attempt → cookie block.** Ran `sync --claude-only`: 0 new reels. Diagnosed
   **Chrome running → cookie DB locked → yt-dlp unauthenticated** ("empty media
   response"). Chose cookies.txt export; wired `auth.cookies_file` (listing keeps
   browser, download uses file); confirmed gitignored; launched a background
   **watcher** that auto-syncs when `cookies.txt` appears.
9. **Dual vision backend (brainstormed spec → build).** Verified via web search that
   **Kimi is open-source** (Modified MIT); correct vision model = **Kimi-VL-A3B-Instruct**
   (open-weights, ~2.8B active), not K2 (text-only, 340GB). Decisions gathered:
   runs on user's **own GPU box** (LAN, OpenAI-compatible) · selectable via
   config+CLI+**UI** · build-ahead (no box yet) · originally auto-fallback, later
   changed to **strict local**. See [[dual-vision-backend]].

**Changes:**
- `extract/vision.py` — new `_via_local` (OpenAI-compatible `/chat/completions`,
  base64 frames), `_run_local` (retry + fallback), provenance (`tokens.backend`/`model`).
- `config.py` — `VisionLocalCfg`, `vision_backend` enum + `local`, `vision_local_fallback`,
  validator requires `base_url` for local.
- `models.py` — `tokens` widened `dict[str,float]` → `dict[str,Any]` for provenance.
- `cli.py` — `sync --backend/-B`. `api/app.py` — `POST /api/sync` + `/api/sync/status`
  (threaded), `SyncIn`, `_SYNC`; `collections`/`timestamp` on `ReelSummary`.
- Web — `ReaderPage.tsx`, `SourcesPage` **SyncPanel** backend toggle, api.ts
  `sync`/`syncStatus`/`SyncBackend`/`SyncStatus`, Reels date+collection filters, Back bar.
- Config — `config-local.yaml` (strict local, `vision_local_fallback:false`),
  `vision_local` block in `config-claude.yaml`.
- Docs — `docs/LOCAL-VISION.md` (serving guide), `docs/PROJECT-STATUS.md` (kanban
  backlog), this entry. Tests — `tests/test_vision_local.py` (5 cases; **26/26** total).

**Decisions:**
- **Claude-code-only is the new default**; local ML (whisper/OCR) off but retained.
- **Local vision = strictly private** (`vision_local_fallback:false`) — failed reels
  dead-letter (`sync --retry-failed`), never egress. Upholds [[privacy-first-workflow]].
- **Server-agnostic local backend** (generic OpenAI-compat) over a Kimi-specific client.
- Verified real HTTP path against a stand-in server (build-ahead; GPU box not wired).

**Follow-ups / blocked on user:**
- [ ] Export `cookies.txt` → watcher auto-syncs fresh reels.
- [ ] Set GPU-box `base_url` in `config-local.yaml` → real local-vision run.
- [ ] Sync the other 9 collections (only 3 of 12 pulled).
- [ ] Reader feedback (section order, left-index density).
- [ ] Provenance badge in UI (data already in `tokens.backend`).

## 2026-07-03 20:01 — 50-feature backlog + Waves 1–4 + token-accounting truth + SPA fix

**Summary:** Architected a 50-feature backlog (10 epics) and built Waves 1–4 (**32/50**),
diagnosed the inflated "input tokens" (mostly cached claude-cli machinery, not reels)
and fixed the accounting, and fixed SPA deep-link refresh.

**Changes:**
- `docs/BACKLOG-50.md` (new) — 50 features, prioritized with effort/value/deps + build waves.
- Wave 1: tag-cloud page, similar-reels (`/api/reels/{id}/similar`), Home overview
  dashboard, path-traversal guard. Wave 2: quick-add reel, language badge, per-reel
  notes, filtered export, `/api/report`. Wave 3: semantic Search tab, keyboard
  shortcuts (j/k/s/esc/`/`), empty states. Wave 4: **Kanban board** (status columns),
  tag merge/rename/delete (`/api/tags/rename`), min-likes range, "surprise me", budget guard.
- Copy: section + whole-reel-markdown copy; Table multi-select + bulk actions.
- `extract/vision.py` + `api/app.py` — token metering split into
  input/cache_read/cache_creation/output/**cost_usd**; `/api/stats` uses real CLI cost.
- `api/app.py` — **SPA fallback**: serve index.html for client routes so refresh works.

**Decisions:**
- "Input tokens" looked huge because claude-cli reloads Claude Code's system prompt +
  tool schemas (~62k, cached ~free) per call. Metering now separates that; real fix is
  `vision_backend=api` (~15× fewer, ~$0.02 vs $0.38/reel). Budget guard caps spend.
- E2/E3 (collection/account pages) covered by existing filters — not duplicated.
- H5 model picker + P3 items (local-LLM vision, encryption, webhooks, Notion) deferred.

**Follow-ups:**
- [ ] Remaining backlog: D3 saved searches, H5 model picker, P3 epics.
- [ ] tech-guff still IG-429 (watcher gave up); use quick-add URLs.

## 2026-07-03 03:43 — Workflow layer: status flags, saved views, richer export

**Summary:** Turned the archive into a workflow surface — per-reel status flags
(star/read/archive), saved filter views, and CSV/XLSX/MD export — completing the
near-term roadmap; local-LLM vision assessed and honestly deferred (GPU-blocked).

**Changes:**
- `src/reels_scrap/userstate.py` (new) — annotations + saved views stores under
  output/, kept separate from `data/` reel records so they survive re-extraction.
- `api/app.py` + `schemas.py` — `/api/annotations`, `/api/reels/{id}/annotate`,
  `/api/views` (+ save/delete), `/api/export.md`, `/api/export.xlsx` (openpyxl);
  reel list now carries `starred/read/archived`.
- `web/ReelsPage` + `api.ts` — star + archive buttons on cards, mark-read-on-open,
  status filter (all/starred/unread/archived), saved-view chips + "Save view",
  export menu (CSV/XLSX/MD).

**Decisions:**
- User state lives in `output/annotations.json` + `views.json`, NOT in reel JSON —
  subjective annotations must not be clobbered by a re-extract.
- **Local-LLM vision deferred**: LLaVA/moondream needs torch, the dep we skip on
  this no-GPU box (same blocker as OCR). Design ready; not faked.

**Follow-ups:**
- [ ] tech-guff profile sync — watcher polling (IG 429); fires when it clears.
- [ ] Local-LLM vision when a GPU/torch box is available.

## 2026-07-03 03:36 — Cost dashboard + scheduled sync + token-reduction defaults + tech-guff watcher

**Summary:** Shipped two roadmap items — a cost dashboard ($ from tokens) and a
no-sudo scheduled-sync timer — wired the token-reduction levers in as defaults, and
set an auto-retry watcher for the rate-limited tech-guff profile pull.

**Changes:**
- `api/schemas.py` + `api/app.py` — `/api/stats` now returns estimated USD cost
  (price table by model) total + per-category, with an honest "upper bound / $0 on
  subscription" note.
- `web/` — cost shown in the Reels stats bar + per-category headers (hover = note).
- `scripts/setup-scheduled-sync.sh` — systemd **user** timer (no sudo) running
  `sync --config config-claude.yaml --claude-only` nightly; manage via `systemctl --user`.
- Reductions as defaults: `vision_backend: auto` (api if key else claude-cli) in all
  configs + `config.py`; `max_frames` (6, 4 in fast) + `frame_max_width` (720, 512 fast)
  baked into config.yaml/config-deep/config-claude; validator accepts `auto`.
- Backfill finished: 121/123 tags+tokens (2 reels fail vision — bad frames); docs +
  knowledge + index rebuilt.
- tech-guff watcher (`scratchpad/techguff_watch.sh`) polls IG every 20min ~3h, runs
  the sync when 429 clears.

**Decisions:**
- Cost shown as an **estimate/upper bound** — claude-cli token counts include the whole
  CLI turn; real API cost ≈ 15× lower, and $0 on the flat subscription.
- `auto` backend picks the cheap+parallel API path only when a key is present — safe default.
- Scheduled sync uses claude-only (no CPU) + incremental + dead-letter → safe unattended.

**Follow-ups:**
- [ ] tech-guff profile sync — blocked by IG 429; watcher will fire when it clears (or feed URLs).
- [ ] 2 reels with unusable frames never got vision — acceptable.
- [ ] Roadmap remaining: saved views, status flags, richer export, local-LLM vision.

## 2026-07-03 01:05 — Token-reduction: frame downscaling

**Summary:** Added `extract.frame_max_width` (default 720) — downscales sampled
frames before vision so image tokens drop ~2-3× at negligible quality cost. Rounds
out the token-reduction levers (API backend, fewer frames, downscale, haiku).

**Changes:**
- `config.py` `extract.frame_max_width`; `extract/frames.py` ffmpeg `scale` filter;
  `extract/vision.py` passes it. `docs/OPTIMIZATION.md` — ranked "reduce tokens" table.

**Decisions:** on subscription (claude-cli) tokens are free-but-slow, so downscale/
fewer-frames buy speed; on the API backend they cut real cost (~15× stacked).

## 2026-07-03 01:02 — Tags, token metering, Table view, filters, privacy scrub, opts

**Summary:** Turned the archive into a usable product surface — per-reel tags +
token metering, an Excel-style Table view with CSV export, sort + category/account
filters, a claude-only fast mode, and vision cost/speed optimizations — plus a
full privacy audit that scrubbed a leaked file from public git history.

**Changes:**
- `models.py` — `tags[]` + `tokens{input,output}` on Reel.
- `extract/vision.py` — capture Claude usage via `claude -p --output-format json`;
  request tags; configurable `max_frames` (6). `extract/frames.py` — frame caching.
- `api/app.py` + `schemas.py` — `tags`/`tokens` on ReelSummary; `/api/stats`
  (per-category tokens + top tags); `/api/export.csv`; `/api/sources` (list/add/toggle).
- `web/` — **Table** view (sortable + CSV export), **Sources** tab; Reels + Table
  gain sort (likes/comments/tokens/duration/title) + **category** + **account** filters;
  tag chips (clickable) + token badges.
- `config-claude.yaml` + `sync --claude-only/--full` — skip CPU whisper/OCR, Claude
  vision only. `sync --only <name>`; `scripts/backfill_vision.py` (parallel/api-aware).
- `pyproject.toml` — lean core + gated extras (from prior session); `config.py` max_frames.
- Privacy: `.gitignore` hardened (sources.json/reels lists/media); `sources.example.json`;
  `git filter-branch` scrub of `reels.txt` + **force-push all branches**.
- Docs: `PRD.md`, `OPTIMIZATION.md`, `PRIVACY.md`, `SYNC.md`; TICKETS 22–27.

**Decisions:**
- **claude-cli throttles on parallel** (3 workers → 84/120 failed). Forced
  concurrency 1; the API backend (inline images) is the parallel + ~15× cheaper path.
- Token numbers from claude-cli are an **upper bound** (whole CLI turn), not vision cost;
  on subscription the backfill is $0 marginal. Worth it as a one-time pass; syncs are incremental.
- No-GPU box → transcript via whisper CPU, OCR deferred behind `.[ocr]`; vision = the one egress.
- Profile scraping (`_tech_guff_`) needs a session (anon = 403); currently IG 429 under load.

**Follow-ups:**
- [ ] Finish backfill (102/123 at log time) → full tags/tokens coverage.
- [ ] Retry `tech-guff` profile sync when IG not rate-limiting.
- [ ] Cost dashboard ($ from tokens), scheduled sync, saved views (see PRD roadmap).

## 2026-07-02 17:52 — Torch-free deep extraction + Sources tab + deps gating

**Summary:** Populated the phd reels with summary/genre/key-facts (claude-cli
vision) + transcript (faster-whisper CPU) — no GPU on this box, so OCR/torch was
skipped and gated behind an extra. Added a Sources tab to the UI and refactored
deps so a no-GPU install stays lean.

**Changes:**
- `pyproject.toml` — split monolithic deps into lean core (15) + extras
  (`transcript`/`ocr`/`vision`/`pdf`/`docs`/`ui`/`cpu`/`full`); `pip install -e .`
  no longer pulls torch.
- `scripts/install-extraction.sh` (new) — CPU-only torch wheel + easyocr for OCR later.
- `environment.yml` → `pip install -e ".[cpu]"` (torch-free); `config-deep.yaml`
  runs transcript+vision with `ocr:false`.
- `web` — Sources tab (`SourcesPage` + nav) to add/save IG URLs; `ReelsPage`
  now groups cards by category; `/api/sources` list/add/toggle over `sources.json`.
- Ran extraction: 11/11 phd reels summary+genre+facts, 8/11 transcript; knowledge
  base 6 topics / 33 reels; consolidated doc + index rebuilt.

**Decisions:**
- No NVIDIA GPU (Intel iGPU only) → don't install torch. faster-whisper (CTranslate2)
  and claude-cli vision are torch-free and cover transcript + summary/genre/facts.
  On-screen OCR (easyocr→torch) deferred behind `.[ocr]` + install script.
- Heavy imports are lazy, so gating them as extras degrades one feature at most —
  the core (fetch/sync/serve/doc) never breaks.

**Follow-ups:**
- [ ] Run `scripts/install-extraction.sh` + set `ocr:true` if on-screen text wanted.
- [ ] 3 music-only phd reels have no transcript (no speech) — expected.

## 2026-07-02 17:23 — phd-opportunities archive + incremental sync + two-track envs

**Summary:** Fetched the `phd-opportunities` saved collection into a local
self-contained HTML doc and served it through the React frontend, then built a
data-engineering incremental sync layer (`sources.json` registry → dedup →
new-only ingest → dead-letter ledger) so every run pulls only the latest reels
with no duplicates.

**Changes:**
- `src/reels_scrap/sources.py` (new) — declarative source registry + `poll_all`/
  `poll_source`; shortcode-keyed set-diff dedup over the flat `data/` pool,
  dead-letter set, run-state watermark (`output/sources_state.json`).
- `src/reels_scrap/cli.py` — `sync`, `add-source`, `list-sources` commands
  (`--retry-failed`, `--docs/--no-docs`).
- `environment.yml` (new) + `config-fast.yaml` (new) — two-track envs: lean
  `.venv` (fetch/sync/serve) vs full conda `reels-scrap` (torch/whisper/OCR);
  fast caption-only config for the venv path.
- `sources.json` (new) — phd-opportunities registered.
- `tests/test_sources.py` (new) — dedup + dead-letter + retry; suite 20 green.
- `docs/SYNC.md` (new), `TICKETS.md` — tickets 13–21; env + sync docs.

**Decisions:**
- Chrome `sessionid` auth failure root-caused to the lean install skipping
  `secretstorage` (declared dep) → encrypted session cookie silently failed to
  decrypt. Installed it; auth now works. Documented as required on Linux.
- Reel shortcode is the natural primary key; dedup is a set-diff against the
  shared pool, so a reel saved in two collections downloads once.
- Non-video posts (photo/carousel) permanently fail a *reels* extractor, so a
  dead-letter ledger stops re-attempting them every run — idempotency verified
  (run 2 → `new=0 deduped=29`).
- Deep extraction deliberately deferred (torch is multi-GB); caption-only fast
  pass drives the doc, conda env available on demand.

**Follow-ups:**
- [ ] Add image-post ingestion to capture the 18 photo/carousel saves.
- [ ] Run deep extraction (transcript/OCR/vision) via the conda env + `config.yaml`.
- [ ] Schedule `reels-scrap sync` (cron / systemd timer) for hands-off pulls.

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
