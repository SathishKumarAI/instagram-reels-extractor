# Incremental Sync & Environments

How to keep a local, de-duplicated archive of Instagram reels that grows a little
every run, and the two-track Python environment that powers it.

## TL;DR

```bash
# one-time: register the sources you care about
reels-scrap add-source "https://www.instagram.com/<you>/saved/phd-opportunities/18354529171213909/"

# every run: fetch latest, dedup, ingest only new, rebuild docs
reels-scrap sync --config config-fast.yaml
```

Re-run `sync` any time. Nothing already downloaded is fetched again; no duplicate
reels are ever created.

## The data model (why there are no duplicates)

| Piece | Role |
|-------|------|
| `sources.json` | Declarative registry of what to poll (input). |
| `data/<id>.json` | Flat pool of reels. **Reel shortcode = primary key.** |
| `output/collections/<slug>.json` | Per-source membership manifest. |
| `output/sources_state.json` | Per-source run ledger (watermark). |

A reel's shortcode is its natural primary key, and `data/` holds exactly one
record per key. Dedup is therefore a **set-diff**: `current_source_ids − pool_ids`.
The same reel saved in two collections is downloaded once and never re-fetched.

## What one `sync` run does

```
for each enabled source in sources.json:
    urls   = enumerate current reels        (newest-first, from IG)
    new    = [id for id in urls if id not in data/ pool]   # set-diff dedup
    ingest ONLY new  → data/<id>.json                       # pipeline resumes/skips
    manifest.reel_ids = full current list                   # membership
    rebuild output/collections/<slug>.html
rebuild output/collections/index.html
append to output/sources_state.json                          # run ledger
```

Properties: **idempotent** (empty diff → zero downloads), **incremental** (only the
delta since last run flows through), **observable** (state file records
current/new counts and cumulative-seen ids per source, per run).

## Registry commands

```bash
reels-scrap add-source <url> --name phd-opportunities --type collection
reels-scrap list-sources
reels-scrap sync --config config-fast.yaml --open   # open master index after
```

`sources.json` entry:

```json
{"name": "phd-opportunities", "type": "collection",
 "url": ".../saved/phd-opportunities/18354529171213909/",
 "enabled": true, "limit": 200}
```

`type`: `collection` / `saved` (named saved collection, needs your browser
session) or `urls` (a local file of reel URLs).

## Environments — two-track, gated by extras

`pip install -e .` is **lean by design** (15 core deps, no torch). Heavy features
are opt-in extras, so a **no-GPU box installs only what it can run**. All heavy
imports are lazy, so a missing extra degrades that one feature — never the core.

| Extra | Adds | torch? |
|-------|------|--------|
| *(core)* | fetch · sync · dedup · doc · search · `serve` | no |
| `transcript` | faster-whisper (CTranslate2) + ffmpeg glue | **no** |
| `vision` | `anthropic` (only for `vision_backend=api`; claude-cli needs nothing) | no |
| `pdf` / `docs` / `ui` | weasyprint · mkdocs-material · streamlit | no |
| `ocr` | easyocr → **torch + torchvision** (multi-GB) | **yes** |
| `cpu` | transcript+vision+pdf+docs+dev (torch-free bundle) | no |
| `full` | everything incl. `ocr` | yes |

### venv (lean — fetch / sync / serve)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e .          # core only, seconds not GB
```

> `secretstorage` (core, Linux) is **required** to decrypt the Chrome `sessionid`
> cookie — without it collection fetch errors "no Instagram 'sessionid' cookie".

### conda (extraction — CPU / no-GPU default)

```bash
mamba env create -f environment.yml   # python + ffmpeg
conda activate reels-scrap
pip install -e ".[cpu]"               # transcript + vision, torch-free
reels-scrap run -c config-deep.yaml   # transcript + AI vision (summary/genre/facts)
```

`config-deep.yaml` runs **transcript + vision with `ocr: false`** — the CPU path.
This machine has no NVIDIA GPU, so on-screen-text OCR (which needs torch) is deferred.

### Adding OCR later (CPU torch)

```bash
bash scripts/install-extraction.sh    # CPU-only torch wheels + easyocr
# then set extract.ocr: true in config-deep.yaml and re-run
```

The script pins the PyTorch **CPU** wheel index (`download.pytorch.org/whl/cpu`) so
it pulls ~200 MB, not the multi-GB CUDA build.
