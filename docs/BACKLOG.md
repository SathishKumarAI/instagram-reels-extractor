# Feature Backlog — reels-scrap

Prioritized by **value ÷ effort**, grouped into shipping tiers. Status: ☐ todo · ◑ in progress · ☑ done.

The research platform itself (ingest → extract → structure → render → search → API → UI)
is built (see `TICKETS.md`). This backlog is about making it a **good, reliable codebase**
and closing the gaps that show up in real use.

---

## Product roadmap — toward a usable product (2026-07-02)

Shipped this session (see TICKETS 22–27 + tasks): incremental multi-source `sync`,
Sources tab (add/save URLs), category-grouped dashboard, **per-reel tags**,
**per-reel + per-category token metering** (`/api/stats`), privacy hardening.

Next, to make it a genuinely usable product:

| Feature | Value | Effort | Why |
|---------|-------|--------|-----|
| **Backfill tags/tokens** on existing reels (re-extract) | ★★★ | S | current archive predates the feature; one re-vision pass populates all |
| **Cost dashboard** — $ from tokens (model price × in/out), per-collection spend, per-run cost | ★★★ | S | `total_cost_usd` is already in the claude envelope; surface it |
| **Tag pages / tag cloud** — click a tag → all reels across collections | ★★☆ | S | tags exist; add a `/tags` route + `/api/reels?tag=` filter |
| **Global search bar** in the dashboard (semantic + tag + text) | ★★★ | M | `/api/search` exists; wire a top-bar omnisearch |
| **Saved views / smart collections** (e.g. "all jobs+internships", "AI this month") | ★★☆ | M | cross-collection filters over genre+tag+date |
| **Export** — Markdown / CSV / Notion per collection | ★★☆ | S | reuse render layer; add `/api/export` |
| **Scheduled sync** — cron/systemd timer running `sync` nightly | ★★★ | S | incremental + dead-letter already make it safe to automate |
| **Reel status flags** — read/unread, starred, archived, "to-apply" | ★★☆ | M | turns the archive into an actionable workflow |
| **Dedup near-duplicates** across collections (same reel re-shared) | ★★☆ | M | shortcode dedup is exact; add perceptual/caption similarity |
| ☑ **Local LLM vision option** (privacy) — DONE 2026-07-11: `local` backend (OpenAI-compatible, Kimi-VL on your GPU box), strict no-egress. See `docs/LOCAL-VISION.md` + `docs/PROJECT-STATUS.md` | ★★☆ | L | closes the one egress point for fully-air-gapped use |

---

## Now — shipped / in flight

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 1 | **Local consolidated docs** — `collection <url>` (fetch→extract→doc→open) + `consolidate` (rebuild from data) + per-collection membership manifests + master index | ★★★ | M | ☑ | `render/consolidated.py`, `collections.py`, `docs.py`, CLI cmds, `tests/test_docs.py` (7 passing). Self-contained HTML, thumbnails embedded, links back to reels. |
| 2 | **Reproducible dev env** — the `.venv` was broken (interpreter shebang pointed at the repo's *old* path `insta_reels_scrap/`, pre-rename). Recreated with mise py3.12; added `[dev]` extras (pytest, ruff) + pytest config | ★★★ | S | ☑ | Lean install (server+search+tests, no torch chain). Suite green (17). Extraction deps (whisper✓ now, easyocr/weasyprint/yt-dlp still skipped) install on demand. |

## Next — high value, do soon

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 3 | **`reels-scrap collections` (list/status)** — table of downloaded collections: name, #reels, #with-vision, last updated, doc path | ★★ | S | ☐ | Reads manifests + `run_report.json`. Cheap, high everyday utility. |
| 4 | **Transcript quality** — non-English reels garbled by forced-English decoding. Now auto-detect language + Whisper `task=translate`; record `transcript_language/_translated/_confidence`; ⚠ badge in the doc | ★★★ | M | ☑ | 22 re-transcribed; the Hindi reel now reads as English (detect p=0.997) + badged. Quality is `whisper_model`-bound (base fumbles; small/medium better) — bump the model for accuracy. `scripts/retranscribe.py` re-runs just this stage. |
| 5 | **Doc test coverage for render/pipeline** — only api/knowledge/rag are tested. Add render (markdown+pdf), structure, and an ingest-mock pipeline test | ★★ | M | ☐ | Guards the parts users actually see. |
| 6 | **Incremental / idempotent guarantees, verified** — `resume` skips downloaded reels; add a test proving re-run of `collection` re-downloads nothing and only re-renders | ★★ | S | ☐ | Protects the "run it again when I save more" workflow. |

## Later — nice to have

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 7 | **Search/knowledge scoped to a collection** — `search --collection front-end`, per-collection knowledge base | ★★ | M | ☐ | Manifests already give the reel-id set to filter on. |
| 8 | **Combined & per-collection PDF** — reuse `render/combined` to emit a print-ready PDF alongside the HTML doc | ★ | S | ☐ | HTML is primary; PDF for offline/sharing. |
| 9 | **UI: collections view** — surface collections + their docs in the Streamlit/React app | ★★ | M | ☐ | Backend endpoint over manifests, then a grid in `web/`. |
| 10 | **CI** — GitHub Actions: ruff + pytest on push; fail the PR on red | ★★ | S | ☐ | Depends on #2. Keeps `main` green. |
| 11 | **Config for docs** — `output.collections: true`, doc theme/accent in `config.yaml` | ★ | S | ☐ | Only if theming demand appears (YAGNI until then). |

---

## Notes on sequencing

- **#2 unblocks everything runnable** — do it first so the pipeline + suite run locally and in CI (#10).
- **#4 (transcript quality) is the biggest correctness win** — the docs are only as trustworthy as the extraction; bad transcripts poison summaries/facts.
- #7–#11 all build cleanly on the manifest layer added in #1 — no rework needed.
