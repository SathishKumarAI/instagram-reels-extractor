# instagram-reels-extractor — STATUS

Update this when you STOP working, not when you start.

- **Last touched:** 2026-08-04 (now on the **Windows** box, not the Rocky Linux one)
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
- **Where it stands:** 68 tests pass, ruff clean (78 findings → 0), `tsc -b` clean,
  API + UI up. 13 tabs. Corpus 674 reels.
- **Known gaps, stated plainly:**
  - Author-based discovery is code-complete but Instagram is 429ing the profile
    endpoint after a session of heavy use — needs a cooldown to verify end to end.
    The hashtag path works (27 candidates found).
  - GPU transcripts (C6) and local RAG chat (L1) not built — see the plan for why.
  - Local variant backfill still running at ~306/665 when this was written.
- **Next session:** Epic M in `docs/BACKLOG-120.md` — the owner's parked requests:
  model-provenance badges everywhere, per-reel local-vs-cloud diff in the reader,
  and **collection tags on every reel** (`front-end`, `topic-books`, `ai`).
- **Blocked on:** nothing. Open questions for the owner in `docs/PLAN-2026-08.md` §5.
