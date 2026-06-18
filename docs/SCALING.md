# Scaling to ~100 reels/hour

> How the pipeline sustains ~100 reels/hour (1 reel / 36 s) despite a Claude vision stage that throttles past 2 parallel calls — by decoupling stages, bounding concurrency per stage, rate-limiting vision, and making the whole run resumable.

The throughput target is **~100 reels/hour = 1 reel every 36 seconds** (spec §8). You don't hit that by turning concurrency up everywhere — one stage (vision) has a hard ceiling, and naive parallelism makes it *fail*. The design routes around that ceiling.

Most of this is the target `pipeline/` package and is marked **Planned** (ticket #4). Today the codebase runs a simpler per-reel `batch.workers` model (`pipeline.py`); the principles below explain where it's going and why.

## The two bottlenecks

| Stage | Limit | Nature |
|-------|-------|--------|
| **Claude vision** | quota + concurrency — **3 parallel `claude -p` calls already throttle** to empty-stderr failures (observed live) | external, hard ceiling |
| **whisper** | CPU-bound transcription | local, scales with cores |

Everything else (download IO, OCR, render, embed) is comparatively cheap and parallelizes freely. So the strategy: **let the cheap stages run wide, isolate the two bottlenecks, and never let one stall the others.**

## Design

### 1. Stage-decoupled pipeline

Each stage is **independent and idempotent**. Ingest (IO-bound, high parallelism) feeds a queue; extract workers pull from it; downstream stages read the resulting records. A slow vision call can't block downloads, and a re-run only redoes what's incomplete.

> **Why decouple:** if all stages ran in one per-reel worker, the vision ceiling (concurrency 1–2) would cap the *entire* pipeline at 1–2 reels in flight. Decoupling lets ingest run 8-wide while vision sips at its safe rate.

### 2. Bounded concurrency per stage

Each stage gets its own concurrency budget instead of one global `workers` number:

- **ingest** — high (e.g. 8); IO-bound.
- **whisper** — pool ≈ CPU cores; CPU-bound.
- **vision** — **concurrency 1–2**, behind a token-bucket rate limiter.

### 3. Vision: token bucket + backoff

Vision goes through `pipeline/ratelimit.py`:

- **Token-bucket rate limit** (`extract.vision_rate_per_min`) smooths calls so you stay under quota.
- **Concurrency 1–2** (`extract.vision_concurrency`) — never the 3+ that throttles.
- **Exponential backoff** on CLI failure — the empty-stderr throttle is treated as recoverable, the call retries after a growing delay rather than burning a reel.

> **Why 1–2, not 3:** 3 parallel `claude -p` calls were observed throttling to silent (empty-stderr) failures. 1–2 is the safe shoulder. For real concurrency, switch `vision_backend: api` (the Claude API), which lifts the CLI ceiling — see [DEPLOY.md](DEPLOY.md).

### 4. Persistent, resumable queue

`pipeline/queue.py` keeps a SQLite (or JSONL) table of `{reel_id, stage, status, attempts}` under `output/logs/`. It **survives restart** — re-running `reels-scrap run` resumes only incomplete stages, building on the existing resume-by-sidecar behaviour.

> **Why persistent:** a 100-reel run that dies at reel 80 should resume at 80, not re-scrape and re-pay-for-vision on the first 80.

### 5. Retry + provenance

Per-stage retry with backoff; every failure is recorded in `output/logs/run_report.json` (the provenance manifest already in place). You can see exactly which reel failed which stage, and how many attempts it took — no silent data loss.

## Tuning table

| Knob | Stage | Default (target) | Raise when… | Lower when… |
|------|-------|------------------|-------------|-------------|
| `batch.ingest_workers` | ingest | 8 | downloads are the bottleneck and IG isn't rate-limiting | IG returns rate-limit errors |
| `batch.whisper_workers` | transcript | ≈ CPU cores | CPU is idle during transcription | machine thrashes / OOMs |
| `extract.vision_concurrency` | vision | 1–2 | switched to `vision_backend: api` | seeing empty-stderr throttle |
| `extract.vision_rate_per_min` | vision | tuned to quota | well under quota, want more throughput | hitting quota / 429s |
| `extract.vision_backend` | vision | `claude-cli` | need real concurrency (cloud) → `api` | staying local subscription |
| `batch.workers` *(current code)* | extract+render | 3 | extra cores, vision off or API | vision throttles |

> **Planned vs. now:** the per-stage knobs above are spec §8 (ticket #4). Today only `batch.workers` exists, governing per-reel extract+render parallelism — keep it at 3 or lower while vision uses the CLI.

## Doing the throughput math

At the 36 s/reel budget, vision is the pacing stage. With `vision_concurrency: 2` and ~60 s per call, two-in-flight clears ~2 reels/min ≈ 120/hr — *if* the rate limiter and backoff keep calls from throttling. The other stages must stay ahead of vision (they do, being cheaper and wider), so the queue never starves. Drop to the CLI's safe 1–2 concurrency and respect the rate limit, and ~100/hr is the realistic sustained figure; push past it (3+) and you go *backwards* as throttled calls retry.

## Cloud-future

The interfaces don't change when you scale out (spec §8):

- Swap the queue backend: **SQLite → Redis/RQ**.
- Flip vision to the **Claude API** backend for real concurrency.

Same `pipeline/` contract, same stages. See [DEPLOY.md](DEPLOY.md) for the migration checklist.

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — pipeline package + data flow
- [USAGE.md](USAGE.md) — the config knobs in context
- [DEPLOY.md](DEPLOY.md) — local→cloud, the API-backend path
- [Design spec §8](superpowers/specs/2026-06-18-research-platform-design.md)
