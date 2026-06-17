# reels-scrap

Instagram reels → text → PDF → professional docs site.

Pulls reels, extracts **caption + metadata**, **spoken audio transcript** (Whisper),
**on-screen text** (OCR), and an **AI visual summary** (Claude vision), then renders
each reel as a clean **PDF** and a linked **mkdocs-material** site with a master index.

All sources, extractors, and outputs are toggles in `config.yaml` — turn on what you need.

## Setup

```bash
./setup.sh                       # ffmpeg + native deps + venv + pip install -e .
source .venv/bin/activate
cp .env.example .env             # only if using vision; set ANTHROPIC_API_KEY
```

> ffmpeg and (optional) tesseract are required; `setup.sh` installs them via dnf.
> First transcript/OCR run downloads Whisper/easyocr models (large).

## Use

1. Put reel URLs in `reels.txt` (one per line).
2. Edit `config.yaml` toggles.
3. Run:

```bash
reels-scrap run -c config.yaml
```

Outputs:

| Path | What |
|------|------|
| `output/markdown/<id>.md` | per-reel markdown |
| `output/pdfs/<id>.pdf`    | per-reel professional PDF |
| `output/all_reels.pdf`    | combined PDF (if `combined_pdf: true`) |
| `output/site/index.html`  | docs site, master index links every reel + PDF |

Preview the site live:

```bash
mkdocs serve -f output/site_src/mkdocs.yml
```

## Stage subcommands (reruns)

```bash
reels-scrap ingest-cmd    # download only
reels-scrap extract-cmd   # re-run transcript/ocr/vision on downloaded reels
reels-scrap render-cmd    # re-render markdown/PDF/site
```

## Sources

| `source.type` | Needs | Notes |
|---------------|-------|-------|
| `urls`    | `reels.txt` | public, no login (yt-dlp) — **default** |
| `profile` | `target` handle | instaloader; large crawls get rate-limited |
| `hashtag` | `target` tag | instaloader |
| `saved`   | `login: true` + `username` | your saved reels |

## ⚠️ Legal

Automated scraping violates Instagram's ToS. Logged-in scraping risks bans and
rate limits. Default is public-only + your own content. Respect rate limits and
the rights of content owners. You are responsible for how you use this.
