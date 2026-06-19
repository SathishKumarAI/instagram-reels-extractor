# Scaling to ~100 reels/hour

> How the pipeline sustains ~100 reels/hour (1 reel / 36 s) despite a Claude vision stage that throttles past 2 parallel calls — by decoupling stages, bounding concurrency per stage, rate-limiting vision, and making the whole run resumable.

The throughput target is **~100 reels/hour = 1 reel every 36 seconds** (spec §8). You don't hit that by turning concurrency up everywhere — one stage (vision) has a hard ceiling, and naive parallelism makes it *fail*. The design routes around that ceiling.

Today the pipeline (`pipeline.py`) runs the cheap stages wide via a `ThreadPoolExecutor` (`batch.workers`) while gating vision through a process-wide semaphore + exponential backoff in `ratelimit.py`. The one remaining cloud-phase step — a durable, distributed job queue — is marked **Planned** below.

## The two bottlenecks

| Stage | Limit | Nature |
|-------|-------|--------|
| **Claude vision** | quota + concurrency — **3 parallel `claude -p` calls already throttle** to empty-stderr failures (observed live) | external, hard ceiling |
| **whisper** | CPU-bound transcription | local, scales with cores |

Everything else (download IO, OCR, render, embed) is comparatively cheap and parallelizes freely. So the strategy: **let the cheap stages run wide, isolate the two bottlenecks, and never let one stall the others.**

## Design

### 1. Wide-cheap stages, gated vision

The pipeline runs reels through a `ThreadPoolExecutor` (`batch.workers`), so the cheap stages (download IO, OCR, render, embed) run in parallel. Vision is the exception: every vision call passes through a **process-wide semaphore** (`ratelimit.py`), so however many worker threads are in flight, only `extract.vision_concurrency` of them call `claude -p` at once. A slow or throttled vision call can't multiply across threads.

> **Why gate vision separately:** if vision parallelism tracked `batch.workers`, raising workers to 8 would fire 8 concurrent `claude -p` calls — well past the throttle point. The semaphore decouples the two so you can run the cheap stages wide and still keep vision at its safe 1–2.

### 2. Bounded vision concurrency

Vision concurrency is its own budget, not tied to `batch.workers`:

- **cheap stages** — ride `batch.workers` (default 3); IO/CPU-bound, parallelize freely.
- **vision** — **concurrency 1–2** (`extract.vision_concurrency`), held behind the semaphore.

### 3. Vision: semaphore + backoff

Vision goes through `ratelimit.py`:

- **Process-wide semaphore** (`extract.vision_concurrency`, default 1) — never the 3+ that throttles.
- **Exponential backoff** on CLI failure (`extract.vision_max_retries`, `extract.vision_retry_backoff`) — the empty-stderr throttle is treated as recoverable; the call retries after a delay growing by `2^n` rather than burning a reel.

> **Why 1–2, not 3:** 3 parallel `claude -p` calls were observed throttling to silent (empty-stderr) failures. 1–2 is the safe shoulder. For real concurrency, switch `vision_backend: api` (the Claude API), which lifts the CLI ceiling — see [DEPLOY.md](DEPLOY.md).

### 4. Resume-by-sidecar (durable queue is Planned)

Re-running `reels-scrap run` resumes only incomplete stages: each reel's per-reel JSON record acts as a sidecar marking what's already done, so a run that dies partway doesn't re-scrape or re-pay-for-vision on finished reels.

> **Planned (spec §8):** a full **persistent, distributed job queue** — a SQLite/Redis table of `{reel_id, stage, status, attempts}` for multi-worker scale-out — is the cloud-phase step. Today's resume relies on the per-reel sidecar plus the `run_report.json` manifest, not a standalone queue.

### 5. Retry + provenance

Vision gets per-call retry with backoff; every failure is recorded in `output/logs/run_report.json` (the provenance manifest). You can see exactly which reel failed which stage, and how many attempts it took — no silent data loss.

## Tuning table

| Knob | Stage | Default | Raise when… | Lower when… |
|------|-------|---------|-------------|-------------|
| `batch.workers` | extract+render | 3 | extra cores, vision off or on `api` | vision throttles / machine thrashes |
| `extract.vision_concurrency` | vision | 1 | switched to `vision_backend: api` | seeing empty-stderr throttle |
| `extract.vision_max_retries` | vision | 3 | throttling is frequent and transient | failures are real, not throttle |
| `extract.vision_retry_backoff` | vision | 5.0s | throttle clears slowly | calls recover fast, want less idle |
| `extract.vision_backend` | vision | `claude-cli` | need real concurrency (cloud) → `api` | staying local subscription |

> **Today vs. cloud:** these knobs are all live. The one piece still ahead is the durable distributed queue (spec §8) — until then, keep `batch.workers` at 3 or lower while vision uses the CLI, and let the semaphore + backoff absorb throttling.

## Doing the throughput math

At the 36 s/reel budget, vision is the pacing stage. With `vision_concurrency: 2` and ~60 s per call, two-in-flight clears ~2 reels/min ≈ 120/hr — *if* the semaphore and backoff keep calls from throttling. The other stages stay ahead of vision (they're cheaper and ride the wider `batch.workers` pool), so vision never starves. Stay at the CLI's safe 1–2 concurrency and ~100/hr is the realistic sustained figure; push past it (3+) and you go *backwards* as throttled calls retry.

## Cloud-future

Two pieces change when you scale out (spec §8):

- **Add a persistent, distributed queue** (SQLite → Redis/RQ) so multiple workers can pull jobs — this is the one **Planned** item; today's resume is sidecar-based, single-process.
- **Flip vision to the Claude API** backend for real concurrency.

Same stages, same `ratelimit.py` gate (which then keeps you under the API quota across workers). See [DEPLOY.md](DEPLOY.md) for the migration checklist.

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — module map + data flow
- [USAGE.md](USAGE.md) — the config knobs in context
- [DEPLOY.md](DEPLOY.md) — local→cloud, the API-backend path
- [Design spec §8](superpowers/specs/2026-06-18-research-platform-design.md)
