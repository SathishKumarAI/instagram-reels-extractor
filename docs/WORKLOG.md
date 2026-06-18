# Worklog

## 2026-06-18 13:26 — Multi-reel batch validation + 2 edge-case fixes

**Summary:** Ran the first true multi-reel batch (4 URLs, 3 workers), validating
the parallel path live. Found and fixed two real edge-case bugs; re-ran to
confirm. Committed on branch `fix/batch-edge-cases`.

**Changes:**
- `extract/frames.py` — new `has_audio_stream()` probe (ffmpeg `-i` → look for
  `Audio:` in stderr)
- `extract/transcript.py` — skip transcript cleanly on video-only reels instead
  of crashing
- `ingest/__init__.py`, `ingest/ytdlp.py`, `ingest/instaloader_src.py` — thread
  optional `failures` dict; route ingest errors through `log.error`
- `pipeline.py` — record dropped URLs in `run_report.json` as ingest errors
- `reels.txt` — 4 test URLs (1 control + 3 fresh public reels)
- `output/validation_results.md` — full validation report (untracked artifact)

**Bugs fixed (found via batch run):**
1. No-audio/video-only reel crashed transcript — ffmpeg `-vn` exits 234 →
   CalledProcessError. Now probed and skipped clean (like the no-speech path).
2. Failed/login-gated URL dropped silently — caught with `print()`+`continue`,
   no report/log entry. Now logged + recorded as `ingest: error` with reason.

**Verification:** 4-URL batch report went `total 3 → 4`; video-only
`DXZgeTJDDLD` processes fully (genre=news); login-gated `DZQq3aaEfzF` recorded
with "empty media response / use cookies" reason. 3 markdown + 3 PDFs + docs
site + 26-vector search index produced.

**Follow-ups:**
- [ ] Open PR / merge `fix/batch-edge-cases` into `main`
- [ ] Private-reel batch via `auth.cookies_from_browser` (would recover the
      login-gated URL)
- [ ] Earlier follow-ups still open: scene-aware frame sampling, knowledge-graph
      auto-linking, watch/daemon mode, test suite

## 2026-06-16 20:35 — Publish + polish; checkpoint for continuation

**Summary:** Pushed to GitHub (public), rewrote README, added MIT license, and
saved a resume memory. App left running on :8501.

**Changes:**
- GitHub: `SathishKumarAI/insta_reels_scrap` created, pushed, made **public**
- `README.md` — full rewrite: leads with structured-extraction/provenance/
  local-first value; documents UI, semantic search, cookie auth, batch perf
- `LICENSE` (MIT) + `license` metadata in `pyproject.toml`

**Resume here next session:**
- [ ] **Run a real multi-reel batch** — parallel path proven (4×1s→2s) but only
  run on 1 real URL (`DZJv2DUzGPQ`). Need 3-5 reel URLs from user.
- [ ] Then pick up earlier follow-ups (scene-aware sampling, knowledge-graph
  links, watch/daemon, tests) listed in the entry below.
- [ ] Remove synthetic `DEMO123` artifacts from `data/`/`output/` (rm is
  deny-listed — confirm first).
- Streamlit may still be running on http://localhost:8501.

---

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
