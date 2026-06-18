# reels-scrap

**Turn Instagram reels into searchable, professional documents.** Pull reels, extract
their content as structured text, render each as a clean PDF + a linked docs site, and
search the whole archive semantically — all local, no cloud required.

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Local-first](https://img.shields.io/badge/local--first-no%20cloud-orange)

```
ingest ──► extract ──► structure ──► render ──► search
download   transcript   genre +       PDF +      semantic
+ metadata  OCR          provenance    docs site   (local)
            vision       facts
```

## Why it's different

- **Structured, not slop.** Vision returns *typed fields per genre* (a product reel →
  `{name, price, link, claims}`; a tutorial → `{tools, commands, links, steps}`) — not a
  generic paragraph.
- **Provenance on every fact.** Each extracted fact carries the **frame + timestamp** it
  came from. Scrub the reel to that second to verify. Hallucination-resistant by design.
- **No API key needed.** Vision runs through the **Claude Code CLI** (your subscription).
  Anthropic API is an optional backend.
- **Fully local.** Whisper (transcript), easyocr (on-screen text), and fastembed
  (semantic search) all run on-device. Your data never leaves the machine.

## Quickstart

```bash
# 1. install (no sudo — ships a static ffmpeg via pip)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. run the UI
streamlit run app.py          # http://localhost:8501

# …or the CLI
echo "https://www.instagram.com/reel/XXXX/" > reels.txt
reels-scrap run -c config.yaml
reels-scrap search "system design caching"
```

> First transcript/OCR/search run downloads local models (Whisper ~150 MB, easyocr,
> fastembed ~130 MB) — one time. `./setup.sh` is optional (system ffmpeg/tesseract via dnf).

## The UI

`streamlit run app.py` → two tabs:

- **▶️ Extract** — paste reel URLs, toggle extractors, set parallel workers, Run. Live
  progress, per-reel cards, PDF/markdown downloads.
- **🔎 Search archive** — natural-language search over summaries, structured fields,
  transcripts, and individual facts.

## Extraction options (per `config.yaml`)

| Extractor | What | Backend |
|-----------|------|---------|
| `caption` | author, caption, hashtags, stats | metadata (free) |
| `transcript` | spoken audio → text | faster-whisper (local) |
| `ocr` | on-screen text | easyocr (local, confidence-filtered) |
| `vision` | genre + structured fields + provenance facts | Claude CLI *(default)* or API |

Force English to stop multilingual hallucination on music/text reels: `whisper_language: en`.

## Sources

| `source.type` | Needs | Notes |
|---------------|-------|-------|
| `urls`    | `reels.txt` | public via yt-dlp — **default** |
| `urls` + `auth.cookies_from_browser` | logged-in browser | **private reels** you can access |
| `profile` / `hashtag` | `target` | instaloader; large crawls get rate-limited |
| `saved`   | `login: true` + `username` | your saved reels |

**Private reels:** set `auth.cookies_from_browser: chrome` (or firefox/brave). On Linux,
Chrome needs `secretstorage` (bundled) and the browser **closed** when running.

## Outputs

| Path | What |
|------|------|
| `output/markdown/<id>.md` | per-reel markdown (genre, structured fields, provenance table) |
| `output/pdfs/<id>.pdf` | per-reel professional PDF |
| `output/site/index.html` | mkdocs-material site, master index links every reel + PDF |
| `output/search_index.*` | local semantic index |
| `output/run_report.json` | per-reel, per-stage success/error manifest |

Preview the site: `mkdocs serve -f output/site_src/mkdocs.yml`.

## CLI

```bash
reels-scrap run                # full pipeline (ingest → extract → structure → render → index)
reels-scrap fetch-collection U # enumerate a named saved collection → reels.txt (browser cookies)
reels-scrap ingest-cmd         # download only
reels-scrap extract-cmd        # re-run extractors on downloaded reels
reels-scrap render-cmd         # re-render markdown/PDF/site
reels-scrap index              # rebuild semantic index
reels-scrap knowledge          # rebuild the aggregated Knowledge Base
reels-scrap search "q"         # semantic query
reels-scrap ask "question"     # RAG research answer with citations (CLI)
reels-scrap serve              # launch the React research UI + API (http://127.0.0.1:8000)
reels-scrap login USER         # create a local Instagram session (instaloader)
```

## Research platform (React + FastAPI)

Beyond the static docs, `reels-scrap serve` runs a modern **research UI**
(Vite + React + shadcn-style, Catppuccin Mocha) over a FastAPI backend:

- **Knowledge Base** — the corpus aggregated into topics (by genre), each with key
  facts (provenance-linked) and source reels. Optional Claude topic overviews
  (`reels-scrap knowledge --synthesize`).
- **Reels** — filterable grid → detail drawer (video, facts table with timestamps,
  transcript, on-screen text, caption, PDF).
- **Research Chat** — ask questions across the archive; answers are synthesised by
  Claude (CLI, your subscription) and **cite the reels they came from**. Falls back to
  raw sources if synthesis is unavailable.

```bash
cd web && npm install && npm run build   # build the UI once
reels-scrap serve                        # serves API + UI on one port
# dev mode: `npm run dev` (Vite :5173, proxies /api to :8000) + `reels-scrap serve`
```

Architecture, scaling (~100 reels/hr), and Docker deploy are documented in
`docs/ARCHITECTURE.md`, `docs/SCALING.md`, `docs/DEPLOY.md`. Rebuild-from-scratch
prompt templates live in `prompts/`.

## Docker

```bash
docker compose -f docker/docker-compose.yml up --build   # API+UI on :8000
```
`./data` (inputs) and `./output` (derived) are bind-mounted so everything stays local.
Claude CLI auth is mounted from the host; for cloud, switch `vision_backend: api` +
`ANTHROPIC_API_KEY` (see `docs/DEPLOY.md`).

## Batch + performance

Built for batches of short clips. `batch.workers` (default 3) processes several reels
concurrently through extract + render, with thread-safe model loading. Ingest stays
sequential on purpose — parallel Instagram requests trigger rate-limits.

> 20 clips, vision ~60 s each: ~20 min sequential → **~7 min at 3 workers**. Vision uses
> your Claude quota (1 call/reel); watch it for large batches.

## ⚠️ Legal

Automated scraping violates Instagram's ToS. Logged-in scraping risks account bans and
rate limits. The default is public-only and your own content; passwords never touch the
code (session/cookie files only). Respect rate limits and content owners' rights. **You
are responsible for how you use this.**
