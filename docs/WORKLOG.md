# Worklog

## 2026-06-16 20:20 — Build reels→text→PDF→docs pipeline (greenfield)

**Summary:** Built `reels-scrap` end-to-end from an empty repo: an Instagram-reel
ETL that extracts caption/transcript/OCR/structured-vision per clip, renders a
professional PDF + linked mkdocs-material site, and exposes a Streamlit UI + CLI.
Verified live on a real private reel.

**Changes:**
- `src/reels_scrap/ingest/` — yt-dlp (public + browser-cookie auth for private),
  instaloader (profile/hashtag/saved); idempotent resume, rate-limit backoff
- `src/reels_scrap/extract/` — faster-whisper transcript (forced-lang
  anti-hallucination), easyocr (confidence-filtered), **structured Claude vision
  with provenance** (genre → typed fields + facts tied to frame/timestamp)
- `src/reels_scrap/render/` — weasyprint PDF (Catppuccin CSS) + mkdocs-material
  site with master index
- `src/reels_scrap/pipeline.py` — shared orchestration, bounded-parallel batch
  (thread-safe model loading), per-run JSON manifest + structured logging
- `src/reels_scrap/search.py` — local semantic search (fastembed ONNX) over
  reels + facts; CLI `index`/`search` + UI Search tab
- `app.py` — Streamlit UI (Extract + Search tabs); `cli.py` — typer CLI
- `config.py` — fail-fast pydantic validation for every section

**Decisions:**
- **Vision via Claude Code CLI** (`claude -p`, subscription) as default backend —
  no API key; Anthropic API optional. Subscription quota is the cost lever.
- **Structured extraction + provenance over prose** — anti-slop: output is typed
  data, every fact cites the frame/timestamp it came from.
- **Local-first** — Whisper, easyocr, fastembed all run on-device; static ffmpeg
  via pip (`imageio-ffmpeg`) so no sudo needed; `secretstorage` for Chrome cookies.
- **Public-default, login opt-in** — yt-dlp public path is default; private uses
  browser cookies; passwords never touch code (session/cookie files only).
- Skipped: cloud/Vercel (local heavy deps), prose summaries, generic chatbot.

**Follow-ups:**
- [ ] Scene-aware frame sampling (`select='gt(scene,0.4)'`) — fewer, sharper frames
- [ ] Knowledge-graph auto-linking between reels sharing entities
- [ ] Watch/daemon mode to auto-ingest new saved reels on a schedule
- [ ] Test suite (config validators, URL validation, render fixtures)
- [ ] Multi-reel batch live test (parallel path proven, not yet run on >1 real reel)
- [ ] Remove synthetic `DEMO123` artifacts from `data/`/`output/`
