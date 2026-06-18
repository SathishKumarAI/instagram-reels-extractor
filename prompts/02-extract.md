# Layer 02 — Extract

You are a multimodal-extraction engineer. Your objective is to build the
`extract/` package and the genre-typing in `structure/genres.py`: pure
per-modality functions that enrich an existing `Reel` in place with a transcript,
on-screen text (OCR), an AI visual summary (Claude), and structured genre-typed
fields where every fact carries frame/timestamp provenance.

<context>
  <depends_on>
    Layers 00–01 exist. A `Reel` already has media on disk (`video_path`,
    `thumbnail_path`) and metadata. Frames/audio caches go under
    `paths.input_media` via `frames_dir(id)`. Whisper + model caches under
    `paths.input_cache`.
  </depends_on>
  <boundary>
    `extract` enriches a `Reel` IN PLACE with pure functions, one per modality.
    Each function takes a `Reel` (+ config) and returns the same `Reel` with new
    fields filled. No scraping, no rendering, no concurrency (that's Layer 08).
    Each modality is independently toggled by `config.extract.*` and idempotent
    (skip if its field is already populated).
  </boundary>
  <provenance_principle>
    Anti-hallucination by construction: every `Fact` records the `timestamp`
    (seconds) and `frame` index it was read from, so a reviewer can scrub the
    reel to that exact moment to verify. OCR strings and vision facts must be
    traceable to a sampled frame.
  </provenance_principle>
  <claude_backends>
    Vision default backend is `claude-cli` (`config.extract.vision_backend`):
    shell out to `claude -p` with the prompt + frame images, using the user's
    subscription (no API key). Fallback backend `api` uses `ANTHROPIC_API_KEY`
    with the Anthropic SDK. Default vision model `claude-sonnet-4-6`
    (`config.extract.vision_model`); `claude-opus-4-8` for max quality.
  </claude_backends>
</context>

## Instructions
1. **`extract/frames.py`.** `sample_frames(reel, config) -> list[FrameRef]`:
   sample one frame every `config.extract.frame_every_sec` seconds from
   `reel.video_path` (imageio/ffmpeg), write JPGs to `frames_dir(id)`, and return
   refs `{index, timestamp, path}`. Idempotent: reuse existing frames. Used by
   both OCR and vision so frames are sampled once.
2. **`extract/transcript.py`.** `transcribe(reel, config) -> Reel` using
   faster-whisper (`whisper_model`, `whisper_device`, `whisper_language`,
   cache under `paths.input_cache`). Fill `reel.transcript` (segments with
   start/end/text) and `reel.transcript_text`. **Handle no-audio reels:**
   detect a missing/silent audio track (no audio stream, or empty/near-silent),
   skip cleanly, leave transcript empty, and record a skip in the `RunReport` —
   never crash or hallucinate text. Extract audio to `audio_path` only if needed.
3. **`extract/ocr.py`.** `read_on_screen_text(reel, config) -> Reel` using
   easyocr over the sampled frames (reuse `frames.sample_frames`). Dedupe
   repeated text across consecutive frames; fill `reel.ocr_text`. Keep the
   frame index/timestamp association available so the genre step can attach
   provenance.
4. **`extract/vision.py`.** `summarize_visual(reel, config) -> Reel`:
   - build the frame set via `frames.sample_frames`;
   - `claude-cli` backend: write a prompt instructing Claude to produce a clean
     visual summary of the reel from the frames + transcript + caption, and to
     extract discrete facts each tagged with the frame/timestamp it came from;
     invoke `claude -p` with the images attached; parse the response.
   - `api` backend: same prompt via the Anthropic SDK with
     `config.extract.vision_model` and the frames as image blocks.
   Fill `reel.summary` and append provenance-bearing `Fact`s to `reel.facts`.
   **Resilience:** on CLI failure (e.g. empty-stderr throttle) raise/catch
   `VisionUnavailable`, SKIP the vision step for that reel, record it in the
   `RunReport`, and continue — never abort the batch.
5. **`structure/genres.py` — genre → typed fields.** `classify_and_structure(
   reel, config) -> Reel`: infer `reel.genre` (e.g. tutorial | product |
   educational | recipe | news | other) from caption/transcript/summary, then
   populate `reel.structured` with genre-specific typed fields, e.g.:
   - tutorial → `{steps: [...], tools: [...], difficulty}`
   - product → `{product_name, price, features: [...], cta}`
   - recipe → `{ingredients: [...], steps: [...], time, servings}`
   - educational → `{key_points: [...], definitions: {...}}`
   Each extracted claim becomes a `Fact` with the `timestamp`/`frame` it was
   sourced from (carried over from OCR/vision frame refs). Keep classification
   deterministic where possible; use the vision summary as input, not a second
   LLM call unless `vision` is enabled.
6. **Pipeline wiring (sequential for now).** Add an `extract(reel, config)`
   orchestration that runs the enabled modalities in order
   (frames→transcript→ocr→vision→genre), each guarded by its `config.extract.*`
   toggle and its idempotency check, saving the enriched `Reel` back to
   `output/reels/<id>.json`. Concurrency comes in Layer 08; here it is linear.
7. **Tests.** `tests/test_extract.py`: frame sampling count for a known duration
   (mock the reader); transcript skip path on a no-audio fixture; OCR dedupe
   across duplicate frames; vision fallback returns a `Reel` with empty summary +
   a recorded skip when the `claude` subprocess is mocked to fail; genre
   classifier maps a sample transcript to the right genre and emits `Fact`s with
   non-null `timestamp`/`frame`.

## Constraints
- MUST keep each modality a pure, independently-toggled, idempotent function.
- MUST attach `timestamp` + `frame` provenance to every extracted `Fact`.
- MUST handle no-audio reels by skipping transcription cleanly (no hallucinated
  text, no crash).
- MUST default vision to the `claude-cli` backend and degrade to skip+record on
  CLI failure; only use the `api` backend when configured.
- MUST sample frames once and share them between OCR and vision.
- MUST resolve all paths through `core/paths`; caches under `input/cache`,
  frames under `input/media`.
- MUST NOT scrape, render, or add concurrency in this layer.
- MUST NOT fabricate facts the frames/transcript don't support.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`extract/frames.py`, `extract/transcript.py`, `extract/ocr.py`,
`extract/vision.py`, `structure/genres.py`, the extract orchestration addition,
and `tests/test_extract.py`. Include the exact `claude -p` invocation used for
vision (flags + how frames are attached). End with the commands to add deps
(`faster-whisper`, `easyocr`, `imageio[ffmpeg]`, and the Anthropic SDK for the
api fallback) and run the tests.

Reason briefly in a `<thinking>` block first, then output the files.
