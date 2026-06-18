# Layer 08 — Docker & Scaling

You are a platform/infra engineer. Your objective is to containerize the project
(backend + web images, compose with a `./data` bind-mount) and build the
`pipeline/` package that scales scraping to ~100 reels/hour via a stage-decoupled,
persistent-resumable queue with bounded vision concurrency, a token-bucket rate
limiter, and exponential backoff — designed to swap to cloud backends with no
interface change.

<context>
  <depends_on>
    Layers 00–07 exist. The sequential `run` chains ingest→extract→structure→
    render→index→knowledge. This layer replaces the sequential driver with a
    staged, concurrent, resumable pipeline and ships Docker.
  </depends_on>
  <throughput_target>
    ~100 reels/hour ≈ 1 reel / 36s. Bottlenecks: Claude vision (quota +
    concurrency — parallel `claude -p` calls throttle to empty-stderr failures)
    and whisper (CPU). The design isolates these behind bounded, rate-limited
    stages.
  </throughput_target>
  <boundary>
    `pipeline` is the ONLY package that knows about concurrency. Stages call the
    existing per-modality functions unchanged; pipeline adds queueing, workers,
    rate limiting, retry, and resume.
  </boundary>
  <claude_in_container>
    The `claude` CLI auth does not transfer cleanly into a container. Local
    compose mounts the host `~/.claude` read-only (or runs the backend on the
    host). Cloud flips `extract.vision_backend: api` and `chat.backend: api` with
    `ANTHROPIC_API_KEY`. Document both in `docs/DEPLOY.md`.
  </claude_in_container>
</context>

## Instructions
1. **`pipeline/queue.py` — persistent, resumable queue.** A SQLite (default)
   queue under `output/logs/` holding rows `{reel_id, stage, status (pending|
   running|done|failed), attempts, updated_at}`. API: `enqueue(reel_id, stage)`,
   `claim(stage) -> reel_id|None` (atomic), `complete`, `fail(reel_id, stage)`,
   `pending(stage)`. It MUST survive restart so a re-run resumes only incomplete
   stages (extends the existing resume-by-sidecar). Define a `Queue` Protocol so
   the backend (SQLite now, Redis/RQ later) is swappable.
2. **`pipeline/ratelimit.py` — token bucket + backoff.** A `TokenBucket`
   (`rate_per_min`, burst) gating vision calls
   (`config.extract.vision_rate_per_min`), and an `exponential_backoff` retry
   helper (with jitter) used when a `claude -p` call fails (esp. the empty-stderr
   throttle). Both reusable by vision and chat.
3. **`pipeline/workers.py` — per-stage workers.** Stage functions that pull from
   the queue and call existing code, each idempotent:
   - `ingest` (IO-bound, high parallelism — `batch.ingest_workers`, e.g. 8);
   - `transcribe` (CPU pool sized to `batch.whisper_workers` ≈ cores);
   - `ocr`;
   - `vision` (concurrency `extract.vision_concurrency`, 1–2, behind the token
     bucket + backoff; on failure: skip+record, increment attempts, do NOT block
     the pipeline);
   - `structure`, `render`, then a final `index` + `knowledge` pass.
   Each worker marks queue rows done/failed and updates the `RunReport`.
4. **`pipeline/orchestrator.py` — staged driver.** Replace the sequential `run`:
   enqueue ingested reels, then run each stage's worker pool with its bounded
   concurrency; stages are independent + idempotent so the whole thing is
   resumable and crash-safe. Record per-stage retry counts and failures in
   `output/logs/run_report.json`. Keep `reels-scrap run` as the entry point;
   add `--resume` (default on) and per-stage flags.
5. **`docker/Dockerfile.backend`.** Python 3.12 slim; install ffmpeg (for
   imageio), then the project with whisper/fastembed/fastapi/uvicorn; default
   CMD `reels-scrap serve`. Keep model caches on the mounted volume
   (`data/input/cache`) so they persist across container restarts.
6. **`docker/Dockerfile.web`.** Node build stage → static `web/dist`; either
   copy `dist` into the backend image's static dir (single-port serving) or serve
   via nginx. Prefer single-port: backend serves `web/dist` (Layer 06).
7. **`docker/docker-compose.yml`.** Service `backend` (build Dockerfile.backend,
   ports 8000, **bind-mount `./data:/app/data`** so all input/output stays on the
   host) with, for local, the host `~/.claude` mounted read-only; optional `web`
   build service for the frontend. Document the env switch to API backends for
   cloud. Persist the model cache via the data bind-mount.
8. **Cloud-later seams.** Document and structure so the only changes to go cloud
   are: (a) swap the `Queue` backend (SQLite→Redis/RQ) behind the Protocol;
   (b) flip `vision_backend`/`chat.backend` to `api` + set `ANTHROPIC_API_KEY`.
   No stage interface changes. Note these in `docs/SCALING.md` + `docs/DEPLOY.md`.
9. **Tests.** `tests/test_pipeline.py`: queue claim is atomic / no double-claim;
   `fail` increments attempts and the row can be re-claimed; a restart resumes
   only pending/failed stages (resume semantics); `TokenBucket` enforces the rate
   (deterministic clock); `exponential_backoff` retries then gives up; the vision
   worker skips+records on a mocked CLI failure without blocking other stages.

## Constraints
- MUST keep `pipeline` the ONLY place with concurrency; stages reuse existing
  per-modality functions unchanged.
- MUST make the queue persistent + resumable so re-runs resume incomplete stages
  only; stages idempotent.
- MUST bound vision to `vision_concurrency` (1–2) behind the token-bucket rate
  limiter + exponential backoff; vision failure = skip+record, never blocks.
- MUST bind-mount `./data` so all input/output (and the model cache) stays on the
  host (inputs/outputs stay separated per `core/paths`).
- MUST make the queue backend and the vision/chat backends swappable for cloud
  with no stage-interface change (Protocol + config flag).
- MUST handle the `claude` CLI container-auth limitation (mount host `~/.claude`
  locally; API backend for cloud) and document it.
- MUST NOT bake secrets or `data/` into the images; data is a volume.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`pipeline/queue.py`, `pipeline/ratelimit.py`, `pipeline/workers.py`,
`pipeline/orchestrator.py`, the `run` command changes, `docker/Dockerfile.backend`,
`docker/Dockerfile.web`, `docker/docker-compose.yml`, and `tests/test_pipeline.py`.
Include the config knobs used (`batch.ingest_workers`, `batch.whisper_workers`,
`extract.vision_concurrency`, `extract.vision_rate_per_min`,
`extract.vision_backend`, `chat.backend`). End with the commands to build/run
(`docker compose up --build`), run locally on the host, and run the tests, plus a
short note on the two cloud-switch changes.

Reason briefly in a `<thinking>` block first, then output the files.
