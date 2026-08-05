# Vision model bench — design (2026-08-05)

A research harness that runs many vision models over one fixed set of reels and
explains **why their outputs differ**. Companion docs: `docs/research/README.md`
(the running research log), `docs/BACKLOG-120.md` Epic M/N, `STATUS.md`.

## 1. Why

The corpus was extracted by two models — 644 reels by `claude-cli`
(claude-sonnet-4-6) and 25 by a local `reels-vision` (qwen2.5vl 7B q8) — and the
only comparison so far was 4 reels deep:

| backend | facts | tags | summary chars | structured fields | sec | cost |
|---|---|---|---|---|---|---|
| claude-cli | 7.0 | 6.0 | 286 | 4.25 | 19.2 | $1.34 |
| local | 5.0 | 5.0 | 205 | 1.75 | 7.9 | $0.00 |

Two problems with that. The sample is too small to separate models, and *fewer
facts* is a symptom, not an explanation. The open question is which property of a
model — size, family, quantisation, OCR strength — actually costs a claim, and
whether a 2026 open-weights model closes the gap that a 2025 one could not.

The current code cannot answer it: `vision_backend` is a closed set of three
strings, `local` means exactly one model, and `reel.variants` is keyed by backend,
so a second local model **overwrites** the first.

## 2. Scope

In: model profiles, model install, the bench runner, the per-model scoreboard, a
written analysis, and the Compare tab picking from N profiles.

Out (own slices): M2 inline reader diff, per-claim truth judging, model-mix
policy per collection (M13), anything that changes the default production backend
— the bench produces the evidence for that decision, it does not take it.

## 3. Architecture

Four units, each usable alone.

### 3.1 `profiles.py` — what a "model" is

```yaml
extract:
  vision_profiles:
    qwen3vl-8b:
      kind: local              # local | claude-cli | api
      model: qwen3-vl-32k:8b   # the ollama tag to run
      base_url: http://127.0.0.1:11434/v1
      num_ctx: 32768
      max_tokens: 1500
      timeout: 300
      notes: "2026 successor to the 7B baseline"
```

`resolve_profile(name, base_config) -> Config` returns a Config whose
`extract.*` fields are set for that one model, exactly as `cfg_for_backend()`
does today for `local`. Compatibility rules:

- `claude-cli`, `api` and `local` resolve even when no profile is declared —
  `local` from `extract.vision_local` (i.e. `config-local.yaml`), the other two
  from the base config. Every stored variant and every existing caller keeps working.
- A declared profile wins over the implicit one of the same name.
- `cfg_for_backend()` stays as a thin alias so `compare.py`, the CLI and the sync
  endpoint need no edit beyond the rename.

**Variants become keyed by profile name.** `reel.variants["qwen3vl-8b"]`. The two
existing keys (`claude-cli`, `local`) are already valid profile names, so no
corpus migration runs — 641 reels keep their variants.

### 3.2 `models.yaml` + `reels-scrap models` — install

A curated registry, not an arbitrary pull. Each entry carries the ollama tag, the
context the frames need, approximate VRAM, and **why it is in the set** — the
research value is in the contrast, not the count.

| profile | model | role in the experiment | ~VRAM |
|---|---|---|---|
| `reels-vision` | qwen2.5vl:7b-q8_0 (installed) | control — wrote the existing local records | 9.4 GB |
| `qwen3vl-8b` | qwen3-vl:8b | same family, one generation newer | ~8 GB |
| `qwen3vl-4b` | qwen3-vl:4b | size ladder rung | ~4 GB |
| `qwen3vl-2b` | qwen3-vl:2b | size ladder floor — where does it break | ~2 GB |
| `minicpm-v45` | minicpm-v4.5:8b | different family, OCR-strong | ~6 GB |
| `gemma4-12b` | gemma4:12b | largest with headroom left | ~9 GB |
| `deepseek-ocr` | deepseek-ocr:3b | specialist control: OCR without a generalist | ~3 GB |
| `claude-cli` | claude-sonnet-4-6 | cloud reference, reuses stored variants | — |

`models list` prints installed vs missing. `models pull <profile>` runs
`ollama pull`, then `ollama create <profile>-32k` from a generated Modelfile that
raises `num_ctx` — the same reason `reels-vision` exists at all: a stock 4096
context rejects six frames plus the prompt. Every pull is explicit; nothing
downloads implicitly during a run.

### 3.3 `bench.py` — the experiment

```
reels-scrap bench sample -n 30      # once: pick the fixed sample
reels-scrap bench run --profiles all
reels-scrap bench report
```

- **sample** — stratified over genre × collection, seeded (`--seed 0`) so it is
  reproducible, written to `output/bench/sample.json` and reused by every later
  run. One fixed sample is what makes the arms comparable.
- **run** — for each profile, for each sampled reel: reuse the **cached frames and
  transcript** and call only the vision step, so the single variable is the model.
  Models run one profile at a time (16GB VRAM, one resident model), with
  `keep_alive=0` between profiles so the GPU is actually released. Idempotent:
  a stored `(reel, profile)` pair is skipped unless `--force`. Every attempt
  appends a row to `output/bench/runs.jsonl` — elapsed, tokens, error — so a
  failed arm is visible instead of silently thinning a mean.
- **report** — see below.

Failure policy follows the pipeline's: one model failing a reel dead-letters that
pair with a reason and the run continues. A model that fails more than half its
reels is reported as unusable rather than averaged.

### 3.4 Scoreboard + written analysis

`compare.scoreboard()` already aggregates per variant key, so it becomes
per-model once keys are profile names. It gains, per profile: agreement against
the `claude-cli` arm (the existing containment matcher), the count of claims only
that model made, and elapsed/cost.

`bench report` writes `docs/research/BENCH-<date>.md`:

1. the metrics table (facts, tags, summary chars, structured fields, seconds, cost,
   disagreement vs reference);
2. a **written analysis** — Claude reads a bounded, stratified sample (~40) of the
   actual `only_a` / `only_b` claims and explains the pattern per model. The unit
   of explanation is a claim the model missed or invented, quoted. The prompt that
   produces it lives in `docs/research/prompts/` with every other build prompt.

Both are files on disk; the UI reads the same numbers through
`/api/compare/scoreboard`.

### 3.5 UI

Compare tab: the two hard-coded backends become a picker over declared profiles,
and the scoreboard table grows a row per profile. Nothing else in the UI changes
in this slice.

## 4. Data flow

```
sample.json ──┐
              ├─→ bench run ──→ reel.variants[profile]  ──→ scoreboard() ──→ /api/compare/scoreboard
models.yaml ──┘         └────→ output/bench/runs.jsonl  ──→ bench report ──→ docs/research/BENCH-<date>.md
```

Nothing new leaves the machine: local profiles hit `127.0.0.1:11434`, the
`claude-cli` arm reuses variants that already exist, and the analysis pass sends
only claim text — never frames, never cookies.

## 5. Testing

One runnable check per non-trivial unit, all offline:

- profile resolution — declared profile wins, implicit `local` still resolves from
  `vision_local`, unknown name raises.
- sampler — same seed gives the same 30 ids; strata proportions hold; asking for
  more reels than exist returns what exists.
- bench runner — with a stubbed vision call: skips stored pairs, `--force`
  re-runs, a failing profile records an error row without killing the run.
- scoreboard — groups by profile name, disagreement computed against the named
  reference.
- report — renders from a fake corpus with the analysis pass stubbed.

## 6. Risks

- **VRAM.** 16.3GB, one model resident. The runner serialises profiles; a model
  that does not fit is a config error, not a crash mid-run.
- **Registry drift.** `models.yaml` names tags that must exist on ollama; `models
  pull` fails loudly on a bad tag rather than silently skipping an arm.
- **Analysis is a model reading models.** The written report is grounded in quoted
  claims and shipped next to the raw metrics, so a wrong narrative is checkable
  against the numbers.
- **Cost.** Local arms are $0 and ~3.5h of GPU; the Claude arm reuses stored
  variants, so it is $0 unless a sampled reel lacks one.
