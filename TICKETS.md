# Tickets — Reels Research Platform

Tracking the build of the research platform (spec:
`docs/superpowers/specs/2026-06-18-research-platform-design.md`).
Status: ☐ todo · ◑ in progress · ☑ done

| # | Ticket | Status | Notes |
|---|--------|--------|-------|
| 1 | Design spec | ☑ | committed |
| 2 | Modular restructure + input/output dirs + path helpers | ☑ | additive (kept working pipeline); `Config` knowledge/index/logs dirs |
| 3 | Promote collection fetcher → `ingest/collection.py` | ☑ | `reels-scrap fetch-collection` |
| 4 | Scalable pipeline (vision concurrency + rate limit) | ☑ | `ratelimit.py` + knobs; persistent queue = cloud step (SCALING.md) |
| 5 | Knowledge aggregation module | ☑ | `knowledge/` group-by-genre + cached synthesis |
| 6 | RAG chat module (Claude CLI) | ☑ | `chat/` answer+citations, retrieval fallback |
| 7 | FastAPI backend + `serve` command | ☑ | reels/knowledge/search/chat/media endpoints |
| 8 | React + shadcn frontend (`web/`) | ☑ | Catppuccin Mocha; build + vitest green |
| 9 | Docker + compose (local, cloud-ready) | ☑ | bind-mount ./data + ./output; compose valid |
| 10 | Replication prompt templates (`prompts/`) | ☑ | 10 files, REPLICATE.md master |
| 11 | Docs + TICKETS upkeep + worklog | ☑ | ARCHITECTURE/USAGE/SCALING/DEPLOY reconciled; README + worklog |
| 12 | Tests (backend + RAG + frontend smoke) | ☑ | 9 pytest + 2 vitest passing |

**All 12 tickets done.**

## Verified
- 18/18 collection reels now have AI vision (0 errors) after the
  `vision_concurrency=1` + backoff fix — was 6/18. Knowledge base: 5 topics
  (product 9, educational 6, tutorial 6, news 1) over 23 reels, was 13 uncategorized.
- API + SPA serve single-port; `ask` returns grounded cited answers; builds + tests green.

## Follow-ups
- [ ] Optional per-topic Claude synthesis is off by default (`reels-scrap knowledge --synthesize`).
- [ ] `fix/batch-edge-cases` + `feat/research-platform` branches not yet merged to main.
- [ ] Full persistent/distributed queue (Redis) + SSE chat streaming deferred to cloud phase.

---

## Session 2026-07-02 — topic-research + incremental sync + envs

| # | Ticket | Status | Notes |
|---|--------|--------|-------|
| 13 | Fetch topic-research saved collection → local | ☑ | `reels-scrap collection` (config-fast); 11 video reels ingested, 18 photo-posts have no video stream |
| 14 | Fix Chrome cookie auth (`sessionid`) | ☑ | root cause: lean venv skipped `secretstorage`; encrypted session cookie silently failed to decrypt |
| 15 | Build consolidated HTML doc | ☑ | `output/collections/topic-research.html` (1.8 MB, self-contained) + master index |
| 16 | Serve React frontend + open in Chrome | ☑ | `reels-scrap serve --port 8010` (UI 200 / API 200); doc + index + UI opened in Chrome |
| 17 | Two-track envs: lean `.venv` + full `conda` | ☑ | `environment.yml`; conda `reels-scrap` (py3.12 + ffmpeg) verified; venv gained `secretstorage` |
| 18 | Data-eng incremental source poller | ☑ | `sources.json` registry + `sources.py` + `sync`/`add-source`/`list-sources`; shortcode-keyed dedup over shared pool |
| 19 | Dead-letter ledger for non-video posts | ☑ | photo-only posts no longer re-attempted every run; `sync --retry-failed` clears; state watermark in `output/sources_state.json` |
| 20 | Tests for poller (dedup + dead-letter + retry) | ☑ | `tests/test_sources.py` 3 tests; full suite 20 green |
| 21 | Docs (`docs/SYNC.md`) + worklog | ◑ | SYNC.md written; worklog via `/document` |

| 22 | Deep extraction on phd reels (torch-free) | ☑ | machine has NO GPU → skip torch/OCR; transcript (faster-whisper CPU) + vision (claude-cli). 11/11 summary+genre+facts, 8/11 transcript |
| 25 | DevOps: gate heavy deps behind extras | ☑ | `pyproject` lean core (15) + extras (transcript/ocr/vision/pdf/docs/cpu/full); `scripts/install-extraction.sh` for CPU-torch/OCR later; `environment.yml` → `.[cpu]` |
| 26 | Add 11 saved collections to registry | ☑ | two `ai` lists → `ai`/`ai-2` (slug-collision fix + auto-disambiguate); collision test added |
| 27 | PRIVACY audit + hardening | ☑ | untracked leaked `reels.txt`; gitignore sources.json/reels lists/media; `sources.example.json`; `docs/PRIVACY.md`; egress = claude vision only (air-gap via `vision:false`) |

### Privacy follow-ups
- [ ] Scrub `reels.txt` from git history before any push (still in earlier local commits).
- [ ] Every new external call → document in PRIVACY egress table + gate behind config toggle.
| 23 | Dashboard grouped by category | ☑ | `ReelsPage` groups cards under genre headers + counts; drawer shows summary/facts/transcript/on-screen text |
| 24 | Sources tab (left nav) to add + save URLs | ☑ | `SourcesPage` + `/api/sources` (list/add/toggle) → persists `sources.json`; POST idempotent |

**Idempotency verified:** run 1 `new=18 ingested=0` (photo posts dead-lettered),
run 2 `new=0 deduped=29`. No duplicate reels; only the delta flows each run.

### Session follow-ups
- [ ] 18 photo/carousel posts in the collection aren't videos → skipped by design.
  Add image-post ingestion (yt-dlp `--write-thumbnail` / instaloader) to capture them.
- [ ] Deep extraction (transcript/OCR/vision) not run — use conda env + `config.yaml`.
- [ ] Schedule `reels-scrap sync` (cron / systemd timer) for hands-off latest-reel pulls.
- [ ] Register more saved collections (`front-end` already has a manifest).
