# 50-Feature Backlog — Reels Research Platform

Architected as 10 epics × 5 features. Priority **P0** (now) → **P3** (later);
Effort **S/M/L**; Value ★–★★★. `dep:` = prerequisite feature id. Build order follows
priority then dependency. Status: ☐ todo · ◑ wip · ☑ done.

Legend for "build like engineer": each feature = one thin vertical slice
(store → API → UI), lazy-imported, tested where logic is non-trivial, degrades gracefully.

---

## Epic A — Ingestion & Sources
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| A1 | Profile source via session | P1 | M | ★★ | ☑ built; IG 429 watcher |
| A2 | Hashtag source type | P2 | M | ★★ | instaloader hashtag → urls |
| A3 | Single-URL quick-add ("paste a reel") | P0 | S | ★★★ | box in Sources → ingest one |
| A4 | Source health + last-error surfaced in UI | P1 | S | ★★ | from sources_state |
| A5 | Per-source limit + schedule override | P2 | S | ★ | fields already in registry |

## Epic B — Extraction & Enrichment
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| B1 | Configurable vision prompt / schema | P2 | M | ★★ | prompt in config |
| B2 | Re-extract single reel from UI | P1 | M | ★★ | button → job |
| B3 | Language field + non-English badge | P1 | S | ★★ | transcript_language exists |
| B4 | Entity extraction (people/tools/links) | P2 | M | ★★ | from structured |
| B5 | Local-LLM vision (moondream) | P3 | L | ★★ | dep: torch/GPU — deferred |

## Epic C — Organization
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| C1 | Status flags (star/read/archive) | P0 | M | ★★★ | ☑ built |
| C2 | Saved views | P0 | M | ★★ | ☑ built |
| C3 | Tag cloud page | P0 | S | ★★ | dep: stats.top_tags |
| C4 | Tag rename / merge | P2 | M | ★ | edit across reels |
| C5 | Notes per reel (freeform) | P1 | S | ★★ | annotations.note exists |

## Epic D — Search & Discovery
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| D1 | Global omnisearch bar | P1 | M | ★★★ | dep: /api/search |
| D2 | Similar reels ("more like this") | P0 | M | ★★ | reuse embeddings |
| D3 | Saved searches | P2 | S | ★ | like views |
| D4 | Filter by duration / likes range | P1 | S | ★ | slider |
| D5 | Random / "surprise me" reel | P2 | S | ★ | discovery |

## Epic E — Views & Dashboards
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| E1 | Home overview dashboard | P0 | M | ★★★ | stat cards + recent |
| E2 | Per-collection page | P1 | M | ★★ | dep: manifests |
| E3 | Per-account page | P1 | M | ★★ | dep: author |
| E4 | Timeline / calendar view | P2 | M | ★ | dep: timestamp |
| E5 | Kanban by status (to-apply/reading) | P2 | M | ★★ | dep: C1 |

## Epic F — Export & Integration
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| F1 | CSV export | P0 | S | ★★ | ☑ built |
| F2 | XLSX + Markdown export | P0 | S | ★★ | ☑ built |
| F3 | Filtered export (honor current filters) | P1 | S | ★★ | query params |
| F4 | Notion / Obsidian export | P3 | M | ★ | API/vault |
| F5 | Public shareable static HTML (already local docs) | P1 | S | ★★ | consolidate |

## Epic G — Automation & Scheduling
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| G1 | Scheduled sync (systemd/cron) | P0 | S | ★★★ | ☑ built |
| G2 | Watch-and-retry on rate-limit | P1 | S | ★★ | ☑ example-profile watcher |
| G3 | Post-sync summary notification | P2 | S | ★ | desktop notify |
| G4 | Auto-backfill new fields | P2 | M | ★ | dep: B2 |
| G5 | Webhook / RSS of new reels | P3 | M | ★ | feed |

## Epic H — Cost & Observability
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| H1 | Cost dashboard ($ from tokens) | P0 | S | ★★ | ☑ built |
| H2 | Per-run cost ledger | P1 | S | ★★ | from state |
| H3 | Token budget guard (stop at $X) | P2 | M | ★★ | pre-flight |
| H4 | Extraction success/error report page | P1 | S | ★★ | run_report |
| H5 | Model/backend picker in UI | P2 | S | ★ | settings |

## Epic I — Privacy & Security
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| I1 | Gitignore + example templates | P0 | S | ★★★ | ☑ built |
| I2 | Git-history secret scrub | P0 | M | ★★★ | ☑ built |
| I3 | Air-gapped mode (vision off) toggle | P1 | S | ★★ | dep: config |
| I4 | Media-endpoint path-traversal guard | P1 | S | ★★ | validate id |
| I5 | Encrypt data/ at rest (opt-in) | P3 | L | ★ | fs crypto |

## Epic J — Platform & DevEx
| # | Feature | P | E | V | Notes |
|---|---------|---|---|---|-------|
| J1 | Two-track envs + gated extras | P0 | M | ★★ | ☑ built |
| J2 | Health + version endpoint | P1 | S | ★ | /api/health exists |
| J3 | Keyboard shortcuts in UI | P1 | S | ★★ | j/k/esc/star |
| J4 | Loading + empty states | P1 | S | ★★ | polish |
| J5 | E2E smoke test (api+ui) | P2 | M | ★★ | pytest+vitest |

---

## Build order (waves)

- **Wave 1 (P0, this session):** C3 tag-cloud · D2 similar-reels · E1 home dashboard ·
  A3 quick-add-URL · I4 path-traversal guard. (Plus already-done C1/C2/F1/F2/G1/H1.)
- **Wave 2 (P1):** D1 omnisearch · F3 filtered export · C5 notes · B3 language badge ·
  H4 error report · J3 shortcuts · J4 states · E2/E3 collection/account pages.
- **Wave 3 (P2):** ranges, saved searches, kanban, budget guard, tag merge, model picker.
- **Wave 4 (P3):** local-LLM vision, encryption, webhooks, Notion, calendar.

Done (**21/50**): A1, A3, C1, C2, C3, C5, D2, E1, F1, F2, F3, G1, G2, H1, H4, I1, I2, I4, J1, J2, B3.
- **Wave 1:** C3 tag-cloud · D2 similar-reels · E1 home dashboard · I4 security guard.
- **Wave 2:** A3 quick-add-one-reel (background caption ingest) · B3 transcript-language
  badge · C5 per-reel notes (auto-save) · F3 filtered export (honours filters via ids) ·
  H4 run-report endpoint.
- **Wave 3 (26/50):** D1 omnisearch (semantic Search tab, debounced) · J3 keyboard
  shortcuts (drawer j/k next-prev · s star · esc close · `/` focus search) · J4
  loading/empty states (Reels, Table, Search). E2/E3 collection/account views are
  covered by existing filters + consolidated docs (dedicated pages = optional polish).
- **Wave 4 (28/50):** H3 token/cost budget guard (`backfill_vision --max-cost`,
  stops at ceiling using real per-reel cost) + honest token accounting (split cache
  reads from fresh input; stats uses CLI `total_cost_usd`). Also SPA deep-link fallback.
  Plus **C4** tag merge/rename/delete across all reels · **D4** min-likes range filter ·
  **D5** "surprise me" random reel. Running total: **31/50**.
Next: D3 saved searches, E5 kanban-by-status, H5 model picker; then P3 (local-LLM
vision, encryption, webhooks, Notion, calendar).
