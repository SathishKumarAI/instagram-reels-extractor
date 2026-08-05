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

Since 2026-08-04 there is a **fully local vision path**: Ollama on your own GPU
(`config-local.yaml`, `vision_backend: local`, `vision_local_fallback: false`).
That closes the one egress point above while keeping summaries — frames go to a
model running on your machine. See `docs/LOCAL-VISION.md`.

## The cookie file — read this before copying this setup

On Linux, cookies are read live from the browser and stay in memory. **On Windows
that is impossible**: Chrome 127+ encrypts cookies app-bound and yt-dlp cannot
decrypt them (yt-dlp #10927). The only working path is an exported
`cookies.txt` in the repo root.

That file contains your `sessionid`. Treat it exactly like your password:

- It is a **live login**. Anyone holding it is logged into your Instagram until you log out.
- It is gitignored (`cookies*.txt`, `cookies*.bak`, `*.bak`) and blocked by the pre-commit hook.
- **Never** paste it into a chat, an issue, a screenshot, a log, or a bug report.
- Rotate it by logging out of Instagram — that invalidates every copy at once.
- Re-export when sync suddenly fails on every source; that is expiry, not a bug.

## Guard rails (enabled per clone)

```bash
git config core.hooksPath .githooks    # one time, per clone
```

`.githooks/pre-commit` refuses a commit that contains:
credential filenames (`cookies.txt`, `sources.json`, `.env`, `*.session.json`),
a credential-shaped value in the diff (IG `sessionid`, `sk-ant-…` API key),
or reel media / `data/` / `output/` files — including via `git add -f`.

Verified 2026-08-04: `git log --all -- cookies* .env *.session*` is empty. No
credential has ever been committed to this repo.

## Before making the repo public

1. `git log --all -- "cookies*" ".env" "*.session*"` → must be empty.
2. `git grep -nE "[0-9]{6,}%3A[A-Za-z0-9_-]{10,}"` → must be empty (sessionid shape).
3. `git ls-files | grep -iE "cookie|session|secret|token|credential"` → only `.env.example`.
4. Collection names: `sources.json` is gitignored, and the tracked docs use
   neutral stand-ins (`topic-research`, `topic-jobs`, …). Real names can reveal
   health conditions or a job search — keep them out of docs, commit messages
   and screenshots. `scripts/scrub-personal.py` re-runs the substitution.
5. Screenshots: crop or blur the browser URL bar and any logged-in Instagram tab.

## Rules for future work (uphold this flow)

1. **Never** add `data/`, `output/`, `sources.json`, reel lists, or media to git.
   New personal artifacts → add the pattern to `.gitignore` **in the same edit**
   that creates them. A backup or export of a secret is still a secret.
2. New extractors/features must be **local by default**. Any new external call is an
   egress point → document it in the table above and gate it behind a config toggle.
3. `serve` binds `127.0.0.1` only — do not default-bind `0.0.0.0`. There is no
   auth on the API; binding it to a LAN address exposes the whole corpus.
4. Session/cookies stay in memory, the OS keyring, or a gitignored `cookies.txt`
   — never in a tracked file, never in a log line, never in an error message.
5. Ship `*.example.*` templates for anything personal; gitignore the real file.
6. Before any commit/push: `git status` must show **no** `data/`, `output/`,
   `sources.json`, or reel-list files staged. The hook enforces this, but check.
