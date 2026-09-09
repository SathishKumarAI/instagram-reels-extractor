# Optimization audit — 2026-09-08

> A read-only pass over `src/reels_scrap/`, `scripts/` and `web/src/` looking for wasted work,
> throughput ceilings, token spend, API/UI memory, and failure modes a three-line guard would
> prevent. Nothing was edited. Every timing below was produced on this box against the live
> corpus (755 records, 6.7 GB `data/`, 172 MB `output/`) with `.venv-win/Scripts/python.exe`.

## How to read this

| Label | Means |
|---|---|
| **MEASURED** | A number produced on this machine during the audit, by running the code or reading the files. The command that produced it is named in the finding. |
| **ESTIMATE** | Arithmetic on measured inputs, or extrapolation past what was run. Never a measurement wearing a measurement's clothes. |
| **UNMEASURED** | The mechanism is visible in the code; the cost was not reproduced. Stated as a mechanism, not a saving. |

Two things this report deliberately does **not** propose, because `STATUS.md` records them as
measured and rejected: `frame_max_width: 1440` (loses to 720 on every metric) and two-pass local
extraction (`vision_local_two_pass`, +0.94 facts for shorter summaries, fewer fields, +24% time).
Nothing here proposes parallelising an Instagram call, a new dependency, or moving the API off
`127.0.0.1`.

Confidence counts: **9 high**, **6 medium**, **2 speculative**.

## Filed on the board

Three findings were verified by hand against the code after this report was written, and filed
so they do not live only here:

| Finding | Work item | State |
|---|---|---|
| #5 — `annotate()` loses flags under concurrent writes | **COD-179** (`type:fix`, high) | Backlog |
| #1 — `api` backend capped at `max_tokens=900` | **COD-180** (`type:fix`, high) | Backlog |
| #2 — nested retry loops multiply to 9 × 240 s | **COD-181** (`type:fix`, medium) | Backlog |

Everything else in this report is unfiled: evidence for a decision, not a queue.

## Ranked summary

| # | Finding | File | Effort | Payoff | Confidence |
|---|---|---|---|---|---|
| 1 | `api` vision backend capped at `max_tokens=900` — 4.4× under the measured truncation floor | `extract/vision.py:197` | 1 line | Unblocks the cheapest cloud path; the planned 719-reel re-extract would otherwise burn money producing nothing | High |
| 2 | Vision retries multiply: 3 outer × 3 inner = **9 attempts × 240 s** on one reel | `extract/__init__.py:65` + `extract/vision.py:312` | 1 line | Caps a single bad reel at ~12 min instead of ~37 | High |
| 3 | 723 full-size thumbnails fetched on grid mount — **77.9 MB**, no `loading="lazy"` | `web/src/views/ReelsPage.tsx:311` | 2 attributes | ~97% of the initial pull | High |
| 4 | Compare tab recomputes the corpus-wide scoreboard every 3 s forever | `web/src/views/ComparePage.tsx:119` | 1 line | ~1.9 s CPU + 130 MB of reads per idle minute | High |
| 5 | `annotate()` is an unlocked read-modify-write; bulk archive **loses most flags** | `userstate.py:30` + `web/src/views/TablePage.tsx:80` | 3 lines + 1 | Correctness, not speed | High |
| 6 | OCR and vision sample frames under **different specs** — each deletes the other's cache | `extract/ocr.py:34` | 1 argument | Removes a permanent double-ffmpeg per reel the moment OCR is turned on | High |
| 7 | `backfill_vision.py` bypasses the vision semaphore; its guard covers `claude-cli` only | `scripts/backfill_vision.py:50,92` | 1 line | Prevents the already-measured 16 GB KV-cache blow-up | High |
| 8 | Six views each refetch the whole 466 KB corpus on every navigation | `web/src/lib/api.ts:164` | 3 lines | ~1.9 MB + ~400 ms per four-tab tour | Medium |
| 9 | 755 cards / rows / sidebar buttons in the DOM, uncapped | `ReelsPage.tsx:287`, `TablePage.tsx:429`, `ReaderPage.tsx:112` | ~6 lines | Render cost of every keystroke | Medium |
| 10 | `ReelsPage` is the one view whose filter/group/sort is **not** memoized | `web/src/views/ReelsPage.tsx:127` | 1 `useMemo` | Removes a re-sort + 8 KB join per keystroke; also fixes a listener churn | Medium |
| 11 | `build_master_index` loads **727 records to read 54 thumbnails** | `docs.py:72` | 2 lines | 0.128 s → 0.010 s per sync | Medium |
| 12 | `_log_tail` reads all of `run.log` to keep 150 lines, on every Sync poll | `api/routes/sync.py:55` | 3 lines | 10× per poll; grows to the 5 MB rotation ceiling | Medium |
| 13 | Every sync re-renders and rewrites **99.6 MB** of collection HTML, new reels or not | `sources.py:389` | 3-line guard | ~100 MB of write amplification per sync | Medium |
| 14 | 16,490 frames cached (**963.86 MB**) for 6 per reel ever sent to a model | `extract/frames.py:45` | see below | ~700 MB disk | Speculative |
| 15 | `_via_api` records the model it *asked for*, not the one that answered | `extract/vision.py:203` | 1 line | The provenance bug PR #12 fixed for the CLI, still live on the API path | High |
| 16 | `vision_semaphore` is fixed at the first limit the process ever sees | `ratelimit.py:28` | 2 lines | Long-lived API server only | Speculative |
| 17 | Sync page polls at a fixed 2 s while its own comment describes a backoff | `web/src/views/SyncPage.tsx:163` | 3 lines | ~21 MB/min of server file reads on an idle sync | Medium |

---

## 1. The `api` vision backend truncates every reel at 900 tokens

`extract/vision.py:197`

```python
msg = client.messages.create(
    model=cfg.extract.vision_model,
    max_tokens=900,
```

**Why it costs.** `STATUS.md` records this exact failure twice, measured, on the other backends:
`max_tokens: 1500` truncated 1 reel in 12 mid-`summary` and *all three retries failed identically*;
the bench arms were raised to 8000 for the same reason (`profiles.py:119` forces
`max_tokens = max(lc.max_tokens, 8000)`), and `config-local.yaml:42` sits at 4000. The `api` path
never moved. 900 is **4.4× below the 4000 the local path settled on**, and below the 1500 that was already found insufficient.

Three things make this worse than a stale constant:

| | |
|---|---|
| It is the **default when a key exists** | `vision_backend: auto` → `api` whenever `ANTHROPIC_API_KEY` is set (`vision.py:299`). Nobody opts in. |
| It is the path the docs recommend | `docs/OPTIMIZATION.md` calls it "The big win", ~15-20× fewer tokens. |
| It is the path the next planned job needs | `STATUS.md` next-step #2: re-extract 719 stale records via the Batch API, "needs `ANTHROPIC_API_KEY`, which is not set on this box". |

A truncated reply raises in `_parse_json`, so `with_retry` pays for three full API calls and stores
nothing. That is real money, unlike the claude-cli figures. UNMEASURED here (no API key on this box)
— but the truncation itself is measured on the sibling backends, and the token budget is the same
schema and the same 8-frame answer.

**Smallest fix.** Read the budget from config instead of hard-coding it — the field already exists
(`ExtractCfg` has no api-side twin, but `cfg.extract.vision_local.max_tokens` is the wrong home).
The lazy version is one line: `max_tokens=8000`, matching what `profiles.py:119` already forces for
every other arm, with the comment pointing at the measurement. `text_summary.py:80` carries the same
900 and should move with it.

**Verify.** With a key set:

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe -c "
import sys; sys.path.insert(0,'src')
from reels_scrap.config import Config
from reels_scrap.models import Reel
from reels_scrap.extract.vision import run_variant
cfg=Config.load('config.yaml'); cfg.extract.vision_backend='api'
r=Reel.load(cfg.data_dir/'<a reel with a long caption>.json')
v=run_variant(r,cfg,'api'); print(len(v['facts']), v['tokens'])"
```

Before: `RuntimeError: no JSON object in model output` (or a fact list cut short).
After: a complete record, `output` tokens well under the new ceiling. Then re-run the arm on 12
reels and compare the empty-variant count against `config-local.yaml`'s — the same 1-in-12 the
caption ablation measured.

## 2. Vision retries multiply — 9 attempts, 240 s each, on one reel

`extract/__init__.py:63-71` wraps `add_summary` in `with_retry(attempts=e.vision_max_retries)` (3).
`extract/vision.py:312` has its **own** loop: `for attempt in range(1, e.vision_max_retries + 1)`
(3 again). With `config-local.yaml:43` setting `vision_local_fallback: false` — STRICT LOCAL —
`_run_local` raises `RuntimeError` at the end of its three attempts, which the outer `with_retry`
happily retries.

| | Attempts | Each up to | Backoff |
|---|---|---|---|
| inner (`_run_local`) | 3 | `timeout: 240` s | 5, 10 s |
| outer (`with_retry`) | ×3 | | 5, 10 s |
| **worst case, one reel** | **9** | **~36 min** | + 45 s of sleeps |

This is the same shape as the failure `STATUS.md` says the `GpuContended` guard fixed — *"One reel
wasted instead of 9 attempts x 240s"*. That guard works, but only for the GPU-contention cause: it
fires from `processor_of()` reporting anything but `100% GPU`. **Every other cause — ollama
restarting, the model evicted, a malformed JSON reply, a read timeout on a genuinely slow reel —
still pays the full 9 × 240 s.** UNMEASURED (I did not sit through one); the arithmetic is on
measured constants from `config-local.yaml`.

The claude-cli path does not have this problem: `_via_cli` has no inner loop, so the outer 3 is the
only 3.

**Smallest fix.** The local backend already owns its retry policy. Give the outer wrapper one
attempt when the resolved backend is `local`, so the two loops stop composing — one line at the call
site in `extract/__init__.py`, e.g. `attempts=1 if _resolve_backend(e.vision_backend) == "local"
else e.vision_max_retries`.

**Verify.** The tests already monkeypatch `vision._via_local` (`extract/README.md` says so
explicitly). Point it at a counter that always raises and assert the count:

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe -m pytest tests -q -p no:warnings -k "local or retry"
```

plus a new check asserting `calls == 3`, not 9, with `vision_local_fallback: false`. Before the fix
that assertion reads 9.

## 3. The grid fetches 77.9 MB of thumbnails on mount

`web/src/views/ReelsPage.tsx:311-316`

```tsx
<img
  src={api.media(r.id, "thumbnail")}
  alt=""
  className={`h-56 w-full bg-surface0 object-cover ...`}
```

**MEASURED:** 723 thumbnail files totalling **77.9 MB**, average 105 KB, p90 228 KB. Every card is in
the DOM (finding #9), so every `<img>` starts loading at mount. About 20 are ever on screen. There
are **zero** occurrences of `loading=` anywhere under `web/src`. The API serves the original
full-resolution JPEG with a bare `FileResponse` (`api/routes/library.py:147-162`) into a slot
rendered at `h-56`.

**Smallest fix.** Two native attributes on that one tag: `loading="lazy" decoding="async"`. No
dependency, no virtualization, no downscale pass. ESTIMATE: initial pull drops to whatever is in the
viewport, ~2-3 MB. `web/src/views/HomePage.tsx:75` has the same tag for 8 images — worth matching for
consistency, not for savings.

**Verify.** DevTools → Network → filter `thumbnail`, hard-reload `/reels`, read "N requests /
X transferred" at the bottom before and after. Or `curl -s localhost:8000/api/reels | python -c
"import json,sys;print(len(json.load(sys.stdin)))"` for the card count, then compare the request
count to it.

## 4. The Compare tab recomputes the whole scoreboard every 3 seconds, forever

`web/src/views/ComparePage.tsx:119-131`

```tsx
const id = setInterval(() => {
  api.compareStatus().then((s) => { setBatch(s); if (!s.running) loadBoard(); })
}, 3000);
```

`if (!s.running)` is true whenever no batch is running — which is nearly always. The intent was
plainly "refresh once when a batch finishes".

**MEASURED:** `compare.scoreboard(cfg)` takes **0.15 s** and re-parses all 755 records (6.5 MB) per
call. At 20 calls/minute that is **~3 s of server CPU and ~130 MB of file reads per minute** for a
tab sitting idle — on the same single-worker uvicorn that serves the thumbnails.

**Smallest fix.** Fire only on the running→idle edge, the shape `DiscoverPage.tsx:62-70` already
uses: `setBatch((prev) => { if (prev?.running && !s.running) loadBoard(); return s; });`

**Verify.** Open `/compare`, leave it 60 s, then `grep -c "GET /api/compare/scoreboard"` in the
uvicorn access log. Before: ~20. After: 0.

## 5. `annotate()` loses writes under the bulk action that generates them

`userstate.py:30-41` is read-whole-file → mutate → write-whole-file, with no lock:

```python
def annotate(output_dir: Path, reel_id: str, patch: dict) -> dict:
    data = load_annotations(output_dir)
    ...
    _path(output_dir, ANNOTATIONS).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

`POST /api/reels/{id}/annotate` is a plain `def` handler, so FastAPI runs it in a threadpool —
genuinely concurrent. And `web/src/views/TablePage.tsx:80-83` fires one un-awaited POST per selected
reel:

```tsx
selIds.forEach((id) => api.annotate(id, { [key]: val }).catch(() => {}));
```

"Select all → Archive" is up to **755 concurrent read-modify-writes of the same file**. Last writer
wins, so most of the flags are silently dropped. This is a correctness bug, not a performance one,
and it fails quietly — the UI shows the optimistic state.

Second, smaller edge on the same lines: `write_text` truncates before it writes, so a crash mid-write
loses `annotations.json` outright. It is 700 bytes of irreplaceable user judgement.

**Smallest fix.** A module-level `threading.Lock()` held across the read and the write in
`annotate()` — three lines, and it fixes every caller at once rather than the one the report names.
Making the frontend `for … await` is a second line and makes the UI honest about the latency; the
lock is the one that must exist.

**Verify.**

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe -c "
import sys,concurrent.futures as cf; sys.path.insert(0,'src')
from pathlib import Path
from reels_scrap.userstate import annotate, load_annotations
out=Path('/tmp/annotest'); out.mkdir(exist_ok=True)
ids=[f'r{i}' for i in range(200)]
with cf.ThreadPoolExecutor(32) as ex: list(ex.map(lambda i: annotate(out,i,{'archived':True}), ids))
print(sum(1 for v in load_annotations(out).values() if v.get('archived')), 'of 200')"
```

Before: a number well under 200. After: 200.

## 6. OCR and vision sample frames under different specs, so each deletes the other's cache

`extract/ocr.py:34`

```python
frames = sample_frames(video, frames_dir, cfg.extract.frame_every_sec)
```

— no `max_width`, so it defaults to `0`. `extract/vision.py:82-85` passes
`max_width=cfg.extract.frame_max_width` (720 in every config). `sample_frames` keys its cache on
exactly those two values (`frames.py:60-65`) and **deletes the existing frames when the spec
differs**. `extract_all` runs OCR *before* vision (`extract/__init__.py:31,54`), so with both stages
on, every reel every run does:

1. OCR re-samples at native width, deleting the 720 px frames;
2. vision re-samples at 720 px, deleting the native ones.

Two full ffmpeg passes per reel, permanently, and the frame cache — the thing PR #9 exists to make
work — never hits again. The bug is the *same class* the frame-cache fix already caught: a sampling
parameter silently making the cache lie.

Currently **latent**: `ocr: false` in all five configs (`config.yaml:20`, `config-local.yaml:26`,
`config-claude.yaml:21`, `config-deep.yaml:21`, `config-fast.yaml:20`). It becomes a real cost the
day OCR is switched on — which `STATUS.md` next-step #5 contemplates ("order the OCR lines by frame
and re-run `--blank ocr`"). It would also invalidate all **963.86 MB** (MEASURED) of cached frames on
first run.

**Smallest fix.** Pass the same `max_width` OCR's sibling passes:
`sample_frames(video, frames_dir, cfg.extract.frame_every_sec, max_width=cfg.extract.frame_max_width)`.
One argument. Note this changes what easyocr reads (720 px instead of native), so it belongs behind
the `measuring-extraction-changes` skill's A/B before shipping — not because the cache fix is
doubtful, but because OCR recall at 720 px is unmeasured.

**Verify.** With `ocr: true` on one reel, run extract twice and watch `.frames.json`:

```bash
cat data/<id>_frames/.frames.json   # {"every_sec": 2, "max_width": 720} both times, not flipping to 0
ls data/<id>_frames/*.jpg | wc -l   # unchanged between runs
```

Before, the file alternates between `"max_width": 0` and `720` and the jpgs are rewritten each pass.

## 7. `backfill_vision.py` bypasses the vision semaphore, and its guard misses `local`

`scripts/backfill_vision.py:50-52` guards one backend:

```python
if backend == "claude-cli" and workers > 1:
    print("claude-cli throttles on parallel — forcing workers=1 …")
```

but `:85-93` runs `add_summary` directly in a `ThreadPoolExecutor`:

```python
def _one(r):
    add_summary(r, cfg)
```

`add_summary` does **not** take the semaphore — the gate lives in `extract_all`
(`extract/__init__.py:63`), which this script skips. So `--backend local --workers 5` puts five
concurrent 32k-context requests on the card. That is a measured failure in this repo already:
`config-local.yaml:52-54` sets `vision_concurrency: 1` because *"three in-flight requests at 32k ctx
multiply the KV cache and push a 9.4GB model off the 16GB card — every reel then read-timed out at
240s (2026-08-19)"*. The script can reproduce it with a flag.

`docs/SCALING.md` describes the semaphore as the thing that makes concurrency safe "however many
worker threads are in flight". For this script that sentence is not true.

**Smallest fix.** Wrap the body: `with vision_semaphore(cfg.extract.vision_concurrency): add_summary(...)`
— one line, and it makes the script obey the same config knob the docs point at, for every backend
including future ones. (Extending the `claude-cli` string check to `local` also works and is smaller,
but it re-encodes a policy that already lives in config.)

**Verify.** `--backend local --workers 5 --limit 5`, and `ollama ps` during the run: it should stay
at one in-flight request and `100% GPU`. Before the fix, `nvidia-smi` shows the VRAM climb and the
run ends in 240 s timeouts.

## 8. Six views each refetch the full corpus on every navigation

`web/src/lib/api.ts:164-168` is a bare `fetch` with no caching. `GET /api/reels` is called on mount
by `HomePage.tsx:29`, `ReelsPage.tsx:60`, `TablePage.tsx:38`, `KanbanPage.tsx:18`,
`ReaderPage.tsx:42` and `ComparePage.tsx:121`.

**MEASURED:** the response is **466 KB**; the server spends ~100 ms per call (`load_reels` is 0.134 s
for 755 records, measured directly). Overview → Reels → Table → Board is ~1.9 MB and ~400 ms of
re-parsing byte-identical data.

**Smallest fix.** One module-level promise in `lib/api.ts`, three lines, no dependency and no new
abstraction:

```ts
let _reels: Promise<ReelSummary[]> | null = null;
reels: (fresh = false) => (fresh || !_reels ? (_reels = get<ReelSummary[]>("/api/reels")) : _reels),
```

All six call sites keep working unchanged. The one thing the comment must say: it goes stale after a
sync, so `SyncPage`/`SourcesPage` call `api.reels(true)` when a run completes.

**Verify.** DevTools → Network, click through four tabs, count `/api/reels` requests. Before: 4.
After: 1.

Related, same page: `HomePage.tsx:27-33` pulls all 755 records to compute a star count and take 8
ids, when `stats.total_reels` is already on the line above and the star flags live in
`output/annotations.json` — **700 bytes**, already served at `GET /api/annotations` but absent from
`lib/api.ts`. Once the shared promise lands this fetch is free, so it is not worth its own change.
A genuine bug hides there though: `reels.slice(-8)` takes the last 8 of a list the server sorts by
*filename* (`deps.py:28`, `sorted(cfg.data_dir.glob("*.json"))`), so "Recently added" is alphabetical.
Sort by `timestamp` before slicing.

## 9. 755 cards, rows and sidebar buttons, uncapped

`ReelsPage.tsx:287-365` (grid), `TablePage.tsx:429-466` (755 `<tr>`), `ReaderPage.tsx:112-141`
(755 sidebar buttons). ESTIMATE: ~20 DOM nodes per card × 755 ≈ 15k nodes on `/reels`, re-rendered
on every keystroke in the search box. `KanbanPage.tsx:198` already solves this in this codebase with
a plain `.slice(0, 60)` per column.

**Smallest fix.** The pattern the repo already uses: `items.slice(0, shown)` with a "Show N more"
button per section. No virtualization library. Fixing #3 removes most of the *network* pain; this
removes the *render* pain, and the two compound.

**Verify.** DevTools → Elements, or `document.querySelectorAll('*').length` in the console on
`/reels`. Before ~15k; after, bounded by the cap.

## 10. `ReelsPage` is the one view that forgot its `useMemo`

`web/src/views/ReelsPage.tsx:127-160` filters, groups and sorts 755 records and joins an ~8 KB id
string on **every render** — including every keystroke and every star click:

```tsx
const filtered = reels.filter((r) => (!q || r.title.toLowerCase().includes(q.toLowerCase()) || ... ))
...
const expQ = filterActive ? `?ids=${filtered.map((r) => r.id).join(",")}` : "";
```

`TablePage.tsx:51-70` and `ReaderPage.tsx:50-67` already wrap the identical computation in `useMemo`;
`ReelsPage`'s own dropdown option lists at `:98-113` are memoized. This block is the outlier.
ESTIMATE: sub-millisecond in isolation — it matters because it forces the 755-card re-render in #9.

There is a second effect: `ReelsPage.tsx:163-180` lists `orderedIds` (a fresh array every render) in
its dependency array, so the `keydown` listener is torn down and re-added on every render. Memoizing
the block fixes that too.

**Smallest fix.** One `useMemo` around `:127-160`, keyed on the filter inputs — the exact shape
`TablePage` uses ten lines away. Hoist `const ql = q.toLowerCase()` out of the predicate while there.

**Verify.** React DevTools Profiler, type one character into the search box: before, the render
includes the sort; after, only the reconciliation.

## 11. `build_master_index` loads 727 records to read 54 thumbnails

`docs.py:72`

```python
for rec in load_records(cfg.data_dir, m.reel_ids)[:3]:
```

The `[:3]` is applied **after** loading every record in the manifest.

**MEASURED**, this corpus, 20 manifests:

| | Records loaded | Time |
|---|---|---|
| as written | 727 | 0.128 s |
| loading only what is used | 54 | 0.010 s |

Small in absolute terms — reported because it is the exact "whole-corpus load where a subset would
do" pattern, and because it runs on every sync and every `rebuild_all`.

**Smallest fix.** Not the obvious `m.reel_ids[:3]` — `load_records` drops records whose file is
missing, so slicing the ids first can yield 2 thumbnails where the current code yields 3 (this
actually differs on the live corpus: 52 vs 53 thumbnails). The correct minimal change is to stop
after three successful loads — a `for rid in m.reel_ids:` loop with a `break` once `len(thumbs) == 3`.

**Verify.**

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe -c "
import sys,time; sys.path.insert(0,'src')
from reels_scrap.config import Config; from reels_scrap.docs import build_master_index
cfg=Config.load('config.yaml'); t=time.perf_counter(); build_master_index(cfg); print('%.3fs'%(time.perf_counter()-t))"
```

and diff the resulting `output/collections/index.html` — the thumbnail count per card must not change.

## 12. `_log_tail` reads the whole log to keep 150 lines

`api/routes/sync.py:52-56`

```python
tail = p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
```

`run.log` rotates at 5 MB × 3 (`STATUS.md`, P0 slice). Polled by the Sync tab every 2 s (#17), and
by `SourcesPage` too.

**MEASURED** at today's 722 KB log:

| Approach | Time |
|---|---|
| `read_text().splitlines()[-200:]` | 2.3 ms |
| seek to `size - 65536`, decode, `[-200:]` | 0.2 ms |

ESTIMATE at the 5 MB rotation ceiling: ~16 ms per poll, ~8 polls/s of file reads across two open
tabs. It is not a bottleneck today; it is 10× and three lines.

**Smallest fix.** Seek to the last 64 KB before decoding. Guard the case where the file is smaller
than the window.

**Verify.** The timing snippet above, run against a log grown to 5 MB (`--limit`-free sync, or
`head -c 5000000 /dev/urandom`-style padding is not representative — use a real rotated log).

## 13. Every sync rewrites 99.6 MB of collection HTML whether or not anything changed

`sources.py:374-391` rebuilds the manifest **and** the collection doc for every source on every run:

```python
    # refresh membership manifest (full current list) + doc, even if nothing new
```

then `poll_all:478-479` rebuilds the master index on top.

**MEASURED**, rendering all 20 manifests in-process without writing:

| | |
|---|---|
| render time | **0.84 s** |
| HTML produced | **99.6 MB** |
| on disk today | `output/collections` = **111 MB**, largest `front-end.html` 19.0 MB, `index.html` 11.4 MB |

The size is base64 thumbnails inlined by `render/consolidated.py:174` (`data_uri`) — deliberate, the
docs are meant to be self-contained. The waste is not the rendering (0.84 s is nothing beside a
vision pass); it is **~100 MB of writes per sync**, every night, for collections where the membership
list is byte-identical to last run.

**Smallest fix.** A three-line guard in `poll_source`: skip `build_collection_doc` when
`res.ingested == 0` **and** the manifest just written equals the one already on disk. Both values are
already in hand at that point (`m.to_json()` vs `manifest_path(...).read_text()`).

**Verify.** Run `sync --only <source>` twice with nothing new and compare mtimes:

```bash
ls -l --time-style=full-iso output/collections/<slug>.html   # before and after the 2nd run
```

Before: mtime advances and 19 MB is rewritten. After: unchanged.

## 14. 16,490 cached frames for 6 per reel ever sent

`extract/frames.py:66-79` extracts one frame every `frame_every_sec` (2) for the **whole** video;
`extract/vision.py:87-90` then subsamples to `max_frames` (6).

**MEASURED:** 723 frame directories, **16,490 jpgs, 963.86 MB** — 22.8 frames per reel, 6 used.
ESTIMATE: ~74% of that (~700 MB) is decoded, scaled, JPEG-encoded and stored for nothing, in a
`data/` that is already 6.7 GB.

**Marked speculative on purpose.** ffmpeg decodes the video once either way, so the CPU saved is only
the surplus JPEG encodes, not the decode — and any change to *which* frames get sampled changes what
the model sees, which puts it squarely in `measuring-extraction-changes` territory rather than in a
free win. There is a safe half: OCR is the only consumer of the surplus frames, and it is off in
every config, so the ~700 MB is currently dead weight that could simply be pruned by a maintenance
script. I did not propose one — the repo has no such script and YAGNI applies until disk actually
hurts.

**Verify (the disk claim, already run).**

```bash
find data -name "frame_*.jpg" | wc -l
find data -name "frame_*.jpg" -printf "%s\n" | awk '{s+=$1} END {print s/1048576" MB"}'
```

## 15. The `api` backend records the model it asked for, not the one that answered

`extract/vision.py:203-204` builds `tokens` with no `model` key, so `_extract:357-362` falls back to
`cfg.extract.vision_model` — a wish, not a fact. This is exactly the bug PR #12 fixed for the CLI
path ("record the model that ran, not the one config asked for"; live, config said sonnet-4-6 and the
CLI ran `claude-opus-5`). The Anthropic response carries `msg.model`; it is discarded.

It also matters for money: `routes/exports.py:66` prices each record at `tokens["model"]`, and
`PRICES` is per family (opus $5/$25 vs sonnet $3/$15). A mislabelled record is mispriced by up to
1.7×.

**Smallest fix.** One key: `tokens["model"] = msg.model` alongside the usage numbers.

**Verify.** Run one reel on `api` and read the record: `python -c "...; print(Reel.load(p).tokens)"`.
The `model` field must be the wire id the API returned, and must differ from `vision_model` when the
config asks for an alias.

## 16. The vision semaphore is fixed at the first limit the process ever sees

`ratelimit.py:28-37` creates the semaphore once and logs a warning if a later caller wants a
different size. In the CLI that is correct and deliberate. In the long-lived API server it means the
first job to run — a sync on `config-local.yaml` (concurrency 1) — pins the ceiling for every later
Compare batch or profile-driven sync in that process, silently except for one log line.

**Speculative:** I found no case where this currently produces a wrong result, because every config
in the repo sets `vision_concurrency: 1`. It is listed so that the day a profile wants 2, the
symptom ("it ignored my setting") has a named cause. No change proposed — a resize would trade a
known ceiling for an unknown race, and the warning already exists.

## 17. The Sync page polls at a flat 2 s while its comment promises a backoff

`web/src/views/SyncPage.tsx:163-173`

```tsx
// 2s while live, 10s when idle — polling a dead sync is pure waste
const id = setInterval(tick, 2000);
```

The comment describes behaviour that was never written; the comment is the one lying. Each tick costs
the server the full `run.log` read from #12 plus `sources_state.json` (20 KB). ESTIMATE: ~21 MB/min of
server-side file reads on an idle sync tab.

**Smallest fix.** Make the code match its own comment — `setTimeout` recursion with
`s.live ? 2000 : 10000`.

Related leak, same concern, different file: `web/src/views/SourcesPage.tsx:143-153` starts a 2 s
`setInterval` that is cleared only when the sync reports `!running`. Navigate away mid-sync and it
polls for the life of the tab and calls `setState` on an unmounted component. `SyncPanel` in the
**same file** (`:15-36`) gets this right with a ref plus unmount cleanup — copy that.

**Verify.** Open `/sync` with no sync running, wait 60 s, `grep -c "GET /api/sync/status"` in the
access log. Before: ~30. After: ~6.

---

## What I checked and found healthy

The negative results are the point: several of these are exactly where an audit expects to find
something, and the code already handles it.

| Checked | Result |
|---|---|
| **Full-corpus load per API request** (`deps.py:28`) | **Healthy at this size. MEASURED: 0.134 s to `Reel.load` all 755 records** (0.081 s as raw `json.loads`). Not worth a cache; revisit past ~5,000 reels. |
| **Search index load per query** (`search.py:164-166`) | **Healthy. MEASURED: 33 ms npz + 9 ms meta + 0.4 ms matmul** on 5,860 × 384 vectors. The embedder is cached in a module global (`search.py:22`), which is the part that would have been expensive. |
| **`compare.scoreboard`** (`compare.py:247`) | **Healthy in itself: MEASURED 0.15 s over 690 reels with variants.** Its problem is the caller (#4), not the function. |
| **Incremental index reuse** (`search.py:64-83`) | **Healthy and well-reasoned.** Keys on a content hash of the indexed text, not mtime — so a Compare variant, an annotation or an `author_handle` backfill does not force a re-embed. The docstring explains why. This is the single best piece of waste-avoidance in the repo. |
| **Frame cache keyed on the sampling spec** (`frames.py:60-65`) | **Healthy.** `every_sec` and `max_width` are written to `.frames.json` and re-sampled on change. Only OCR's call site (#6) fails to pass the spec. |
| **Instagram calls are serial everywhere** | **Healthy. Verified by grep:** the only `ThreadPoolExecutor`s are `pipeline.py:111` (extract/render, vision gated behind the semaphore) and `scripts/backfill_vision.py:92` (vision, no IG). No IG request is ever made from a worker thread. `_enumerate_profile` (`sources.py:180-197`) pages serially with `time.sleep(1.0)`; `discover.Budget` (`discover.py:36-60`) enforces `min_interval: 3.0`, caps a run at 40 requests, and `kill()` ends the whole run on the first 429 — *"resume tomorrow, not in 5 seconds"*. Nothing here needs changing and nothing here should be parallelised. |
| **Run-start guards** | **Healthy, and the model for finding #2's fix.** `local_gpu_blockers` (`sources.py:395`) and `auth_blockers` both refuse to start before spending an Instagram request; `with_retry(fatal=...)` (`ratelimit.py:45-57`) refuses to retry a `GpuContended`. |
| **`backfill_vision` claude-cli guard** (`scripts/backfill_vision.py:50`) | **Healthy for the backend it names** — forces `workers=1` and says why. It just does not cover `local` (#7). |
| **`_frames_with_time` null-video guard** (`vision.py:76-80`) | **Healthy** — the None check runs before `data_dir / video_path`, with a comment naming the crash it prevents and a regression test. |
| **Sync index rebuild** (`sources.py:482-490`) | **Healthy.** One embedding pass for the whole sync, and only `if any(r.ingested for r in results)`. The per-source rebuild that cost ~70 min is gone. |
| **Search debounce** (`web/src/views/SearchPage.tsx:18-27`) | **Healthy** — a proper 300 ms debounce with `clearTimeout` cleanup. The model the other views should copy. |
| **`TablePage` / `ReaderPage` derived state** | **Healthy** — both correctly `useMemo`'d (`TablePage.tsx:51-70`, `ReaderPage.tsx:50-67`). Only `ReelsPage` (#10) is not. |
| **N+1 fetching per card** | **None found.** No card fetches its own data; the drawer fetches only the focused reel (`ReelsPage.tsx:386-390`). |
| **Video preloading** | **Healthy** — `<video>` renders only inside the open drawer for one reel (`ReelsPage.tsx:450-452`); grid cards carry no video element. |
| **`/api/tags`, `/api/knowledge`** | **Healthy** — both aggregate server-side and the UI consumes fixed-size slices. `KnowledgePage` slices every inner list explicitly. |
| **Note autosave** (`ReelsPage.tsx:562-568`) | **Healthy** — saves on blur, not per keystroke. |
| **Code splitting** (`App.tsx:6-18`) | **Checked and deliberately left alone.** One 293 KB chunk, all 13 views eager. ESTIMATE ~100-200 ms of parse on a localhost load. `React.lazy` + `Suspense` per route is machinery for a cost 265× smaller than finding #3. Not worth it. |

## See also

- [`../OPTIMIZATION.md`](../OPTIMIZATION.md) — token levers; finding #1 is the reason its headline
  recommendation currently cannot be taken as written.
- [`../SCALING.md`](../SCALING.md) — the semaphore design that finding #7 shows one caller escaping.
- [`../research/COSTS.md`](../research/COSTS.md) — what each cost figure means; finding #15 is why one
  of them can be mislabelled.
- [`../../STATUS.md`](../../STATUS.md) — the measured history this audit was written not to repeat.
