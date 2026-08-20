# api/ — the local HTTP surface (127.0.0.1 only, no auth)

Read this table instead of the code.

| Change | File |
|---|---|
| CORS, router order, serving `web/dist` | `app.py` |
| Reels list/detail, annotations, saved views, tags, media | `routes/library.py` |
| Search, RAG chat, aggregated knowledge | `routes/qa.py` |
| `/api/stats`, csv / md / xlsx export, token pricing | `routes/exports.py` |
| Sources, starting a sync, Sync-tab status, single-URL ingest | `routes/sync.py` |
| Variant diff, compare a reel, batch, scoreboard, model profiles | `routes/compare.py` |
| Discovery candidates and Save / No / Later | `routes/discover.py` |
| `/api/health` checks (disk, index, cookies, local vision) | `routes/health.py` |
| Response models the UI's types mirror | `schemas.py` |
| Id guard, reel loading, hit shaping | `deps.py` |

## Rules that keep the table true

- One route group per file, each exposing `build(cfg, config_path) -> APIRouter`.
  `routes/__init__.py` lists them in `ROUTERS`; `create_app` includes them in order.
- **The SPA catch-all is mounted last** and is the one place order matters — it
  swallows every unmatched path, so a router included after it would be dead.
- A helper used by one route group lives in that file. `deps.py` is for what two
  or more need, and stays short.
- Background work is a module-level status dict plus a daemon thread, one per
  concern (`_SYNC`, `_BATCH`, `_DISCOVER`). There is exactly one of each at a
  time: a second start is a **409**, never a queue.
- Heavy imports stay inside the handler — the API must start without ollama,
  openpyxl or a search index present.
- Ids from the URL go through `deps.safe_id` before touching the filesystem.

## Traps

- `app.py` re-exports `_stage_and_progress`, `STAGES`, `SourceIn` and `SyncIn`
  from `routes/sync.py`; they moved there in the 2026-08-20 split and
  `tests/test_sync_status.py` still imports them from `app`.
- **The API binds `127.0.0.1` and has no auth.** Never change that default — see
  `docs/PRIVACY.md`.
- Costs shown by `/api/stats` are real only when the CLI reported them; otherwise
  they are an estimate from `routes/exports.py:PRICES`, which is per *family*
  (opus/sonnet/haiku) and knows nothing about local models ($0).
