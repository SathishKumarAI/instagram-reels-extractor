# The OCR stage wrote to nothing — 2026-08-20

`extract/ocr.py` runs easyocr over the sampled frames and writes `reel.ocr_text`.
Nothing read that field: not the prompt, not the search index, not the UI. 23 reels
carry it (55–103 lines each) from runs when the stage was enabled, and those same
reels have **zero** `on_screen_text` — the model's own reading was never asked for
back then, and the OCR that was collected went nowhere.

So: wire it into the prompt, or delete the stage. This measures which.

## Method

`scripts/ablate_caption.py --blank ocr` — same two-arm harness, different input
under test. A **marker** here is an OCR line the caption and transcript do NOT
contain (≥8 normalised chars), so reproducing one means it came from the OCR block
or from the model reading the frame itself. Both arms see the same frames; only the
OCR block differs. Local backend (`reels-vision`), 4 reels usable on all arms,
160 markers, `$0`.

## Result: it is used, and it costs claims

| arm | OCR lines reproduced | facts/reel |
|---|---|---|
| no OCR in prompt | 2/160 (0.013) | **7.00** |
| OCR, 40-line cap | 41/160 (0.256) | 5.50 |
| **OCR, 15-line cap (shipped)** | 31/160 (0.194) | 6.50 |

Two readings, both true:

- **The model does use it.** 0.013 → 0.256 is not noise; without the block those
  lines essentially never appear, so the VLM was not reading that small print on
  its own.
- **It crowds out reasoning.** 40 noisy, unordered lines cost 1.5 facts per reel —
  and on one reel (`DZbIEwVR-OH`) the model returned **0 facts** with the block and
  6 without. Halving the block recovers most of that (6.50) while keeping most of
  the gain.

## What shipped

- `prompts.prompt_header` includes up to `OCR_LINES = 15` lines, labelled
  "unordered, may contain errors … ignore what the frames contradict", and says
  how many were dropped rather than silently truncating.
- **The stage stays OFF** in every config (`extract.ocr: false`). Nothing changes
  for the default pipeline; enabling OCR now actually does something.

## Ceilings, stated

- 4 reels, one model, one prompt. Small.
- 0.5 facts/reel is still a real cost. If facts matter more than verbatim small
  print for your use, leave OCR off — that is the shipped default.
- easyocr is CPU-only here and adds seconds per reel before any of this applies.
- Untested: whether feeding OCR to the *Claude* arm behaves the same, and whether
  ordering the lines (by frame, instead of easyocr's order) removes the fact cost.
  That is the next thing to try if anyone wants OCR on by default.
