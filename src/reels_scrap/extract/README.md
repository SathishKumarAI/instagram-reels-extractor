# extract/ — a downloaded reel becomes a typed record

Read this table instead of the code.

| Change | File |
|---|---|
| What the model is **told** — schema, field rules, per-backend nudges | `prompts.py` |
| What the caption/transcript **look like** in the message (trimming, hashtags) | `prompts.py` |
| Reading the model's answer — JSON salvage, tags, facts, fragments | `normalise.py` |
| Which backend runs, retries, GPU-contention bail-out, provenance | `vision.py` |
| Frame sampling and caching | `frames.py` |
| Whisper transcript | `transcript.py` |
| Text-only records (RSS/arXiv/GitHub — no video) | `text_summary.py` |
| easyocr over frames | `ocr.py` |
| Stage order and which stages are optional | `__init__.py` |

## Rules that keep the table true

- `prompts.py` holds **no** HTTP and no reel mutation; `normalise.py` holds no
  prompt text. Tuning the prompt is one small file, never a 650-line read.
- `vision.py` re-exports the old private names (`_apply`, `_parse_json`,
  `_prompt_header`, …) under `__all__`. They moved in the 2026-08-20 split;
  callers and tests still import them from `vision`.
- Every backend returns the **same** parsed-JSON shape, so a record is
  schema-identical whichever model made it. Provenance lives in `reel.tokens`
  (`backend`, `model`).
- `LOCAL_NUDGE` goes to the local backend only. A 7B reads "3-8 facts" as "3";
  Claude already fills the schema and a shorter prompt is a cheaper prompt.
- Heavy imports (`requests`, `anthropic`, `easyocr`) stay inside functions — a
  missing optional dep degrades one feature, never the run.

## Traps

- `ocr.py` writes `reel.ocr_text`; since 2026-08-20 `prompts.py` feeds up to
  `OCR_LINES = 15` of them to the model. The stage is still **off** in every config,
  and the cap is measured, not guessed: 40 lines cost 1.5 facts/reel
  (`docs/research/OCR-IN-PROMPT-2026-08-20.md`). It is still not in the search index.
- `_run_local` looks up `_via_local` per attempt on purpose: tests and the bench
  monkeypatch `vision._via_local`, and a hoisted reference misses the patch.
