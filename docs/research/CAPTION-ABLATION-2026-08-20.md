# Does the caption reach the model? — 2026-08-20

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

## Re-run

```bash
PYTHONUTF8=1 .venv-win/Scripts/python.exe scripts/ablate_caption.py -c config-local.yaml --limit 12
```

Writes `output/bench/caption-ablation.json` (summary + per-reel rows and hits).
