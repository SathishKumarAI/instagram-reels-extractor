# instagram-reels-extractor — STATUS

Update this when you STOP working, not when you start.

- **Last touched:** 2026-08-05 (on the **Windows** box, not the Rocky Linux one)
- **Where I stopped:** Full sync ran green — **45 new reels**, corpus now **665**
  (664 with summaries; the 1 gap is an image carousel, no video). Web UI + API
  running locally: API `127.0.0.1:8000`, Vite dev `localhost:5173`.
- **Windows port — four things had to change:**
  1. `.venv` is a Linux venv (`/home/deva/...`) — created `.venv-win` (py3.12,
     `pip install -e ".[docs]"`). `web/node_modules` needed a fresh `npm install`.
  2. Chrome 127+ encrypts cookies app-bound → yt-dlp **cannot** read them
     (`Failed to decrypt with DPAPI`, yt-dlp #10927). Closing Chrome does not help.
     `_ig_cookies()` now also accepts an exported Netscape `cookies.txt`
     (keeps `#HttpOnly_` rows — that is where `sessionid` lives), and
     `_browser_spec()` points the yt-dlp download path at the same file.
     Run with `--browser cookies.txt`; re-export when the session expires.
  3. `read_text()`/`write_text()` default to cp1252 on Windows and choke on emoji
     captions — `Reel.save/load` now force utf-8. Other callsites still bare:
     run with `PYTHONUTF8=1` (or `setx PYTHONUTF8 1`).
  4. A missing `mkdocs` binary used to kill the whole sync; now best-effort like PDF.
- **Sync was ~70 min slower than it should be:** `build_index` re-embeds the whole
  corpus (~3.5 min at 600 reels) and ran **once per source**. Now
  `run_pipeline(refresh_index=False)` per source + one index build at the end of
  `poll_all`.
- **New: Sync tab** (`/sync`, `web/src/views/SyncPage.tsx`) — pipeline strip
  (enumerate → download → extract+vision → docs → index), live `run.log` tail,
  per-source table, run-now button. Follows CLI-started syncs too, since `live`
  is derived from `run.log` mtime. Backed by an extended `GET /api/sync/status`.
- **New: local GPU vision** — Ollama on the RTX 5070 Ti.
  `scripts/ollama-vision.Modelfile` builds `reels-vision` from `qwen2.5vl:7b-q8_0`
  at 32k ctx (stock 4096 rejects even 4 frames). `config-local.yaml` points there
  with 6 frames @720px + 1500 max_tokens — parity with the Claude path.
  `LOCAL_NUDGE` in `extract/vision.py` spells out the schema floors for the local
  backend only (a 7B reads "3-8 facts" as "3"). Measured on 3 reels vs their
  stored Claude records: tags 5 vs 5-6, summary ~275 vs ~320 chars, facts 4-6 vs 8,
  **3-5s vs ~30s per reel**, $0. Caveat: it invented an anime title once — the 7B
  will guess a name Claude leaves out. Use with `sync -c config-local.yaml`.
- **Found the invisible reels:** saving a reel *without picking a collection* puts it
  only in the default "All Posts" feed, which had no source. `fetch_saved_feed()`
  (`ingest/collection.py`) + a `saved-all` source in `sources.json` closed it —
  first run: 26 new detected, **7 ingested**. Corpus now 672.
- **Security posture (repo is safe to publish):** no credential was ever committed
  (`git log --all -- cookies*` empty), no sessionid-shaped value in any tracked
  file, and `.githooks/pre-commit` now blocks credential filenames, sessionid/API-key
  values, and reel media — even via `git add -f`. Enable per clone:
  `git config core.hooksPath .githooks`. Checklist in `docs/PRIVACY.md`.
- **Plan + backlog written:** `docs/PLAN-2026-08.md` (requirements, 3 headline
  features, phasing) and `docs/BACKLOG-120.md` (134 items across 12 epics).
  Repo `CLAUDE.md` added for agents.
- **P0 slice DONE 2026-08-04** (all 43 tests pass, no `PYTHONUTF8` needed any more):
  - utf-8 on 43 read/write sites + stdout/stderr reconfigure in the CLI
  - `run.log` rotates (5MB × 3)
  - cookie-expiry probe prints `auth session ok (cookies.txt)` before a sync
  - `RateLimited` — 429 retries with backoff, then "will retry next run" (⏳, not ✗)
  - non-video posts skipped at enumerate: `saved-all` 200 → **182 real reels**,
    no more "No video formats found" dead-letters
  - `vision_concurrency: 3`
  - **incremental search index: 3m46s → 0.55s** (`index --full` forces a rebuild)
- **Compare tab DONE 2026-08-04** (backlog D1-D5, F3): `variants` on the reel record,
  `POST /api/reels/{id}/compare`, `/api/compare/batch|status|cancel|scoreboard`,
  and a `/compare` tab with metrics strip, side-by-side variants, claim diff and a
  corpus scoreboard. Claim matching uses **containment, not Jaccard** — Claude writes
  `No. 1 is "Project Based Learning" at github.com/...` where local writes
  `no. 1 PROJECT BASED LEARNING`; Jaccard scored that 0.3 and called it a
  disagreement. After the fix that reel reads 6 shared / 1 Claude-only / 0 local-only.
- **First scoreboard (4 reels, both backends):**

  | backend | facts | tags | summary chars | structured fields | sec | cost |
  |---|---|---|---|---|---|---|
  | claude-cli | 7.0 | 6.0 | 286 | 4.25 | 19.2 | $1.34 |
  | local | 5.0 | 5.0 | 205 | 1.75 | 7.9 | $0.00 |

  Claim disagreement averages 0.66 — still high, and `structured` coverage is the
  widest gap (4.25 vs 1.75 fields). Sample is 4 reels; run a bigger batch before
  switching the default backend.
- **Two-pass local extraction (C3): built, measured, left OFF.** 15 reels, same
  frames: 2-pass gets +0.94 facts but shorter summaries, *fewer* structured fields
  and 24% more time. Flag is `extract.vision_local_two_pass`.
  The bigger win came out of that measurement — local models nest `structured`
  under the genre (`{"educational": {...}}`) where Claude returns it flat, so every
  local record read as 1 field when it had 4. `_unwrap_structured()` normalises both.
- **Corpus-wide local variant backfill running** (`scripts/backfill_local_variants.py`,
  ~6s/reel, ~65 min for 665 reels, $0). Stores `variants.local` and leaves the active
  Claude record untouched — re-processing in place would have been a downgrade.
- **Docs scrubbed (K5):** real collection names, handles and collection ids replaced
  with stand-ins across 14 tracked files + the new docs.
  `scripts/scrub-personal.py --check` gates it (exit 1 if anything leaks back).
- **Coloured tag chips DONE (G1-G3):** `GET /api/tags` returns each tag with the
  collections it appears in; `web/src/components/TagChip.tsx` hashes the collection
  name (FNV-1a) to a Catppuccin accent, so a tag is the same colour everywhere.
  **664 of 1603 tags span 2+ collections**, so the split colour rail is the common
  case, not an edge case. Tags page gained a collection filter, sort and legend.
- **Discover pipeline DONE (B1, B5-B10):** `reels-scrap discover`, `/api/discover*`,
  and a Discover tab (card grid, Save / No / Later). First live run found **27
  candidates scoring 0.80-0.83** against collection centroids. Three bugs found by
  running it for real:
  1. `Budget` killed the run on the first `HTTP 429` — as designed.
  2. `author` holds the **display name**, not the handle, so profile lookups were
     doomed. Added `Reel.author_handle` (yt-dlp `channel`/`uploader_id`).
     **B2 (repeat-author candidates) is inert until reels are re-ingested** —
     the 673 existing records have no handle.
  3. Hashtags: our tags are slugs (`open-source`) and IG has none — use caption
     hashtags (`opensource`). And `/tags/web_info/` returns 200 with **zero**
     media; `/tags/<tag>/sections/` is the endpoint that carries posts.
- **`author_handle` backfilled — 663 reels**, from the feed payloads we already
  page (`user.username` was there and discarded). Zero extra Instagram requests.
  8 creators now qualify as repeat-saves, so author-based discovery has input.
- **Phase 4 (production) done:** `scripts/setup-windows.ps1` (idempotent bootstrap;
  `-Schedule` = nightly sync + weekly discovery, `-Autostart` = API at logon),
  rich `/api/health` (disk, index freshness, cookie age, local vision, `?deep=true`
  session probe), CI with pytest + ruff + tsc + a full-history secret scan, and
  `docs/SETUP.md` written for someone who is not you. Ruff: **78 findings → 0**.
- **Incremental index now keys on a content hash, not mtime.** Writing a Compare
  variant or backfilling `author_handle` rewrites a reel's json without changing
  its indexed text — on an mtime key that forced a full 665-reel re-embed. One
  4m14s rebuild installs the hashes; every run after is **1.0s**.
- **Both backfills finished (2026-08-05):** local variants **635 ok / 6 failed**
  in 90.8 min (641 of 674 reels now carry a `variants.local`), and GPU transcripts
  (C6) across the corpus — **454 transcribed, 123 silent, 0 failed** in 19.6 min at
  6.5× realtime. 527 reels have transcript text.
- **Epic M P1 slice DONE 2026-08-05 (M1, M4, M5, M6):**
  - `reels_by_collection()` in `collections.py` — one manifest inverter, replacing
    the loop that was copy-pasted into `/api/reels` and `/api/tags`.
  - `GET /api/reels/{id}` now returns `collections`. It never did, so the reader's
    collection chips had been rendering an empty list all along.
  - `ReelSummary.model` added (`tokens.model` was stored, never exposed).
  - `web/src/components/ModelBadge.tsx` — provenance badge on card, drawer, reader
    and a new table column; `backendChip` moved out of `ReelsPage` (the reader was
    importing it cross-view).
  - `CollectionChip` in `TagChip.tsx` — same FNV-1a accent as the tags page, so a
    shelf is one colour everywhere. Click filters the grid;
    `/reels?collection=<slug>` is the deep link from reader and table.
  - Measured on the live corpus: **644 Claude / 25 local / 5 unknown**, 19 shelves,
    **175 reels on 2+ shelves**, 10 on none.
- **The model bench is built and has been run (2026-08-06).** This is now a
  research project with its own home: `docs/research/`.
  - **Profiles** (`profiles.py`): a model is a *name*, and `reel.variants` is keyed
    by it, so eight models coexist on one reel. `claude-cli`/`api`/`local` still
    resolve with no config change — the 641 stored variants never moved. A model
    in `models.yaml` resolves by name too, which is why the hand-commented
    `config-local.yaml` is never rewritten.
  - **Registry** (`models.yaml`, `modelreg.py`): `models list|pull`. **7/7
    installed**, ~38GB. Each entry earns its place by the contrast it tests; a
    pull is always explicit and a hand-built model is never rebuilt.
  - **Bench** (`bench.py`): `bench sample|run|report`. One seeded, genre-stratified
    30-reel sample, cached frames and transcripts reused, resumable, one model
    resident at a time. Failures land in `runs.jsonl`, never in an average.
  - **Report**: `docs/research/BENCH-2026-08-06.md` — metrics, agreement vs the
    Claude arm, attempts, and a written why-they-differ pass grounded in quoted
    claims. Also `MODELS.md`, `UI-TABS.md`, `COSTS.md`, and one prompt per build
    step in `docs/research/prompts/`.
- **What the bench found** (30 reels, identical frames, $0 for every local arm):

  | model | facts | tags | summary | fields | empty | sec | $/reel |
  |---|---|---|---|---|---|---|---|
  | claude-cli (ref) | 7.4 | 5.7 | 833 | 4.0 | 0 | 29.7 | $0.34 |
  | qwen3vl-8b | 6.4 | 5.9 | 419 | 3.0 | 0 | 42.9 | $0 |
  | qwen3vl-4b | 5.9 | 5.3 | 448 | 2.5 | 2 | 29.6 | $0 |
  | gemma4-12b | 5.6 | 4.9 | 377 | 2.7 | 2 | 60.9 | $0 |
  | minicpm-v45 | 5.6 | 6.6 | 401 | 2.1 | 0 | **7.3** | $0 |
  | reels-vision | 5.2 | 4.9 | 293 | 1.8 | 1 | 7.7 | $0 |
  | qwen3vl-2b | 0.9 | 3.1 | 177 | 21 empty | | 44.9 | $0 |
  | deepseek-ocr | arm abandoned — 0 usable in 10 attempts | | | | | | |

  Different failure classes, not one axis. **minicpm-v45** is the value pick —
  within 0.8 facts of the 8B at a fifth of the time. **qwen3vl-4b is the risky
  one**: the only arm asserting claims that contradict the reference ("Touching
  the kitchen area is now considered illegal under the 2025 rules"). **qwen3vl-2b
  is unusable as shipped.** **deepseek-ocr can read but cannot be instructed** —
  its template-echo output contained real on-screen text.
- **Nine pipeline bugs found by running the experiment** — each one had been
  making a model look worse than it is:
  1. reasoning models put the answer in `reasoning`, not `content`;
  2. a 1500- then 4000-token budget ran out before the JSON closed (now 8000);
  3. a greedy `{.*}` spanned several objects — take the finished one, not the sketch;
  4. `"facts": ["…"]` (a claim with no frame) was dropped entirely;
  5. `_is_fragment` rejected any claim starting lower case, deleting the output of
     models that do not capitalise;
  6. an empty variant counted as a processed reel;
  7. the claim matcher scored the narration ("Frame 2 displays…"), punishing the
     models that obey our own grounding instruction — agreement 5% → 12%;
  8. every text-mode subprocess decoded as cp1252 on Windows;
  9. `claude -p <prompt>` passed the prompt as argv, so a large analysis silently
     degraded to "unavailable" (WinError 206). Prompts go on stdin now.
- **Also shipped:** any installed model can run a sync (`/api/sync` + one shared
  `ModelSelect` on Sync, Sources and Compare); the Compare scoreboard shows
  `$/reel`, `$ total` and an `empty` column; a UI sync no longer silently skips
  transcripts and OCR.
- **Where it stands:** **114 tests pass**, ruff clean, `tsc -b` + `vite build`
  clean. 13 tabs. Corpus 674 reels. API + Vite dev server both up.
- **Known gaps, stated plainly:**
  - **Every local model misses caption-derived claims** (`#manuspartner`, `#ad`)
    and small print. That is an input problem, not a ranking — the caption may not
    be reaching the model. First thing to chase.
  - `deepseek-ocr` was stopped at 10 of 30 attempts once the failure mode repeated
    ten times; the report says so rather than implying a full arm.
  - The Claude arm is 28 of 30: two reels return exit 0 with empty stdout from the
    CLI, twice each.
  - Author-based discovery is code-complete but Instagram 429s the profile
    endpoint after heavy use. The hashtag path works (27 candidates).
  - Local RAG chat (L1) not built. The UI was verified by build + live API, not by
    eye — no Chrome extension on this box, and the devtools MCP loses its browser.
- **Next session:** the caption/fine-print gap above, then Epic M **M2** (inline
  local-vs-cloud diff in the reader — 641 reels have both variants and
  `diff_facts` is pure, but there is still **no read-only endpoint that diffs
  stored variants**), M3 (filter by model) and M7 (collection on search hits).
- **Blocked on:** nothing. Two decisions are the owner's: whether a local model
  becomes the sync default, and whether to re-extract the corpus with one.
