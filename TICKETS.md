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
| 11 | Docs + TICKETS upkeep + worklog | ◑ | ARCHITECTURE/USAGE/SCALING/DEPLOY done; reconciling "Planned" tags |
| 12 | Tests (backend + RAG + frontend smoke) | ◑ | pytest (api/rag/knowledge) + vitest |

## Known issues / follow-ups
- [ ] Recover the 12 collection reels that failed AI vision — re-running now with
      `vision_concurrency=1` + backoff (ticket #4 fix). Verifying.
- [ ] Reconcile docs that mark serve/fetch-collection/knowledge/chat/api/web as
      "Planned" — they are now built.
- [ ] Optional per-topic Claude synthesis is off by default (`--synthesize`).
- [ ] `fix/batch-edge-cases` branch not yet merged to main.
- [ ] Full persistent/distributed queue (Redis) deferred to cloud phase.
