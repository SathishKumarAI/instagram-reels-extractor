# PRD — Reels Research Platform

**One line:** turn your private Instagram saved collections (and public accounts)
into a local, searchable, categorized knowledge base — captions, transcripts,
AI summaries, tags, key facts with provenance — that you own.

**Status:** MVP shipped + in active use. This doc is the source of truth for scope,
priorities, and what's done vs next.

---

## 1. Problem

People save hundreds of reels (jobs, PhD, AI, tutorials, ideas) they never revisit.
Instagram gives no search, no text, no structure, no export — the knowledge is
trapped in a scroll feed. Existing scrapers dump media; none extract *meaning*.

## 2. Users

| Persona | Need |
|---------|------|
| **Primary — the archivist (you)** | one place to search + categorize everything saved, locally, privately |
| Researcher | pull a topic (e.g. "PhD interview tips") across collections with citations |
| Job-seeker | filter jobs/internships reels, export to a sheet, track to-apply |

## 3. Goals / non-goals

**Goals:** local-first & private · text from every reel (caption + transcript + AI
vision) · category + tag + account organization · search + Q&A · export · cheap/fast
extraction · usable dashboard.

**Non-goals:** cloud SaaS, multi-tenant, reposting/publishing, growth/analytics for
*your* account, anything that violates IG ToS at scale.

## 4. Principles

1. **Private by default** — data never leaves the machine except the one documented
   egress (AI vision → Claude). `vision:false` = fully air-gapped. See `PRIVACY.md`.
2. **Local-first** — runs offline; `serve` binds 127.0.0.1.
3. **Incremental & idempotent** — every sync pulls only new reels, no duplicates.
4. **Degrade gracefully** — a missing extra disables one feature, never the core.

## 5. Features

### Shipped ✅
| Area | Feature |
|------|---------|
| Ingest | saved-collection fetch (session cookies) · incremental `sync` · dedup by shortcode · dead-letter for non-video |
| Sources | `sources.json` registry · **Sources tab** (add/enable/disable URLs) · profile + urls + collection types |
| Extract | caption · transcript (whisper CPU, no torch) · **AI vision** (genre/summary/facts) · **tags** · **token metering** |
| Organize | category grouping · **tags** (clickable) · **account/author filter** · **sort** (likes/comments/tokens/duration/title) |
| Views | Reels (cards, grouped) · **Table (Excel-style, sortable) + CSV export** · Knowledge (topics) · Research (RAG chat) |
| Cost/speed | claude-only fast mode · frame cache · configurable `max_frames` · API-backend parallel path |
| Ops | two-track envs (venv/conda) · gated extras · privacy hardening · git-history scrub |

### Roadmap 🔜 (prioritized value ÷ effort)
| P | Feature | Why |
|---|---------|-----|
| P0 | **Backfill tags/tokens** on full archive | current gap; one re-vision pass |
| P0 | **Cost dashboard** ($ from tokens, per-collection/run spend) | `total_cost_usd` already in claude envelope |
| P1 | **Account/profile facet everywhere** — source + author as first-class filters; per-account tab | this session's ask; group by where a reel came from |
| P1 | **Scheduled sync** (cron/systemd) | incremental + dead-letter make it safe to automate |
| P1 | **Global omnisearch** (semantic + tag + text) in top bar | `/api/search` exists |
| P2 | **Saved views / smart collections** (jobs+internships, AI-this-month) | cross-collection filters |
| P2 | **Status flags** (read/starred/to-apply/archived) | turns archive into a workflow |
| P2 | **Export** Markdown/Notion/xlsx (beyond CSV) | reuse render layer |
| P3 | **Local-LLM vision** (LLaVA/moondream) | closes the one egress point |
| P3 | **Near-duplicate detection** across collections | perceptual/caption similarity |

## 6. Architecture (one glance)

`ingest → extract (caption/transcript/vision) → structure → render (docs) + index
(embeddings) → API (FastAPI) → UI (React)`. Flat `data/` pool keyed by reel
shortcode; per-source membership manifests; state watermark in `sources_state.json`.
Full detail in `ARCHITECTURE.md`.

## 7. Metrics (how we know it's working)

- Coverage: % reels with summary / genre / tags / transcript.
- Freshness: reels added per sync; time since last sync per source.
- Cost: tokens + $ per reel / per collection / per run.
- Usefulness: searches run, RAG questions answered, CSV exports.

## 8. Risks

| Risk | Mitigation |
|------|-----------|
| IG rate-limits / blocks (esp. profiles) | incremental + backoff + dead-letter; prefer own saved lists; feed URLs |
| ToS (scraping others' profiles) | opt-in, disabled by default, documented |
| Vision cost/latency (claude-cli) | claude-only mode, frame cap, API-parallel path, haiku option |
| Privacy leak to git | gitignore + example templates + history scrub + pre-push check |

## 9. Milestones

- **M0 (done)** — ingest→extract→docs→search→API→UI, 11 collections, tags+tokens.
- **M1** — full-archive backfill + cost dashboard + account facet + scheduled sync.
- **M2** — saved views + status flags + richer export.
- **M3** — local-LLM vision (fully air-gapped) + dedup.
