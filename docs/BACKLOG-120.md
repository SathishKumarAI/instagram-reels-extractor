# Feature Backlog — 174 items (2026-08-04)

Supersedes `docs/BACKLOG-50.md` (kept for history). Grouped into 12 epics.

**P** priority P0 (now) → P3 (someday) · **E** effort S/M/L · **V** value ★–★★★
Status: ☐ todo · ◑ wip · ☑ done. `→` = depends on.

Design rule for every item: one thin vertical slice (store → API → UI), heavy
imports lazy, degrades gracefully when a backend is missing, and any non-trivial
logic ships with one runnable check.

---

## Epic A — Ingestion & sources (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| A1 | ☑ Named saved-collection source | — | — | ★★★ | shipped |
| A2 | ☑ Default "All Posts" saved feed source | — | — | ★★★ | shipped 2026-08-04 — 7 reels were invisible without it |
| A3 | ☑ cookies.txt auth path (Windows/app-bound Chrome) | — | — | ★★★ | shipped; `_ig_cookies` takes a file |
| A4 | ☑ Cookie expiry probe (CLI banner) | — | — | ★★★ | done 2026-08-04; UI banner still todo |
| A5 | ☑ 429 backoff + `RateLimited` (retry next run, not an error) | — | — | ★★ | done 2026-08-04 |
| A6 | ☑ Skip non-video posts at enumerate | — | — | ★★ | done 2026-08-04; saved-all 200 → 182 real reels |
| A7 | Hashtag source type | P2 | M | ★★ | `#tag` → feed → same pipeline |
| A8 | Author/profile source with follow-count guard | P2 | M | ★★ | exists, needs rate-limit discipline |
| A9 | Import from Instagram data export (ZIP) | P3 | M | ★ | backfill history without scraping |
| A10 | Per-source schedule override (nightly/weekly/manual) | P2 | S | ★★ | field exists in registry |
| A11 | Source health score (last ok, error streak, staleness) | P1 | S | ★★ | surface in Sources + Sync tabs |
| A12 | Re-enumerate only if IG count changed (cheap HEAD-ish check) | P2 | S | ★ | fewer API calls per night |

## Epic B — Discovery & recommendation (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| B1 | ☑ `discover` command — hashtag harvest | — | — | ★★★ | done 2026-08-04; `/tags/<t>/sections/`, not `web_info` |
| B2 | ☑ Candidates from repeat authors | — | — | ★★★ | done 2026-08-04; handles captured during enumerate + backfilled |
| B3 | Candidates from IG "related" surface on a reel page | P2 | M | ★★ | needs HTML/graphql probing |
| B4 | Candidates from your Explore feed | P2 | M | ★★ | already personalised |
| B5 | ☑ Score vs per-collection centroid | — | — | ★★★ | done 2026-08-04; live scores 0.80-0.83 |
| B6 | ☑ Candidate store + state | — | — | ★★★ | done 2026-08-04 (`output/discover.json`) |
| B7 | ☑ **Discover tab** | — | — | ★★★ | done 2026-08-04 |
| B8 | ☑ "Why this matched" per card | — | — | ★★ | done 2026-08-04 (collection + source) |
| B9 | ☑ Reject memory | — | — | ★★ | done 2026-08-04 |
| B10 | ☑ Request budget + 429 kill-switch | — | — | ★★★ | done 2026-08-04; fired on the first live run |
| B11 | Nightly discovery schedule (jittered) | P2 | S | ★★ | → J3 |
| B12 | Negative signals — learn from rejects (down-weight tags/authors) | P3 | M | ★★ | needs ~50 rejects to matter |

## Epic C — Extraction quality & local models (14)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| C1 | ☑ Local vision via Ollama (qwen2.5vl 7B q8, 32k ctx) | — | — | ★★★ | 3-5s/reel, $0 |
| C2 | ☑ Local prompt floors (`LOCAL_NUDGE`) | — | — | ★★ | tags 3→5, summary 2× longer |
| C3 | ☑ Two-pass extraction (opt-in) | — | — | ★★ | done 2026-08-04; +0.94 facts but worse summaries — default off |
| C4 | Confidence field per fact + "unverified" badge | P1 | M | ★★★ | local model invented an anime title |
| C5 | Claude re-check only for low-confidence records | P2 | M | ★★ | hybrid, cost-bounded |
| C6 | GPU transcripts (faster-whisper CUDA) | P1 | M | ★★★ | today both paths are deaf |
| C7 | Speaker-free caption cleanup / dedup of subtitle spam | P2 | S | ★ | subtitles repeat across frames |
| C8 | Scene-aware frame sampling (`select='gt(scene,0.4)'`) | P2 | M | ★★ | fewer, sharper frames |
| C9 | OCR pass for dense text frames (easyocr, GPU) | P3 | M | ★ | VLM mostly covers it now |
| C10 | Prompt/schema in config, not code | P2 | M | ★★ | per-collection schemas |
| C11 | Model registry — pick model per source | P3 | M | ★ | anime ≠ job posts |
| C12 | Re-extract one reel from the UI | P1 | S | ★★ | button → job → variant |
| C13 | ◑ Corpus-wide local **variants** (not overwrite) | P2 | L | ★★ | running 2026-08-04, ~6s/reel |
| C14 | Structured-field coverage metric per genre | P2 | S | ★★ | local fills 1-2 fields vs Claude's 3 |

## Epic D — Model comparison & evaluation (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| D1 | ☑ `variants` on the reel record | — | — | ★★★ | done 2026-08-04 |
| D2 | ☑ `POST /api/reels/{id}/compare` | — | — | ★★★ | done 2026-08-04 |
| D3 | ☑ **Compare tab** — side-by-side + metrics strip | — | — | ★★★ | done 2026-08-04 |
| D4 | ☑ Claim-level diff (containment matcher) | — | — | ★★★ | done 2026-08-04; Jaccard alone read paraphrase as disagreement |
| D5 | ☑ Batch compare + scoreboard | — | — | ★★★ | done 2026-08-04; 4 reels so far |
| D6 | Hallucination check — claims not present in any frame text | P2 | M | ★★★ | catches invented titles automatically |
| D7 | Cost/quality curve per model | P2 | S | ★★ | $/reel vs facts/reel |
| D8 | Golden set — 20 hand-checked reels as regression tests | P2 | M | ★★★ | stops silent quality drift |
| D9 | Latency percentiles per backend | P3 | S | ★ | p50/p95, not averages |
| D10 | A/B a prompt change against the golden set | P2 | M | ★★ | → D8 |
| D11 | Human verdict button (which is better) | P3 | S | ★★ | ground truth for D5 |
| D12 | Export comparison report as Markdown | P3 | S | ★ | shareable evidence |

## Epic E — Search & retrieval (10)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| E1 | ☑ Incremental index, keyed on content hash | — | — | ★★★ | done 2026-08-04: 4m14s → **1.0s**; mtime keying re-embedded on variant writes |
| E2 | Hybrid search — BM25 + dense | P1 | M | ★★★ | exact tool names fail pure-vector |
| E3 | Local cross-encoder rerank | P2 | M | ★★ | quality per retrieved chunk |
| E4 | Filtered search (collection, genre, date, author) | P1 | S | ★★★ | filters exist in UI, not in search |
| E5 | Chunk-level citations with timestamps | P2 | M | ★★ | jump to the second in the video |
| E6 | Near-duplicate detection across collections | P2 | M | ★★ | same reel re-shared |
| E7 | Search-as-you-type with debounce | P2 | S | ★★ | feels twice as fast |
| E8 | Saved searches / smart collections | P2 | M | ★★ | "AI + this month" |
| E9 | Index health panel (size, freshness, dim) | P3 | S | ★ | in the Sync tab |
| E10 | Embedding model swap without full re-index | P3 | L | ★ | versioned index dirs |

## Epic F — Frontend information architecture (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| F1 | ☑ Sync tab — pipeline, live log, per-source table | — | — | ★★★ | shipped 2026-08-04 |
| F2 | ☑ Discover tab | — | — | ★★★ | done 2026-08-04 |
| F3 | ☑ Compare tab | — | — | ★★★ | done 2026-08-04 |
| F4 | Tab consolidation — 11 tabs is already too many | P1 | M | ★★ | group: Library / Discover / Insight / Ops |
| F5 | Command palette (Ctrl-K) — jump to reel, tag, collection | P2 | M | ★★★ | replaces half the nav |
| F6 | Per-page three-zone contract (orient / act / review) | P2 | M | ★★ | pages are flat card stacks today |
| F7 | Keyboard nav in the reel grid (j/k/enter) | P2 | S | ★★ | archive is browsed, not clicked |
| F8 | Deep links that survive refresh for every filter state | P2 | S | ★★ | filters live in component state now |
| F9 | Empty/loading/error states for every view | P1 | S | ★★ | several views render blank on failure |
| F10 | Mobile/tablet layout | P3 | M | ★ | it is a desktop tool today |
| F11 | Onboarding for a fresh clone (no data yet) | P2 | S | ★★ | first-run is currently a blank grid |
| F12 | Per-collection landing page | P2 | M | ★★ | collection as a first-class object |

## Epic G — Visual design & interaction (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| G1 | ☑ **Collection-coloured tag chips** | — | — | ★★★ | done 2026-08-04 (FNV-1a → accent) |
| G2 | ☑ Split rail for multi-collection tags | — | — | ★★ | done; 664 of 1603 tags span 2+ |
| G3 | ☑ Colour legend + collection filter | — | — | ★★ | done 2026-08-04 |
| G4 | Thumbnail hover-scrub (frame strip preview) | P2 | M | ★★ | frames already on disk |
| G5 | Density toggle — comfortable / compact | P2 | S | ★★ | 665 cards is a lot of scrolling |
| G6 | Consistent stat tiles (one visual language) | P2 | S | ★★ | numbers styled differently per page |
| G7 | Skeleton loaders instead of layout jumps | P2 | S | ★★ | grid reflows on load |
| G8 | Focus-visible + contrast audit (a11y baseline) | P1 | S | ★★★ | not optional |
| G9 | Reduced-motion respect for the pulsing live badge | P2 | S | ★ | `prefers-reduced-motion` |
| G10 | Genre iconography (one glyph per genre) | P3 | S | ★ | faster scanning than text |
| G11 | Print/PDF stylesheet for a collection | P3 | S | ★ | reuse render layer |
| G12 | Theme QA across all 12 Catppuccin variants | P3 | S | ★ | switcher exists, untested |

## Epic H — Data model & backend architecture (10)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| H1 | Schema version on every reel record + migrations | P1 | M | ★★★ | `variants` is the first breaking change |
| H2 | SQLite index over `data/*.json` | P1 | L | ★★★ | 665 files re-read per API call today |
| H3 | Typed job queue (sync, discover, compare, re-extract) | P1 | M | ★★★ | one global `_SYNC` dict is the whole state now |
| H4 | Job history with per-job logs | P1 | M | ★★ | → H3; Sync tab reads it |
| H5 | Collection as a stored entity, not a manifest file | P2 | M | ★★ | → F12 |
| H6 | Soft-delete + restore for reels | P2 | S | ★ | nothing is deletable today |
| H7 | Idempotency keys on ingest | P2 | S | ★ | double-click safety |
| H8 | Split `api/app.py` (500+ lines) into routers | P2 | M | ★★ | it is becoming a junk drawer |
| H9 | ☑ utf-8 on every read/write + stdout reconfigure | — | — | ★★★ | done 2026-08-04: 43 call sites; no `PYTHONUTF8` needed |
| H10 | Config layering: repo default + `config.local.yaml` | P1 | S | ★★ | machine-specific values leak into git today |

## Epic I — Performance & GPU utilisation (10)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| I1 | ☑ Index built once per sync, not per source | — | — | ★★★ | shipped — was ~70 min/run |
| I2 | ☑ `vision_concurrency: 3` | — | — | ★★★ | done 2026-08-04 |
| I3 | Model keep-alive tuning (avoid reload per call) | P1 | S | ★★ | first call 19s, warm 4s |
| I4 | VRAM-aware scheduling (vision vs chat model) | P1 | M | ★★ | 9.4GB + 5GB will not co-reside in 16GB |
| I5 | Parallel frame extraction | P2 | S | ★ | ffmpeg is single-threaded per reel |
| I6 | Thumbnail/video streaming with range + cache headers | P2 | S | ★★ | grid loads 100+ thumbs |
| I7 | Frontend virtual scrolling | P2 | M | ★★ | 665 DOM cards |
| I8 | API response caching with invalidation on sync | P2 | M | ★★ | `/api/reels` re-reads everything |
| I9 | Batch embed with larger batch size on GPU | P2 | M | ★★ | fastembed is CPU today |
| I10 | Profile the sync end-to-end, publish a flamegraph | P3 | M | ★ | find the next I1 |

## Epic J — Ops, scheduling, reliability (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| J1 | ☑ Autostart via scheduled task (`-Autostart`) | — | — | ★★★ | done 2026-08-04 (`scripts/setup-windows.ps1`) |
| J2 | ☑ Nightly sync + weekly discover tasks | — | — | ★★★ | done 2026-08-04 (`-Schedule`) |
| J3 | ☑ Weekly discovery job | — | — | ★★ | done 2026-08-04 |
| J4 | ☑ `run.log` rotation (5MB × 3) | — | — | ★★ | done 2026-08-04 |
| J5 | ☑ Rich `/api/health` (+`?deep=true` session probe) | — | — | ★★★ | done 2026-08-04 |
| J6 | Backup `data/` + `output/` to `~/vault/` with retention | P1 | M | ★★★ | the corpus is irreplaceable |
| J7 | Restore drill — document and test it | P2 | S | ★★ | a backup nobody restored is a rumour |
| J8 | Dead-letter management UI (retry / dismiss) | P1 | M | ★★ | 24 dead ids are invisible in the UI |
| J9 | ☑ `scripts/setup-windows.ps1` | — | — | ★★★ | done 2026-08-04; idempotent |
| J10 | ☑ CI: pytest + ruff + tsc + secret scan | — | — | ★★ | done 2026-08-04 (`.github/workflows/ci.yml`) |
| J11 | Desktop notification on sync failure | P2 | S | ★ | silent failure is the worst kind |
| J12 | Version stamp (git sha) in the UI footer | P3 | S | ★ | "which build am I looking at" |

## Epic K — Security, privacy, sharing (8)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| K1 | ☑ Pre-commit guard for credentials + media | — | — | ★★★ | shipped; blocks sessionid values and `git add -f` |
| K2 | ☑ Repo verified clean of secrets, history included | — | — | ★★★ | `git log --all -- cookies*` empty |
| K3 | Cookie file permission check + age warning | P1 | S | ★★ | a stale cookie is a silent outage |
| K4 | Encrypt `cookies.txt` at rest (DPAPI) | P2 | M | ★★ | plaintext live login on disk today |
| K5 | Redact collection names from public docs | P2 | S | ★★ | they reveal job-hunting intent |
| K6 | Public-facing README for reproducers | P1 | M | ★★★ | how to set this up *safely* |
| K7 | ☑ Secret scan in CI (filenames, values, history) | — | — | ★★ | done 2026-08-04 |
| K8 | API bound to 127.0.0.1 by default + auth if exposed | P1 | S | ★★★ | no auth today; fine local, not fine on a LAN |

## Epic L — Insight, cost, knowledge (12)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| L1 | Local RAG chat (retrieval + local LLM + citations) | P1 | L | ★★★ | Claude becomes the "deep answer" button |
| L2 | Cost dashboard — $/collection, $/run, cumulative | P1 | S | ★★★ | `total_cost_usd` already stored |
| L3 | Local-vs-Claude savings counter | P2 | S | ★★ | → L2, D5 |
| L4 | Auto topic clustering over the corpus | P2 | M | ★★ | knowledge tab is manual today |
| L5 | Entity extraction + cross-reel linking (tools, repos, people) | P2 | L | ★★★ | the "knowledge graph" ask |
| L6 | Weekly digest — what you saved, what it was about | P2 | M | ★★ | email/markdown |
| L7 | "Unread / to-action" workflow states | P2 | M | ★★ | archive → actionable |
| L8 | Per-collection quality report (missing summaries, thin records) | P2 | S | ★★ | finds the 1 reel with no summary |
| L9 | Trend view — what topics grew month over month | P3 | M | ★ | timestamps exist |
| L10 | Export to Markdown/CSV/Notion | P2 | S | ★★ | reuse render layer |
| L11 | Reel → "apply/build/watch" task extraction | P3 | M | ★★ | job posts become todos |
| L12 | Corpus stats page (genres, authors, duration, gaps) | P3 | S | ★ | one honest overview |

---

## Epic M — Owner requests, parked 2026-08-04 (13)

Raised mid-session, deliberately **not** built yet. Listed here so they survive
the conversation.

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| M1 | Show which model produced a record, everywhere it is read | P1 | S | ★★★ | badge on reel card/reader: `local · reels-vision` vs `claude · sonnet-4-6`. Provenance already lives in `tokens.backend`/`tokens.model` — it is simply never rendered |
| M2 | Per-reel model diff, inline (not only the Compare tab) | P1 | M | ★★★ | when a reel has 2+ `variants`, offer a toggle on the reader: read the local version vs the cloud one, with changed claims highlighted |
| M3 | "Which model wrote this?" filter | P2 | S | ★★ | filter the library by backend — find every record produced locally before the quality fixes landed |
| M4 | Collection tags on every reel (`front-end`, `topic-books`, `ai`) | P1 | M | ★★★ | today a reel shows only *topic* tags (`ai-tools`) and genre (`educational`). The saved-collection it came from is the tag you actually think in. Data exists (manifests → `ReelSummary.collections`); needs chips wherever tags render, using the same colour hash as G1 |
| M5 | Filter/browse by collection tag | P1 | S | ★★★ | → M4; click `topic-books` anywhere, see that shelf |
| M6 | Multi-collection reels rendered honestly | P2 | S | ★★ | a reel saved to 3 collections shows 3 chips, not a truncated one |
| M7 | Collection tag on search results and chat citations | P2 | S | ★★ | answers should say which shelf a citation came from |
| M8 | Manual tags — your own words, per reel | P2 | M | ★★ | model tags are generated; a hand tag is a promise. Keep them visually distinct |
| M9 | Tag/collection rename that updates every surface | P2 | M | ★★ | rename exists for tags; collections are renamed by editing `sources.json` by hand |
| M10 | Cost-per-model rollup in the UI | P2 | S | ★★ | "this month: local 412 reels $0 · cloud 61 reels $23" — data is in `tokens`, → L2 |
| M11 | Quality badge per record (facts count, structured coverage) | P3 | S | ★★ | makes thin records visible without opening them |
| M12 | Re-run one reel on the other model, from the reader | P2 | S | ★★ | one click to upgrade a thin local record to Claude |
| M13 | Model-mix policy per collection | P3 | M | ★★ | e.g. `topic-jobs` always Claude, `anime` always local — quality where it pays |


## Epic N — Extraction quality (7) — from `docs/WORKFLOW-RESEARCH.md`

Diagnosed 2026-08-04: transcripts cover **10.5%** of the corpus, OCR **3.4%**, and
only 6 of ~21 extracted frames are ever sent. A 16-frame test produced *more* facts
but they were subtitle fragments ("years now and") — so the missing substance is
**audio**, not frames.

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| N1 | GPU transcripts (`faster-whisper` + CUDA) | P0 | M | ★★★ | recovers speech for ~600 reels that have none; needs ~2GB of wheels |
| N2 | Prompt splits overlay text from subtitle stream | P0 | S | ★★★ | stops subtitle fragments being emitted as facts |
| N3 | Scene-change frame sampling (`select='gt(scene,0.3)'`) | P1 | M | ★★ | catch every title card, skip 15 identical talking-head frames |
| N4 | Richer summary contract (3-5 sentences + `key_points` + verbatim `on_screen_text`) | P0 | S | ★★★ | the schema currently *asks* for "1-2 sentences" — vagueness is specified |
| N5 | Fact hygiene — drop fragments, merge cross-frame duplicates | P1 | S | ★★ | the 16-frame run is the reproducer |
| N6 | Per-record quality score, surfaced in the UI | P1 | S | ★★ | makes thin records visible |
| N7 | Re-process the corpus after N1-N5 | P1 | L | ★★★ | ~674 reels, 3-4 GPU hours, $0 |

## Epic O — Sources beyond Instagram (7)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| O1 | Substack / newsletter via RSS | P1 | S | ★★★ | `rss` source type already works — needs UI + a text-card design |
| O2 | YouTube channel / playlist | P1 | M | ★★★ | yt-dlp handles it; real captions beat burned-in subtitles |
| O3 | Instagram Explore as a discovery signal | P2 | M | ★★ | already personalised to you |
| O4 | Reddit / HN by sub or keyword | P2 | S | ★★ | plain JSON, no auth |
| O5 | arXiv saved queries | P2 | S | ★★ | `arxiv` type exists |
| O6 | Podcast feeds | P3 | M | ★★ | audio reuses N1 |
| O7 | Paste-anything box / bookmarklet | P2 | S | ★★★ | one corpus, any URL |

## Epic P — Research layer, the "personal Google" (7)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| P1 | Hybrid search (BM25 + vector) | P1 | M | ★★★ | exact tool/repo names lose to vector fuzz today |
| P2 | Local RAG chat with citations | P1 | L | ★★★ | Claude becomes an opt-in "deep answer" |
| P3 | Entity extraction + cross-source linking | P2 | L | ★★★ | tools/repos/people/papers as nodes |
| P4 | Timeline of what you saved, by month | P3 | M | ★ | your own trend line |
| P5 | Duplicate + contradiction surfacing | P2 | M | ★★ | five reels, one claim |
| P6 | Weekly digest (markdown) | P2 | M | ★★ | what you saved, what it meant |
| P7 | Ask across sources in one answer | P2 | M | ★★★ | reel + Substack + paper, one citation list |

## Epic Q — Output: from research to what you publish (6)

| # | Feature | P | E | V | Notes |
|---|---|---|---|---|---|
| Q1 | Idea inbox ("use this") with citation attached | P2 | S | ★★★ | the capture end of publishing |
| Q2 | Cluster → draft, every claim linked to its reel + timestamp | P2 | M | ★★★ | the leverage feature |
| Q3 | Format targets (LinkedIn / X / newsletter / blog) | P3 | M | ★★ | one draft, several shapes |
| Q4 | Citations by construction — no uncited generated line | P2 | S | ★★★ | this corpus is other people's work |
| Q5 | "What did I miss" pre-publish check | P3 | S | ★★ | saved material you never opened |
| Q6 | Publish log | P3 | S | ★ | stop repeating yourself |


## Suggested first slice (2 weeks of evenings)

P0 only, in this order — every one is S effort and removes a live annoyance:

1. H9 utf-8 everywhere → stop depending on `PYTHONUTF8=1`
2. J4 log rotation → `run.log` is unbounded
3. A4 + K3 cookie expiry probe → the #1 cause of "everything broke"
4. A5 429 backoff, A6 carousel skip → clean sync output
5. I2 concurrency 2-3 → free throughput on an idle GPU
6. E1 incremental index → the last big time sink in a sync
7. B10 request budget → prerequisite before any discovery code exists

Then Phase 2 (C3, D1-D5) decides whether local becomes the default backend, using
numbers rather than the current three-reel sample.
