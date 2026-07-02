# Feature Backlog — reels-scrap

Prioritized by **value ÷ effort**, grouped into shipping tiers. Status: ☐ todo · ◑ in progress · ☑ done.

The research platform itself (ingest → extract → structure → render → search → API → UI)
is built (see `TICKETS.md`). This backlog is about making it a **good, reliable codebase**
and closing the gaps that show up in real use.

---

## Now — shipped / in flight

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 1 | **Local consolidated docs** — `collection <url>` (fetch→extract→doc→open) + `consolidate` (rebuild from data) + per-collection membership manifests + master index | ★★★ | M | ☑ | `render/consolidated.py`, `collections.py`, `docs.py`, CLI cmds, `tests/test_docs.py` (7 passing). Self-contained HTML, thumbnails embedded, links back to reels. |
| 2 | **Reproducible dev env** — the `.venv` is empty/broken (`reels_scrap`, `typer`, `pytest` not installed); base python only has pydantic. Pin deps, one-command bootstrap, `pytest` in dev extras | ★★★ | S | ☐ | Blocks running the full pipeline + suite locally. `pip install -e ".[dev]"` should just work. Add `dev` extras (pytest, ruff). |

## Next — high value, do soon

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 3 | **`reels-scrap collections` (list/status)** — table of downloaded collections: name, #reels, #with-vision, last updated, doc path | ★★ | S | ☐ | Reads manifests + `run_report.json`. Cheap, high everyday utility. |
| 4 | **Transcript quality** — non-English reels get garbled auto-translations (e.g. Hindi→"become a James Bond"). Add per-reel language detect + `translate` task, flag low-confidence transcripts in the doc | ★★★ | M | ☐ | Whisper supports `task=translate`. Surface `whisper_language` per source; mark suspect transcripts so summaries aren't trusted blindly. |
| 5 | **Doc test coverage for render/pipeline** — only api/knowledge/rag are tested. Add render (markdown+pdf), structure, and an ingest-mock pipeline test | ★★ | M | ☐ | Guards the parts users actually see. |
| 6 | **Incremental / idempotent guarantees, verified** — `resume` skips downloaded reels; add a test proving re-run of `collection` re-downloads nothing and only re-renders | ★★ | S | ☐ | Protects the "run it again when I save more" workflow. |

## Later — nice to have

| # | Feature | Value | Effort | Status | Notes |
|---|---------|-------|--------|--------|-------|
| 7 | **Search/knowledge scoped to a collection** — `search --collection front-end`, per-collection knowledge base | ★★ | M | ☐ | Manifests already give the reel-id set to filter on. |
| 8 | **Combined & per-collection PDF** — reuse `render/combined` to emit a print-ready PDF alongside the HTML doc | ★ | S | ☐ | HTML is primary; PDF for offline/sharing. |
| 9 | **UI: collections view** — surface collections + their docs in the Streamlit/React app | ★★ | M | ☐ | Backend endpoint over manifests, then a grid in `web/`. |
| 10 | **CI** — GitHub Actions: ruff + pytest on push; fail the PR on red | ★★ | S | ☐ | Depends on #2. Keeps `main` green. |
| 11 | **Config for docs** — `output.collections: true`, doc theme/accent in `config.yaml` | ★ | S | ☐ | Only if theming demand appears (YAGNI until then). |

---

## Notes on sequencing

- **#2 unblocks everything runnable** — do it first so the pipeline + suite run locally and in CI (#10).
- **#4 (transcript quality) is the biggest correctness win** — the docs are only as trustworthy as the extraction; bad transcripts poison summaries/facts.
- #7–#11 all build cleanly on the manifest layer added in #1 — no rework needed.
