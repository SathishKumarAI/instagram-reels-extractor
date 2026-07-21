# Privacy — local-first, private by default

**Principle:** everything about the user's Instagram — saved collections, reel
content, thumbnails, transcripts, cookies/session — is **private personal data**.
It stays on this machine, is never committed to git, and leaves the box only where
explicitly noted below. Every change to this repo must uphold this flow.

## What is private (and where it lives)

| Data | Location | Protection |
|------|----------|-----------|
| Downloaded reels (video, thumbnail, JSON) | `data/` | gitignored |
| Consolidated docs / site / PDFs | `output/` | gitignored |
| Saved-collection registry (URLs + ids) | `sources.json` | **gitignored** (use `sources.example.json`) |
| Reel URL lists | `reels.txt`, `reels-*.txt` | gitignored |
| Run state / watermark | `output/sources_state.json` | gitignored |
| IG session cookie (`sessionid`) | read from browser at runtime, **in memory only** | never written to repo |
| instaloader session (if used) | `~/.config/instaloader` (outside repo) | never in repo |

`.gitignore` enforces all of the above, plus `*.mp4/*.jpg/*.png/*.webp`, `.env`,
`cookies*.txt`, `*.session`. **Only `sources.example.json` (no personal ids) is
version-controlled.**

## Data egress — the one external call

| Flow | Leaves machine? | Notes |
|------|-----------------|-------|
| Fetch / download (yt-dlp, IG feed) | inbound only | reads your session; no upload |
| Transcript (faster-whisper) | **no** | local CPU |
| Search embeddings (fastembed / ONNX) | **no** | local |
| Doc / dashboard render | **no** | local files + `serve` on 127.0.0.1 |
| **AI vision (`vision_backend=claude-cli`/`api`)** | **YES** | sends sampled **frames** to Claude (Anthropic) for summary/genre/facts |

Vision is the **only** path where reel content leaves the machine. It uses your own
Claude subscription (claude-cli) or API key. If you want a **fully air-gapped run**
(zero egress), set `extract.vision: false` — you keep caption + transcript + search,
lose only the AI summary/genre/facts.

## Rules for future work (uphold this flow)

1. **Never** add `data/`, `output/`, `sources.json`, reel lists, or media to git.
   New personal artifacts → add the pattern to `.gitignore` first.
2. New extractors/features must be **local by default**. Any new external call is an
   egress point → document it in the table above and gate it behind a config toggle.
3. `serve` binds `127.0.0.1` only — do not default-bind `0.0.0.0`.
4. Session/cookies stay in memory or the OS keyring — never persisted in the repo.
5. Ship `*.example.*` templates for anything personal; gitignore the real file.
6. Before any commit/push: `git status` must show **no** `data/`, `output/`,
   `sources.json`, or reel-list files staged.
