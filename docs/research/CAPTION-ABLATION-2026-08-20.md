# Does the caption reach the model? — 2026-08-20

> **Correction, same day.** The headline below ("recall 0.169 → 0.453") counts every
> caption marker equally, and a caption ends in forty topical hashtags. Splitting the
> metric by marker kind showed most of that movement was hashtag copying, not
> comprehension — one model scored 30/30 on a reel by dumping the whole hashtag block
> into `structured.links`. The numbers that matter, and the second prompt change they
> forced, are in **"What the split metric showed"** at the end. Read that section as
> the result; this one as how it was found.

The 08-06 bench ended with an open question: every local arm missed caption-derived
claims (`#ad`, sponsor handles, links). Two explanations fit — the caption never
arrives, or it arrives and the model ignores it. Reading `_prompt_header` cannot
tell them apart, so this measures it.

## Method

`scripts/ablate_caption.py`. Each reel runs **twice on the same cached frames**:
once as stored, once with `caption` blanked. The metric is a **caption-only
marker** — a `#hashtag`, `@handle` or URL that appears in the caption and *not* in
the transcript, the stored on-screen text or the title, so the model can only have
learned it from the caption. Recall = markers found anywhere in the produced record
(summary, key points, facts, tags, on-screen text, structured fields).

Backend `local` (`reels-vision`, qwen2.5vl 7B q8), 12 reels chosen by marker count,
GPU free, `$0`.

## Result: the caption arrives and is used — the gap is recall

| arm | markers found | recall |
|---|---|---|
| with caption | 50 / 296 | **0.169** |
| caption blanked | 11 / 296 | 0.037 |

Blanking the caption costs 4.5× the markers, so delivery was never the problem.
Facts per reel barely moved (7.09 → 7.55), i.e. without the caption the model
produces just as many claims — they are simply about something else.

## Two fixes, measured on the same 11 reels and the same 296 markers

1. **The schema now says the caption is evidence.** `SCHEMA_INSTRUCTION` asks for
   every URL, `@handle`, repo/tool name, promo code, price and sponsorship marker
   copied verbatim into `structured.links` or into a fact; `LOCAL_NUDGE` names
   `links` as a required field.
2. **`max_tokens` 1500 → 4000** in `config-local.yaml`. One reel of 12 failed all
   three attempts with the JSON cut mid-`summary` — a truncation the sync would
   have dead-lettered silently. The bench arms were raised to 8000 for this reason
   in August; the sync config was never updated.

| arm | markers found | recall |
|---|---|---|
| before, with caption | 50 / 296 | 0.169 |
| **after, with caption** | **134 / 296** | **0.453** |
| after, caption blanked | 10 / 296 | 0.034 |

2.7× improvement, and the blind arm stays at the floor — the gain is the caption
being *read*, not the model guessing better. **3 of the 11 reels lost a marker they
had before** (`DNLSDt0gYGC`, `DONQIlEjC5z`, `DRM18FrkUSz`); the change is a large
net gain, not a uniform one.

## Ceilings, stated

- Recall is 0.45, not 1.0. A caption with 40 hashtags will never be fully copied
  into a 6-fact record, and it should not be — the metric counts every marker
  equally, including tag spam.
- Only the local backend was measured. The Claude arm is likely already higher and
  the same prompt change applies to it, unmeasured.
- Two reels still hit an attempt-1 truncation at 4000 tokens and succeeded on
  retry. If that becomes common, raise it again rather than adding retries.
- The metric is presence-anywhere, not correctness: a URL copied into the wrong
  fact still counts.

## What the split metric showed

A marker is now classified: a **link** (URL or `@handle`) is something the reel points
at; a **sponsorship** marker (`#ad`, `#sponsored`, `#partner`, `#collab`, `#gifted`)
says who paid; a **tag** is one of forty topical hashtags and copying the block whole
is not comprehension. Judge on link and sponsorship; tag recall is context.

Same 7 reels, same markers, four arms:

| arm | link | sponsorship | tag | facts |
|---|---|---|---|---|
| before any prompt change (`reels-vision`) | 6/7 | **2/17** | 25/175 | 5.29 |
| after v1 prompt ("copy identifiers verbatim") | 7/7 | **1/17** | 50/175 | 5.86 |
| after v2 prompt (below) | 7/7 | **15/17** | 63/175 | 6.14 |
| after v2 prompt, `minicpm-v45` | 7/7 | **15/17** | 63/175 | 6.57 |

Two things the aggregate number had hidden:

1. **Links were nearly fine already** — 6/7 before any change. The v1 prompt's
   apparent 2.7× gain was tag copying.
2. **v1 made sponsorship *worse*** (2/17 → 1/17). Lumping `#ad` in with "copy every
   identifier into `structured.links`" buried the one hashtag class that matters
   among the thirty-nine that do not.

**v2 prompt**: `structured.links` is URLs and `@handles` **only**; topical hashtags go
to `tags` without the `#`; a sponsorship marker is called out as an exception and must
be **stated as a fact**. Sponsorship recall 1/17 → **15/17**, and facts per reel rose
too (5.86 → 6.14) — the model stopped spending output on hashtag lists.

## Model and resolution, measured on the same harness

| arm | link | sponsorship | facts | on-screen lines | sec |
|---|---|---|---|---|---|
| `reels-vision` @720 (default) | 7/7 | 15/17 | 6.12 | 8.12 | 12.0 |
| `minicpm-v45` @720 | 7/7 | 15/17 | 7.00 | 8.38 | 11.9 |
| `reels-vision` @1440 | — | — | 5.67 | 4.50 | 10.4 |

- **Resolution: no.** Doubling frame width lost ground on every metric (aggregate
  recall 0.302 → 0.262 on the shared reels, fewer facts, half the on-screen lines).
  More pixels buy more image tokens, not more reading. `frame_max_width` stays 720.
  This was only measurable after fixing the frame cache, which ignored `max_width`
  and would have answered "no effect" for the wrong reason.
- **Model: no change.** On the metrics that matter the two arms are identical
  (7/7, 15/17). `minicpm-v45` adds ~0.9 facts and a longer summary at the same
  speed — real, but not worth moving the default the entire stored corpus was
  written with. Revisit if facts-per-reel becomes the goal.

## Re-run

```bash
# the caption question (two arms: as stored vs caption blanked)
PYTHONUTF8=1 .venv-win/Scripts/python.exe scripts/ablate_caption.py -c config-local.yaml --limit 12

# a model or a resolution (one arm each, compare the JSONs)
... scripts/ablate_caption.py -c config-local.yaml --backend minicpm-v45 --limit 8 --no-blind --out minicpm.json
... scripts/ablate_caption.py -c config-local.yaml --frame-width 1440 --limit 8 --no-blind --out w1440.json
```

Writes `output/bench/<name>.json` — summary (including `by_kind`) plus per-reel rows
and the exact markers hit. Release the GPU between arms (`bench._release_gpu(cfg)`).
