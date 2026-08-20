# Project Status & Backlog — reels-scrap

**Snapshot: 2026-07-11.** Feed for the local Kanban. Status legend:
✅ done · 🔨 in progress · 📋 backlog · ⛔ blocked (needs you).

**At a glance:** 184 reels archived · 182 fully extracted (2 = demo fixture + a
video-less carousel) · search index 1,470 vectors · 3 vision backends · 10 UI
pages · 16 CLI commands · 25 API routes. Default extraction = **Claude-code-only**;
optional **strictly-local** vision on your own GPU box.

---

## ✅ Done — working now

### Pipeline: ingest → extract → structure → render → search
| Feature | Notes |
|---------|-------|
| **Ingest** — yt-dlp download + metadata | public path default; private via cookies |
| **Auth** — browser cookies **and** exported `cookies.txt` | listing uses browser; download uses file (avoids Chrome DB lock) |
| **Collection listing** — saved-collection pagination | GraphQL, sessionid from browser |
| **Incremental `sync`** — dedup by shortcode + dead-letter ledger | idempotent; `--retry-failed` re-attempts |
| **Text sources** — RSS/Atom · arXiv · GitHub releases | no yt-dlp, no vision; text → same schema via `text_summary`; `sources.json type: rss\|arxiv\|github` or the Sources-page picker |
| **Extract: caption** | hashtags, mentions, stats from metadata (free) |
| **Extract: transcript** — faster-whisper (CPU) | auto-detect + translate; **off by default** (claude-only), code intact |
| **Extract: OCR** — easyocr | torch-gated extra; **off by default**, code intact |
| **Extract: vision** — genre, summary, tags, structured fields, **facts w/ frame+timestamp provenance**, tokens | the core "anti-slop" typed output |
| **Structure** — per-reel markdown | typed fields per genre |
| **Render** — PDF, mkdocs site, **consolidated local HTML** per collection | |
| **Search** — fastembed semantic index over reels + facts + "similar" | local, on-device |
| **Knowledge** — aggregated topics (+ optional synthesis) | `/api/knowledge` |

### Vision backends (selectable — this is the big one)
| Backend | Runs on | Egress | Status |
|---------|---------|--------|--------|
| `claude-cli` | Claude Code CLI (subscription) | to Claude | ✅ default |
| `api` | Anthropic SDK (`ANTHROPIC_API_KEY`) | to Claude | ✅ |
| `local` | **your GPU box**, OpenAI-compatible (vLLM/Ollama), Kimi-VL | **none (LAN only)** | ✅ built, ⛔ box not wired yet |

- Same JSON schema for every reel regardless of backend (`_apply` shared).
- **Provenance**: each reel records `tokens.backend` + `tokens.model`, shown as a
  **badge** on Reels cards + Reader (Claude / Claude API / Local / Local→Claude).
- **Strict local**: `vision_local_fallback: false` in `config-local.yaml` — failed
  reels dead-letter, **never** egress to Claude.
- Select 3 ways: config (`-c config-local.yaml`) · CLI (`sync --backend local`) ·
  **UI toggle** (Sources → SyncPanel).

### Web UI (10 pages, http://localhost:8010)
| Page | What |
|------|------|
| Home | overview |
| **Reels** | card grid — bigger cards, hover-scale, filters: search/genre/account/**collection**/status/**date**, sorts incl **newest/oldest**, saved views, CSV/XLSX/MD export, drawer detail |
| **Reader** ✨ | text-only "thesis" view — sortable left index (heading+subheading), right long-form paper (abstract/key-points/details/transcript/caption/links), no video |
| Search | semantic search UI |
| Table | tabular view |
| Board | Kanban view |
| Tags | tag cloud / per-tag reels |
| Knowledge | aggregated topics |
| **Sources** | add/toggle sources + **Sync-now panel with backend toggle** |
| Research | RAG chat over the corpus |
| — nav | sidebar + **Back bar on every page** (→ Home fallback) |

### Ops / config
- Config presets: `config.yaml` (claude-only default), `config-claude.yaml`,
  `config-deep.yaml` (+transcript), **`config-local.yaml`** (strict local GPU).
- Privacy: all data local; `cookies.txt` + `*.cookies` gitignored; sole egress =
  chosen cloud vision backend (zero when `local`).
- No-GPU friendly: torch-free default path; heavy deps gated behind extras.
- Tests: 26 passing incl. new `test_vision_local.py` (mock + real-HTTP smoke).

---

## 🔨 In progress
| Item | State |
|------|-------|
| **Cookie-gated re-sync** | ⛔ waiting on you to export `cookies.txt`; watcher auto-syncs when it lands |
| **Local GPU backend live test** | built + smoke-tested vs stand-in; ⛔ needs your GPU box `base_url` to run for real |
| Reader view polish | shipped; awaiting your feedback on section order / left-index density |

---

## 📋 Backlog — future (value ÷ effort)
| Feature | Value | Effort | Why |
|---------|-------|--------|-----|
| **Scheduled sync** — cron/systemd nightly `sync` | ★★★ | S | incremental + dead-letter make it safe |
| **Cost dashboard UI** — $/collection, $/run | ★★★ | S | tokens already metered |
| **Sync more collections** — topic-books, ai, ideas, jobs… | ★★★ | S | only 3 of 12 sources synced so far |
| **Near-duplicate dedup** across collections | ★★☆ | M | shortcode dedup is exact-only |
| **Scene-aware frame sampling** | ★★☆ | M | fewer, sharper frames → cheaper/better vision |
| **Knowledge-graph linking** between reels sharing entities | ★★☆ | L | richer navigation |
| **Watch/daemon mode** — auto-ingest new saved reels | ★★☆ | M | hands-off |
| **UI backend health check** — ping local endpoint before sync | ★★☆ | S | fail fast if GPU box down |
| **Parallel local vision** — raise concurrency on GPU box | ★★☆ | S | GPU handles parallel unlike claude-cli |
| **Remove `DEMO123` fixtures** from data/output | ★☆☆ | S | cleanup |
| **Expand test suite** — render fixtures, sync/dedup, API | ★★☆ | M | reliability |

---

## ⛔ Blocked on you
1. **Export `cookies.txt`** → repo root → watcher auto-syncs (fresh reels).
2. **GPU box `base_url`** → set in `config-local.yaml` → real local-vision run.
