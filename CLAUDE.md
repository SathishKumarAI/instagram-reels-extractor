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
| A CLI command | `cli/<group>.py` — table in `cli/README.md` |
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
- `sync` stops before spending an Instagram request when the session probe fails
  (`auth_blockers()`, exit **4**) or the GPU is busy (exit **3**). A guard that only
  warns is not a guard — the probe used to warn and continue, which is how one dead
  cookie cost 20 requests. Overrides: `REELS_IGNORE_AUTH=1`, `REELS_IGNORE_GPU=1`.
- Instagram rate-limits hard (`HTTP 429`). Never parallelise IG calls, always sleep
  between pages, and stop the run on the first 429 rather than hammering.

<!-- plane-agent-rules:v2 -->
## Issue tracking (Plane, local)

All work across `~/Documents/coding` is tracked in one Plane board.
The `plane` MCP server is registered at user scope, so its tools are available
in every session — no setup needed per repo.

- Workspace `coding`, project `Coding` (identifier `COD`), at <http://localhost:8080/coding/>
- **This repo is the label `repo:instagram-reels-extractor`.** Every work item you create must carry it.
- Also add one `type:` label matching the conventional-commit type you intend to
  use: `type:feat` `type:fix` `type:refactor` `type:perf` `type:docs` `type:test`
  `type:build` `type:chore`.

States, and what each one means here:

| State | Means |
|---|---|
| `Backlog` | Captured, not committed to. Default for anything you file mid-task. |
| `Todo` | Pulled into the current cycle. This week's list. |
| `In Progress` | A branch exists. |
| `In Review` | A PR is open, waiting on CI or a read. |
| `Done` | Squash-merged, branch deleted. |
| `Cancelled` | Decided against. Say why in a comment — that reasoning is the value. |

Rules:

1. **Before starting work, check for an existing work item** for what you are
   about to do. Duplicates are worse than nothing because they split the history
   of a decision. **Two ways to look, and both have a trap** — see "Finding an
   existing item" below. An empty result from a search you got wrong reads
   exactly like an empty board, which is how duplicates get filed.
2. **A found bug outside the current task's scope gets filed, not silently left.**
   File it in `Backlog` with `repo:instagram-reels-extractor`, say in your reply that you filed it.
   This is the mechanism the global CLAUDE.md rule refers to.
3. **Move the item as the branch moves**: `In Progress` when the branch is cut,
   `In Review` when the PR opens, `Done` on squash-merge.
4. **Put the work item id in the PR body** (`COD-12`), not only in the branch name.
5. Do not create Plane *projects*. One project is deliberate — repos are labels
   so a repo can move between `now/`, `shelf/` and `live/` without its tickets
   being migrated.
6. Cycles are weeks. If the user asks "what am I doing this week", read the
   current cycle, not the whole backlog.

### Finding an existing item

This Plane is the **Community edition**. `workitem list` with a `pql` or any
structured filter fails outright:

> PQL and structured filters are not supported on this Plane edition.

So **there is no server-side way to filter by the `repo:` label.** Filter in your
own head instead — list, then read:

```
workitem list  project_id=<COD uuid>  per_page=100
               fields=sequence_id,name,state,labels
```

and keep only the rows whose `labels` contain this repo's label UUID. Get that
UUID once from `label list` (the API returns UUIDs everywhere and accepts nothing
else). The board is small enough that one unfiltered list is cheaper than the
round-trips to avoid it.

`workitem search` also works, but **it matches a contiguous substring of the
title, not a set of words.** Searching `"LM Studio local model"` returns nothing
while `"LM Studio"` returns two items — the first phrase appears in no title.
**Search one distinctive token** (`local_model`, `vault.yaml`, `8787`), never a
sentence, and treat a miss as "my query was too long", not as "no such ticket".

### Useful UUIDs

Every repo shares one project and one set of states, so these are fixed. Only the
`repo:` label differs — look yours up with `label list`.

| Thing | UUID |
|---|---|
| project `Coding` (COD) | `384bb763-72eb-497f-8ddb-142f7c178668` |
| state `Backlog` | `c1497bfa-8446-49f0-aa45-976b0311b82f` |
| state `Todo` | `c074ade8-4a34-4a89-8de3-e7ab61caedf6` |
| state `In Progress` | `824d6862-acf5-4562-82d3-fc1ee7eaadd9` |
| state `In Review` | `25021b28-b089-490e-9628-d4c0fd1a5253` |
| state `Done` | `ede567e7-3e57-405e-ac93-fb04db6bcfff` |
| state `Cancelled` | `85b6f97d-30e3-4cf4-ae58-063a0e239b4f` |

Plane does not replace `STATUS.md`. `STATUS.md` is re-entry context — where you
stopped, the next action, the traps. Plane is the queue. Both, in the same commit
as the work.

<!-- /plane-agent-rules -->
