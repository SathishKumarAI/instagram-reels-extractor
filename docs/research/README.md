# Research — vision model bench

Which vision model should read a reel, and **why** do models disagree about what a
reel says? This folder is the running record: the plan, the prompt behind every
build step, and the measured results.

## Map

| File | What it holds |
|---|---|
| `../superpowers/specs/2026-08-05-vision-model-bench-design.md` | the design that was approved before any code |
| `PLAN.md` | phases, status, what each phase must prove |
| `prompts/` | one file per build step: the prompt written **before** the code |
| `MODELS.md` | every model: architecture, role in the experiment, links, and the knobs that change its answer |
| `UI-TABS.md` | every tab: what it is for, what it reads, the gotcha |
| `COSTS.md` | what each cost number means and where it is produced |
| `BENCH-<date>.md` | measured results + the written why-they-differ analysis |
| `../WORKFLOW-RESEARCH.md` | earlier diagnosis: transcript/OCR coverage gaps |

## Method

1. One fixed, stratified sample of reels (`output/bench/sample.json`), seeded and
   reused by every arm — the models are the only variable.
2. Cached frames and transcripts are reused, so two models see identical input.
3. Every model's output is stored as a named variant on the reel
   (`reel.variants["<profile>"]`), never overwriting another model's.
4. Metrics are computed by code; the narrative is written from quoted claims that
   the models actually disagreed on, and ships next to the numbers so it can be
   checked against them.

## Rules this project keeps

- **Nothing implicit.** Model downloads are explicit commands, never triggered by
  a run.
- **Failures are data.** A model that fails a reel gets an error row, not a
  quietly thinner average.
- **The bench does not decide.** It produces evidence; changing the default
  production backend is a separate, deliberate change.
