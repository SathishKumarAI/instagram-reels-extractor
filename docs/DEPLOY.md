# Deploy

> Run the platform in Docker with your data staying on the host, handle the one real gotcha (the Claude CLI doesn't authenticate cleanly inside a container), and migrate from local to cloud without a rewrite.

The platform is **local-first**: the default deployment is Docker on your own machine, with `./data` and `./output` bind-mounted so all scraped media and derived artifacts never leave the host. Cloud is a config swap, not a port.

## Images

| File | Builds | Runs |
|------|--------|------|
| `docker/Dockerfile.backend` | Python 3.12 + ffmpeg (imageio) + whisper + fastembed + fastapi/uvicorn | `reels-scrap serve` |
| `docker/Dockerfile.web` | Node build → static bundle | optional split frontend behind `docker/nginx.conf` |
| `docker/docker-compose.yml` | backend (web service available but commented out) | bind-mounts `./data` + `./output`; persists model cache |

## The local default: compose + bind-mounted data

```bash
# from repo root
docker compose -f docker/docker-compose.yml up --build
```

Key properties:

- **`./data` and `./output` are bind-mounted into the backend** (`/app/data`, `/app/output`), so inputs (media, per-reel JSON) and outputs (records, PDFs, index, knowledge, logs) stay on the host (R10). `config.yaml` is mounted read-only.
- The **model cache is persisted** via `data/cache/` on the bind-mount — Whisper/fastembed download once, not per container start.
- The backend serves the built `web/dist` bundle on a single port (`8000`). The split nginx frontend (`Dockerfile.web` + `nginx.conf`) is available but commented out in compose — you only need it if you want to serve the UI separately.

> **Why bind-mount instead of a named volume:** you can open the PDFs, inspect `data/*.json`, and back up `data/` directly from the host filesystem — the whole point of local-first is that the data is *yours*, not trapped in a container.

## The Claude CLI auth caveat

The single biggest deployment gotcha: **`claude` CLI auth (your subscription login) does not transfer cleanly into a container.** Vision and chat both default to `vision_backend: claude-cli`, so a fresh container has no way to call Claude.

Two supported paths:

| Path | When | How |
|------|------|-----|
| **Mount host auth** | local Docker, keep using your subscription | the default compose already bind-mounts host `~/.claude` → `/root/.claude` **read-only** in the backend container |
| **Run backend on host** | simplest local | skip the backend container; run `reels-scrap serve` natively, containerize only the web build |
| **API key** | cloud, or any host without an interactive Claude login | set `extract.vision_backend: api`, export `ANTHROPIC_API_KEY` (compose already passes it through) |

```bash
# Cloud / keyed path
export ANTHROPIC_API_KEY=sk-ant-...
# config.yaml:  extract.vision_backend: api   (and chat backend: api)
```

> **Why the API key for cloud:** the subscription CLI is interactive and host-bound; a headless cloud worker can't log in. The API backend is also what unlocks real vision concurrency (see [SCALING.md](SCALING.md)) — the same switch solves auth *and* the throughput ceiling.

The default compose targets **local with host `~/.claude` mounted**; cloud deployments flip to the API backend (spec §9).

## Local-now → cloud-later migration checklist

The design keeps interfaces stable so this is a checklist, not a rewrite (spec §4, §8, §9):

- [ ] **Auth:** switch `extract.vision_backend` (and the chat backend) from `claude-cli` → `api`; set `ANTHROPIC_API_KEY` as a secret (not in the image).
- [ ] **Concurrency:** raise `extract.vision_concurrency` now that the CLI throttle is gone (the API has real concurrency).
- [ ] **Queue backend (Planned):** add a persistent distributed queue (SQLite/JSONL → Redis/RQ) for multi-worker scale-out — today the pipeline is a single-process `ThreadPoolExecutor` with sidecar-based resume.
- [ ] **Storage:** repoint `config.yaml` `paths:` from the host bind-mount to durable cloud storage. `Config`'s `*_dir` properties are the single place the layout lives.
- [ ] **Secrets:** move `ANTHROPIC_API_KEY` and any IG cookies/session out of files into the platform's secret store; never bake them into images.
- [ ] **Web serving:** keep single-port (backend serves `web/dist`) or front with the nginx web image / a CDN — no app change.
- [ ] **Scale the workers:** once the distributed queue lands, run multiple workers against it; the vision semaphore (`ratelimit.py`) keeps you under API quota across all of them.

> **The one-config-change promise:** because `Config`'s `*_dir` properties are the only place that knows the layout and `ratelimit.py` is the only place vision concurrency is bounded, local↔cloud touches config + the swappable LLM backend — not the stage code.

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Vision/chat fail in container with empty error | CLI auth not present inside container | Mount host `~/.claude` read-only, or switch to `vision_backend: api` |
| Model re-downloads every container start | Cache not persisted | Ensure `data/cache/` is on the bind-mount |
| Data disappears on container rebuild | Using an ephemeral volume | Use the `./data` + `./output` bind-mounts (compose default) |
| 429 / throttle after moving to cloud | Concurrency raised but quota unchanged | Lower `extract.vision_concurrency` to fit your API quota — see [SCALING.md](SCALING.md) |

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — module boundaries that make cloud a swap
- [SCALING.md](SCALING.md) — why the API backend lifts the vision ceiling
- [USAGE.md](USAGE.md) — `vision_backend` and the config knobs
- [Design spec §9](superpowers/specs/2026-06-18-research-platform-design.md)
