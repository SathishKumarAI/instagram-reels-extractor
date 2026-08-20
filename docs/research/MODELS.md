# The models

What each arm of the bench is, how it reads a reel, and what to expect from it
here. Numbers marked **measured** come from this machine; everything else is
stated as an expectation and is settled by
[`BENCH-2026-08-05.md`](BENCH-2026-08-05.md).

## What every model is asked to do

Identical for all eight arms — that is the point of the bench:

1. **Frames.** `sample_frames` cuts one frame every 2s from the cached mp4,
   downscaled to 720px wide, and keeps 6 spread across the reel
   (`extract/vision.py::_frames_with_time`). The frames are cached, so every arm
   sees the *same* images.
2. **Prompt.** One instruction asking for a JSON object: `genre`, `summary`,
   `tags`, `structured` (genre-appropriate fields) and `facts` — each fact tied to
   a frame and a timestamp. Local models additionally get `LOCAL_NUDGE`, which
   spells out the schema floors, because a 7B reads "3-8 facts" as "3".
3. **Call.** Cloud arms go through the Claude CLI; local arms POST to an
   OpenAI-compatible endpoint (`/v1/chat/completions`) served by Ollama, with the
   frames inline as base64 data URIs, `temperature: 0`, and a token budget.
4. **Parse.** The reply is scanned for JSON objects and the richest complete one
   wins — reasoning models emit a sketch, a correction and then the answer.
5. **Store.** The result becomes `reel.variants["<profile>"]`, never overwriting
   another model's.

Two things bit us and are worth carrying into any future model:

- **Context.** Six 720px frames are ~2.6k tokens each. The stock Ollama context of
  4096 rejects them outright, which is why every model is rebuilt at
  `num_ctx 32768` (`scripts/modelfiles/*.Modelfile`).
- **Thinking budget.** A reasoning model spends output tokens before it answers.
  At `max_tokens: 1500` qwen3-vl returned truncated JSON or nothing at all;
  at 4000 the same reel produced 6 facts in 24s. **Measured.**

## The set

| Profile | Model | Arch | Params | Quant | Native ctx | Role in the experiment |
|---|---|---|---|---|---|---|
| `claude-cli` | claude-sonnet-4-6 | cloud | — | — | — | reference arm |
| `reels-vision` | qwen2.5-VL 7B | `qwen25vl` | 8.3B | **Q8_0** | 128k | control — wrote the existing local records |
| `qwen3vl-8b` | Qwen3-VL 8B | `qwen3vl` | 8.8B | Q4_K_M | 262k | same family, one generation newer |
| `qwen3vl-4b` | Qwen3-VL 4B | `qwen3vl` | 4.4B | Q4_K_M | 262k | size ladder rung |
| `qwen3vl-2b` | Qwen3-VL 2B | `qwen3vl` | 2.1B | Q4_K_M | 262k | size ladder floor |
| `minicpm-v45` | MiniCPM-V 4.5 | `qwen3` + CLIP 527M | 8.2B | Q4_K_M | 41k | different family, OCR-strong |
| `gemma4-12b` | Gemma 4 12B | `gemma4` + CLIP 52M | 11.9B | Q4_K_M | 262k | largest with headroom |
| `deepseek-ocr` | DeepSeek-OCR 3B | `deepseekocr` | 3.3B | **F16** | 8k | specialist control |

Two contrasts are deliberately *not* confounded: `reels-vision` vs `qwen3vl-8b`
holds family and size roughly constant and changes the generation; `8b → 4b → 2b`
holds family and generation constant and changes size. Everything else in the
table changes more than one variable at once and is read as a hint, not a finding.

## Model by model

### `claude-cli` — Claude Sonnet 4.6 (the reference)
A large hosted multimodal model driven through the Claude Code CLI, which reads
each frame as an agentic `Read` turn. Slowest arm (**measured ~28s/reel**) and the
only one that costs anything (**$0.32/reel**, see [COSTS.md](COSTS.md)). It is the
reference not because it is assumed correct but because it is the arm the corpus
was built with — every other model is described relative to it.
Docs: <https://docs.claude.com/en/docs/about-claude/models>

### `reels-vision` — Qwen2.5-VL 7B, Q8_0 (the control)
The model that wrote the 641 stored local variants. Qwen2.5-VL uses a native
dynamic-resolution ViT so on-screen text survives without tiling tricks, and it
was quantised to Q8_0 rather than the default Q4 deliberately: 9.4GB instead of
6GB, and less quantisation damage to exactly the thing that matters here, reading
small text. Known weakness on this corpus: it will name a thing it cannot read —
it invented an anime title once. **Measured**: ~8s/reel, 5.8 facts.
Model card: <https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct> ·
Ollama: <https://ollama.com/library/qwen2.5vl>

### `qwen3vl-8b` / `4b` / `2b` — Qwen3-VL (the ladder)
The 2026 successor family, Q4_K_M, with a much larger native context (262k) than
we use. **These are reasoning models**: the reply contains a `reasoning` field and
the answer proper, which is why the budget matters (see above) and why per-reel
latency is higher than the parameter count suggests. The 8B is the direct upgrade
comparison to the control; 4B and 2B answer "how far down can you go before the
records stop being worth having".
Ollama: <https://ollama.com/library/qwen3-vl> ·
Family: <https://github.com/QwenLM/Qwen3-VL>

### `minicpm-v45` — MiniCPM-V 4.5
A Qwen3 8B language model with a separate 527M CLIP-family vision encoder — the
biggest vision tower in this set by an order of magnitude. The MiniCPM-V line is
built around document and on-screen text understanding, so it is the cleanest test
of "is the gap OCR strength rather than model size?". Smaller native context (41k)
than the qwen3-vl models, which is still four times what we send.
Model card: <https://huggingface.co/openbmb/MiniCPM-V-4_5> ·
Ollama: <https://ollama.com/library/minicpm-v4.5>

### `gemma4-12b` — Gemma 4 12B
The largest model that still leaves room for a 32k KV cache in 16GB. Tiny vision
tower (52M) attached to a big language model — the opposite trade to MiniCPM-V.
Expect stronger writing and world knowledge, and watch for whether that turns into
*confident* claims the frames do not support: a good language model is exactly the
thing that fills gaps plausibly.
Ollama: <https://ollama.com/library/gemma4>

### `deepseek-ocr` — DeepSeek-OCR 3B (the control that should lose)
Not a general VLM: an OCR system that compresses page images into vision tokens
for a small decoder. F16, 8k native context — the tightest budget in the set. It is
here as a boundary case: it should read on-screen text well and produce poor
summaries, and if it does not, that says something about how much of this task is
just reading.
Paper/repo: <https://github.com/deepseek-ai/DeepSeek-OCR> ·
Ollama: <https://ollama.com/library/deepseek-ocr>

## Knobs that change the answer

| Knob | Where | Effect |
|---|---|---|
| `max_frames` (6) | `config*.yaml` | more frames ≠ more substance — a 16-frame test produced subtitle fragments, not facts |
| `frame_max_width` (720) | `config*.yaml` | image tokens scale with pixels; 720 from 1080 costs ~2-3× fewer tokens with no visible loss for this task |
| `num_ctx` (32768) | `scripts/modelfiles/*` | below ~8k the frames do not fit at all |
| `max_tokens` (4000 local) | profile / `vision_local` | a reasoning model needs room to think *and* answer |
| `temperature` (0) | `_via_local` | repeatability: the same reel must give the same variant |
| `vision_local_two_pass` | config | read-then-structure. **Measured**: +0.94 facts, shorter summaries, fewer structured fields, 24% slower. Off |
| `LOCAL_NUDGE` | `extract/vision.py` | schema floors for local models only; adding it to the Claude prompt makes Claude worse |

## Adding a model

1. Add it to `models.yaml` with the contrast it tests — an arm with no contrast is
   GPU time spent on nothing.
2. `reels-scrap models pull <name>` — pulls the tag, rebuilds it at 32k context.
3. `reels-scrap bench run -p <name>` — same sample, same frames, resumable.
4. `reels-scrap bench report` — the numbers, then the explanation.

VRAM is the ceiling: 16.3GB, one model resident at a time. The runner serialises
arms and releases the GPU between them.
