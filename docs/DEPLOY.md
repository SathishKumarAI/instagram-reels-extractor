# Deploy

> Run the platform in Docker with your data staying on the host, handle the one real gotcha (the Claude CLI doesn't authenticate cleanly inside a container), and migrate from local to cloud without a rewrite.

The platform is **local-first**: the default deployment is Docker on your own machine, with `./data` bind-mounted so all scraped media and derived artifacts never leave the host. Cloud is a config swap, not a port.

Everything in this doc is the target design (spec §9) and is marked **Planned** — the `docker/` directory is ticket #9. The auth model and migration path below are the decisions that shape it.

## Images (Planned)

| File | Builds | Runs |
|------|--------|------|
| `docker/Dockerfile.backend` | Python 3.12 + ffmpeg (imageio) + whisper + fastembed + fastapi/uvicorn | `reels-scrap serve` |
| `docker/Dockerfile.web` | Node build → static bundle | served by backend on one port, or nginx |
| `docker/docker-compose.yml` | backend + (optional) web | bind-mounts `./data`; persists model cache |

## The local default: compose + bind-mounted data

```bash
# (Planned) from repo root
docker compose -f docker/docker-compose.yml up --build
```

Key properties:

- **`./data` is bind-mounted into the backend**, so `data/input/` (media, cookies, session) and `data/output/` (records, PDFs, index, knowledge) stay on the host (R10).
- The **model cache is persisted** via `data/input/cache/` — Whisper/fastembed download once, not per container start.
- The web bundle is served by the backend on a single port (or nginx if you split it).

> **Why bind-mount instead of a named volume:** you can open the PDFs, inspect `output/reels/*.json`, and back up `data/input/` directly from the host filesystem — the whole point of local-first is that the data is *yours*, not trapped in a container.

## The Claude CLI auth caveat

The single biggest deployment gotcha: **`claude` CLI auth (your subscription login) does not transfer cleanly into a container.** Vision and chat both default to `vision_backend: claude-cli`, so a fresh container has no way to call Claude.

Two supported paths:

| Path | When | How |
|------|------|-----|
| **Mount host auth** | local Docker, keep using your subscription | bind-mount host `~/.claude` **read-only** into the backend container — the default compose targets this |
| **Run backend on host** | simplest local | skip the backend container; run `reels-scrap serve` natively, containerize only the web build |
| **API key** | cloud, or any host without an interactive Claude login | set `extract.vision_backend: api` **and** chat backend `api`, export `ANTHROPIC_API_KEY` |

```bash
# Cloud / keyed path
export ANTHROPIC_API_KEY=sk-ant-...
# config.yaml:  extract.vision_backend: api   (and chat backend: api)
```

> **Why the API key for cloud:** the subscription CLI is interactive and host-bound; a headless cloud worker can't log in. The API backend is also what unlocks real vision concurrency (see [SCALING.md](SCALING.md)) — the same switch solves auth *and* the throughput ceiling.

The default compose targets **local with host `~/.claude` mounted**; cloud deployments flip to the API backend (spec §9).

## Local-now → cloud-later migration checklist

The design keeps interfaces stable so this is a checklist, not a rewrite (spec §4, §8, §9):

- [ ] **Auth:** switch `vision_backend` and chat backend from `claude-cli` → `api`; set `ANTHROPIC_API_KEY` as a secret (not in the image).
- [ ] **Concurrency:** raise `extract.vision_concurrency` / `vision_rate_per_min` now that the CLI throttle is gone (API has real concurrency).
- [ ] **Queue backend:** swap `pipeline/queue.py` from SQLite/JSONL → Redis/RQ for multi-worker scale-out (interface unchanged).
- [ ] **Storage:** repoint `core/paths.py` (via `config.yaml` `paths:`) from the host bind-mount to durable cloud storage. The `paths` module is the single place this lives.
- [ ] **Secrets:** move `ANTHROPIC_API_KEY` and any IG cookies/session out of files into the platform's secret store; never bake them into images.
- [ ] **Web serving:** keep single-port (backend serves static) or front with nginx/CDN — no app change.
- [ ] **Scale the workers:** run multiple extract workers against the shared Redis queue; vision rate limit (`ratelimit.py`) keeps you under API quota across all of them.

> **The one-config-change promise:** because `core/paths.py` is the only module that knows the layout and `pipeline/` is the only place that knows concurrency, local↔cloud touches config + two swappable backends — not the stage code.

## Gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Vision/chat fail in container with empty error | CLI auth not present inside container | Mount host `~/.claude` read-only, or switch to `vision_backend: api` |
| Model re-downloads every container start | Cache not persisted | Ensure `data/input/cache/` is on the bind-mount |
| Data disappears on container rebuild | Using an ephemeral volume | Use the `./data` bind-mount (compose default) |
| 429 / throttle after moving to cloud | Concurrency raised but quota unchanged | Tune `vision_rate_per_min` to your API quota — see [SCALING.md](SCALING.md) |

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — module boundaries that make cloud a swap
- [SCALING.md](SCALING.md) — why the API backend lifts the vision ceiling
- [USAGE.md](USAGE.md) — `vision_backend` and the config knobs
- [Design spec §9](superpowers/specs/2026-06-18-research-platform-design.md)
