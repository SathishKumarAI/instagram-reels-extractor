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
