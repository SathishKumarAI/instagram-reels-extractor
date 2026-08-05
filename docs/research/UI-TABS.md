# The UI, tab by tab

13 tabs, one API on `127.0.0.1:8000`, one corpus of 674 reels on disk. This is
what each surface is for, what it reads, and the thing about it worth knowing.

Everything is client-side filtered: each tab loads the full reel list once from
`GET /api/reels` and filters in memory. At 674 reels that is the simpler design;
if the corpus reaches five figures it is the first thing to change.

| Tab | For | Reads |
|---|---|---|
| Overview | where the corpus stands | `/api/stats`, `/api/report` |
| Search | find a reel by meaning, not keyword | `/api/search` |
| Reels | browse and triage the library | `/api/reels`, `/api/stats`, `/api/views` |
| Reader | read a reel as a paper | `/api/reels`, `/api/reels/{id}` |
| Table | sort, select, export | `/api/reels`, `/api/export.*` |
| Board | move reels through states | `/api/reels`, `/api/annotations` |
| Tags | see the vocabulary the models produced | `/api/tags` |
| Knowledge | topic-level synthesis | `/api/knowledge` |
| Discover | find reels you have not saved yet | `/api/discover*` |
| Sources | what gets synced, and start a sync | `/api/sources`, `/api/sync` |
| Sync | watch the pipeline run | `/api/sync/status` |
| Compare | put two models on the same reel | `/api/profiles`, `/api/reels/{id}/compare`, `/api/compare/*` |
| Research | ask the corpus a question | `/api/chat` |

---

## Overview
The landing page: corpus size, token and cost totals, genre breakdown, and the
last run's health. The cost figure here is an **estimate over mixed provenance** —
644 reels were extracted by Claude and 30 by local models, and the local ones
contribute zero. See [COSTS.md](COSTS.md).

## Search
Semantic search over an embedding index built by fastembed (ONNX, CPU) across
summaries, facts, captions and transcripts. Returns passages with a score, not
whole reels, so a hit points at the sentence that matched.
**Gotcha:** the index is incremental and keyed on a content hash — writing a
Compare variant does not trigger a re-embed, but changing a summary does. Rebuild
with `reels-scrap index --full` if results ever look stale.

## Reels
The main library. Cards carry the thumbnail, genre, **which model wrote the
record**, the collections it belongs to, its tags and its engagement numbers.
Filters: text, tag, genre, account, collection, status (starred/unread/archived),
date window and sort. Filter sets can be saved as named views.
**Clicking a collection chip filters the grid**; `/reels?collection=<slug>` is the
deep link other tabs use. Clicking a card opens a drawer with the full record,
facts table, copy-as-markdown and "more like this".

## Reader
A distraction-free reading surface: left is a searchable index of reels, right is
one reel rendered as a paper — abstract, key points with timestamps, structured
details, transcript, caption, on-screen text and extracted links. The header shows
the model that wrote it and the shelves it sits on, both clickable.
**Gotcha:** the reader shows the *active* variant. To see what another model wrote
for the same reel, use Compare.

## Table
The same corpus as a sortable, selectable spreadsheet, including Collections and
Model columns. Multi-select feeds CSV / Markdown / XLSX export. Use this when the
question is "which reels have thin records" rather than "what is this reel about".

## Board
Kanban over the annotation states (`starred`, `read`, `archived`) — the triage
surface. Annotations live in `output/annotations.json`, not in the reel records,
so re-running extraction never disturbs them.

## Tags
Every tag the models produced, with the collections it appears in and a colour
rail hashed from the collection name (FNV-1a), so a shelf is the same accent
everywhere. **664 of 1603 tags span two or more collections** — that is why chips
are split rather than blended. Tags can be renamed or merged corpus-wide here.

## Knowledge
Topic-level synthesis: reels grouped into topics, each with an overview and the
facts that back it. This is aggregation over stored records, not a fresh model
call — it changes when the corpus changes.

## Discover
Proposes reels you have **not** saved, scored against the centroid of each
collection's embeddings, from hashtag feeds and repeat authors. Save / No / Later
per candidate. Runs on a request budget and stops on the first `HTTP 429` rather
than hammering Instagram.
**Gotcha:** hashtags come from reel captions, not our slug tags (`opensource`, not
`open-source`), and `/tags/<tag>/sections/` is the endpoint that actually carries
posts — `/tags/<tag>/` returns 200 with nothing.

## Sources
The registry of saved collections and feeds that `sync` walks, each toggleable.
Also starts a sync, now with **any installed model** chosen from the same picker
the Compare tab uses.

## Sync
The live pipeline view: enumerate → download → extract+vision → docs → index, with
a tailing `run.log`, per-source counts and a run-now button. It follows syncs
started from the CLI too, because "live" is derived from the log's mtime rather
than from the API's own state.
**Gotcha:** a sync with a local model needs an endpoint. The API resolves profiles
(`config-local.yaml`), and refuses a model that is not pulled with the exact
`models pull` command to fix it.

## Compare
Two models, one reel, the same frames. Pick any two installed profiles; the tab
runs both (~35s, Claude is the slow half), shows the metrics side by side, then
the **claim diff** — what one model claimed and the other did not. Claims are
matched by containment rather than exact text, because the same claim carries more
detail on one side (`No. 1 is "Project Based Learning" at github.com/…` vs
`no. 1 PROJECT BASED LEARNING`).
Below that is the corpus scoreboard: per model, average facts / tags / summary
length / structured fields / seconds, plus **$/reel and $ total**.
**Gotcha:** a single reel is not evidence. Use "Batch compare" for a sample, or the
CLI bench (`reels-scrap bench`) for the fixed 30-reel experiment.

## Research
RAG chat over the corpus: retrieves passages, answers with citations back to the
reels. Answers are grounded in stored records — if the extraction missed
something, the chat cannot recover it.

---

## Running it

```bash
# API (127.0.0.1 only — never change that default)
reels-scrap serve -c config.yaml --port 8000

# dev UI with hot reload, proxying /api to 8000
cd web && npm run dev          # http://localhost:5173

# or build once and let the API serve it at /
cd web && npm run build
```

Related: [`MODELS.md`](MODELS.md) for the models behind the badges,
[`COSTS.md`](COSTS.md) for the money column, `docs/SETUP.md` for a clean install.
