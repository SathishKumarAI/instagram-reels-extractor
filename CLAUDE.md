# CLAUDE.md — reels-scrap

Instagram saved reels → structured records (caption / frames / vision) → search,
docs, and a local research UI. Everything runs on this machine.

## Read first
- `STATUS.md` — where work stopped and what is next. Update it when you stop.
- `docs/PLAN-2026-08.md` — current requirements and phasing.
- `docs/BACKLOG-120.md` — the feature list.
- `docs/PRIVACY.md` — what must never leave the machine or enter git.

## Security — non-negotiable
- `cookies.txt` is a **live Instagram login**. Never print it, log it, paste it into
  a message, or include it in a diff. Same for `sessionid` values and API keys.
- Personal data (`data/`, `output/`, `sources.json`, `reels*.txt`, media) is
  gitignored. When you create a new personal artifact, add its ignore pattern in
  the same edit — a backup or export of a secret is still a secret.
- `.githooks/pre-commit` blocks credentials and media. Enable per clone:
  `git config core.hooksPath .githooks`.
- The API has no auth. It binds `127.0.0.1`; never change that default.

## This machine (Windows)
- Use `.venv-win`, not `.venv` (that one is a Linux venv from the old box).
- Prefix commands with `PYTHONUTF8=1` — several file reads still lack an explicit
  encoding and Windows defaults to cp1252, which cannot read our own JSON back.
- Put `.venv-win/Scripts` on PATH when a run shells out to `mkdocs` or `ffmpeg`.
- Chrome cookie extraction does **not** work here (app-bound encryption). Always
  pass `--browser cookies.txt`, or use `config-local.yaml`, which sets it.

## Commands
```bash
# sync everything, Claude vision
PYTHONUTF8=1 .venv-win/Scripts/python.exe -m reels_scrap.cli sync -c config.yaml --browser cookies.txt

# sync everything, local GPU vision (free, ~5s/reel)
PYTHONUTF8=1 .venv-win/Scripts/python.exe -m reels_scrap.cli sync -c config-local.yaml

# one source only
... sync -c config-local.yaml --only saved-all

# repair pass: reels whose vision failed (sync will never revisit them — they are
# downloaded, so they are no longer "new", and --retry-failed only redoes ingest)
... -m reels_scrap.cli extract-cmd -c config-local.yaml --missing-vision

# API (127.0.0.1:8000) and web dev server (localhost:5173, proxies /api)
... -m reels_scrap.cli serve -c config.yaml --port 8000
cd web && npm run dev

# checks
PYTHONUTF8=1 .venv-win/Scripts/python.exe -m pytest tests -q -p no:warnings
cd web && npx tsc -b
```

## Local vision
`scripts/ollama-vision.Modelfile` builds `reels-vision` (qwen2.5vl 7B q8, 32k ctx)
because the stock model's 4096 context rejects the frames we send. Rebuild after
editing it: `ollama create reels-vision -f scripts/ollama-vision.Modelfile`.
`LOCAL_NUDGE` in `extract/prompts.py` applies only to the local backend — a 7B reads
"3-8 facts" as "3". Do not add it to the Claude prompt.

## Where to look

| Question | File |
|---|---|
| What is the model **told** — schema, nudges, caption/transcript assembly | `extract/prompts.py` |
| How its answer is **read** — JSON salvage, tags, fact hygiene | `extract/normalise.py` |
| Which backend runs, retries, GPU bail-out, provenance | `extract/vision.py` |
| An HTTP endpoint | `api/routes/<group>.py` — table in `api/README.md` |
| Why a measurement says what it says | `docs/research/` |

Every directory with more than ~4 source files carries a `README.md` whose first
section is a change → file table. Read that instead of the code.

**The GPU is shared with your other repos.** Never start a local-vision run onto a
busy card: ollama silently offloads layers to CPU and every reel then dies on the
240s read timeout. `modelreg.gpu_blockers()` refuses to start (foreign model
resident / free VRAM under `vram_gb` + 2GB / util ≥50%), and a failed call re-reads
`ollama ps` — anything but `100% GPU` raises `GpuContended` and ends the run rather
than retrying. `REELS_IGNORE_GPU=1` overrides both. Check with `ollama ps` and
`nvidia-smi`; do not stop someone else's model to make room.

## Conventions
- Heavy imports stay inside functions; a missing optional dep degrades one feature,
  never the run. PDF and docs-site stages are best-effort — follow that pattern.
- Non-trivial logic ships with one runnable check in `tests/`.
- Sync is idempotent and incremental. Anything that fails goes to the dead-letter
  with a reason; `--retry-failed` re-attempts.
- Instagram rate-limits hard (`HTTP 429`). Never parallelise IG calls, always sleep
  between pages, and stop the run on the first 429 rather than hammering.
