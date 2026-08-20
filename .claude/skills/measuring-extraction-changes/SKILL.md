---
name: measuring-extraction-changes
description: Use when about to change anything that alters what this repo's vision/text extraction produces — the prompt, the model or profile, frame resolution or count, max_tokens, OCR/transcript inputs — or when a record is missing something (a link, a sponsorship marker, on-screen fine print) and the cause is unknown.
---

# Measuring an extraction change

A prompt or model change that is not measured is a guess with a commit message.
The corpus is 755 reels and the local arm is free, so the measurement is minutes.

## The rule

**Same reels, same metric, before and after.** Never compare a new run against a
number from a different sample, a different limit, or a different day's config.
If the sample changed, say so and re-run the baseline.

## The harness

`scripts/ablate_caption.py` runs each reel twice on the **same cached frames**:

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe scripts/ablate_caption.py \
  -c config-local.yaml [--backend NAME] [--frame-width N] [--no-blind] \
  [--limit 12] [--out my-arm.json]
```

| Flag | Use it for |
|---|---|
| *(none)* | Does the caption matter? Second arm blanks the caption. |
| `--backend minicpm-v45` | Which model? Any profile or `models.yaml` name. |
| `--frame-width 1440` | Which resolution? |
| `--no-blind` | Comparing two runs, not testing the caption — halves the time. |
| `--out NAME.json` | Keep arms side by side under `output/bench/`. |

Reel selection is deterministic (sorted by marker count), so `--limit 8` is always
the same 8 reels. That is what makes two runs comparable.

## Procedure

1. **Baseline first.** Run the arm you are about to change, unchanged. Keep the
   JSON — `cp output/bench/caption-ablation.json output/bench/<name>-before.json`.
2. **Change one thing.** Prompt text, or model, or width — not two.
3. **Re-run and compare on the shared reels**, not on the summary line: the
   summary moves when the sample or `--limit` moves.
4. **Read the per-reel rows.** Report reels that got *worse*; a mean hides them.
5. **Write it down** in `docs/research/<TOPIC>-<DATE>.md`: method, the table,
   and a "ceilings, stated" section. Then update `STATUS.md`.

## Split the metric before you believe it

An aggregate rewards volume. The harness reports `by_kind`:

| kind | what it is | weight |
|---|---|---|
| `link` | a URL or `@handle` — something the reel points at | **judge on this** |
| `sponsorship` | `#ad`, `#sponsored`, `#partner`, `#collab`, `#gifted` — who paid | **judge on this** |
| `tag` | one of forty topical hashtags | context only |

Measured 2026-08-20: an aggregate "caption marker recall" moved 0.169 → 0.453 and
the change looked like a win. Split by kind, links had been 6/7 before the change
and **sponsorship had gone 2/17 → 1/17** — the prompt that "improved recall" buried
the one hashtag class that matters. A second prompt took sponsorship to 15/17.
`minicpm-v45` had meanwhile scored 30/30 on one reel by dumping the whole hashtag
block into `structured.links` having barely read the reel.

**If a change makes a number go up, ask which sub-population moved.**

## Traps in this repo

- **Frames are cached** in `data/<id>_frames` and keyed on `{every_sec, max_width}`
  (`extract/frames.py`). Older frame dirs written before that key existed get
  re-sampled once. If you bypass `sample_frames`, you will measure the old pixels.
- **The GPU runs one model at a time.** Between arms call
  `bench._release_gpu(cfg)` or ollama offloads to CPU and every reel dies on the
  240s timeout — that failure looks like "the model is bad", it is not.
- **A truncated JSON reads as a bad model.** `no JSON object in model output` with
  the text cut mid-`summary` is `max_tokens`, not capability.
- **`$0` is only the local arm.** `--backend claude-cli` costs ~$0.34/reel; say
  the price in the plan before running it.

## What "done" looks like

A table with the same denominator in every row, a named regression count, and a
sentence saying what was *not* measured (usually: the Claude arm, and the 719
stored records that predate the change).
