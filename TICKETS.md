# Tickets — Reels Research Platform

Tracking the build of the research platform (spec:
`docs/superpowers/specs/2026-06-18-research-platform-design.md`).
Status: ☐ todo · ◑ in progress · ☑ done

| # | Ticket | Status | Notes |
|---|--------|--------|-------|
| 1 | Design spec | ☑ | committed |
| 2 | Modular restructure + input/output dirs + `core/paths.py` | ☐ | foundation |
| 3 | Promote collection fetcher → `ingest/collection.py` | ☐ | from scripts/ |
| 4 | Scalable pipeline (queue + bounded workers + rate limit) | ☐ | ~100 reels/hr |
| 5 | Knowledge aggregation module | ☐ | group by genre/topic |
| 6 | RAG chat module (Claude CLI) | ☐ | answer + citations |
| 7 | FastAPI backend + `serve` command | ☐ | thin HTTP layer |
| 8 | React + shadcn frontend (`web/`) | ☐ | Catppuccin Mocha |
| 9 | Docker + compose (local, cloud-ready) | ☐ | bind-mount ./data |
| 10 | Replication prompt templates (`prompts/`) | ☐ | rebuild-from-scratch |
| 11 | Docs + TICKETS upkeep + worklog | ◑ | ongoing |
| 12 | Tests (backend + RAG + frontend smoke) | ☐ | pytest + vitest |

## Known issues / follow-ups
- [ ] 12/18 collection reels failed AI vision (`claude CLI failed:` — concurrency/quota throttle at 3 parallel calls). Retry via resume once #4 lands (vision_concurrency=1–2 + backoff).
- [ ] PDF link in docs copied outside repo uses relative `../pdfs/` (cosmetic).
- [ ] `fix/batch-edge-cases` branch not yet merged to main.
