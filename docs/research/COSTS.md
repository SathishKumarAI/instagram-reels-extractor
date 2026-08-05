# What the cost numbers mean

Three different things in this app are called "cost". They are not
interchangeable, and one of them is not money at all. This page says exactly
where each number comes from, so a figure on screen can be checked.

## The short answer

| Backend | Number shown | What it is | Money actually moved |
|---|---|---|---|
| `claude-cli` | `tokens.cost_usd` | the CLI's own `total_cost_usd` for that turn — what the same turn would cost **on the API** | **none** on a Claude subscription |
| `api` | computed from `msg.usage` | real token usage × published sonnet prices | yes, billed per call |
| local (`reels-vision`, `qwen3vl-*`, `minicpm-v45`, `gemma4-12b`, `deepseek-ocr`) | `0.0` | nothing is billed; it runs on the RTX 5070 Ti | none (electricity only) |

Measured on the bench sample: **claude-cli ≈ $0.31 per reel**, every local model
**$0.00 per reel**. Corpus-wide the same estimate totals ~$182 across 674 reels —
that is the price the work *would* have had on the API, not a bill anyone paid.

## Where each number is produced

**`claude-cli`** — `extract/vision.py::_via_cli` runs
`claude -p … --output-format json` and reads the envelope:

```python
tokens = {
    "input": u["input_tokens"],                 # fresh tokens this turn
    "cache_read": u["cache_read_input_tokens"], # ~10% price, mostly the CLI's own prompt
    "cache_creation": u["cache_creation_input_tokens"],
    "output": u["output_tokens"],
    "cost_usd": env["total_cost_usd"],          # the CLI's own figure
}
```

Two consequences worth knowing:

1. **`input` is an upper bound, not the vision call.** It counts the CLI's system
   prompt, its tool schemas and the agentic Read turns that fetch each frame. For
   a true per-call number use `vision_backend=api`, where `msg.usage` is exactly
   the request.
2. **`cost_usd` is a price, not a charge.** On a subscription no money moves. It
   is still the honest number for comparing against a local model, because it is
   what the same work costs when you have to buy it.

**`api`** — `_via_api` prices the real usage at `$3/M` input and `$15/M` output.
That is a hard-coded sonnet rate: if the model or the price list changes, this
number silently goes stale. It is the only path where the figure equals a bill.

**local** — `_via_local` sets `cost_usd: 0.0`. No guess about electricity, GPU
depreciation or your time: the app only reports what it can actually measure.
A 20-second reel on the 5070 Ti costs a few watt-hours, which is real but is not
a number this project has any business inventing.

## Where each number is shown

| Surface | Figure | Note |
|---|---|---|
| Compare → Scoreboard | `$/reel` and `$ total`, per model | with the footnote repeating this page's summary |
| Compare → per-variant card | that one run's `cost_usd` | a single reel, one model |
| Reels tab header | corpus-wide tokens + estimated cost | `/api/stats`, all 674 reels, all backends |
| `bench report` | `$/reel` per arm, on the 30-reel sample | `docs/research/BENCH-*.md` |

The scoreboard used to render the raw float (`$13.2164`), which reads like a much
bigger number than it is. It now formats to two decimals — four when the figure is
under a cent — and always shows the per-reel figure beside the total.

## Reading it honestly

- **Compare per-reel, not totals.** A total is a function of how many reels an arm
  happened to run. `claude-cli` at $0.31/reel and a local model at $0.00/reel is
  the comparison; "$13.22 vs $0.00" is an artefact of the sample.
- **A local model is free, not cheap.** The trade is quality and your GPU time —
  which is what `docs/research/BENCH-*.md` measures.
- **`/api/stats` is an estimate over mixed provenance.** 644 of the 674 reels were
  extracted by Claude and 30 by local models; the corpus figure prices the Claude
  ones and adds zero for the rest.

Related: [`BENCH-2026-08-05.md`](BENCH-2026-08-05.md) for what that money bought,
and [`MODELS.md`](MODELS.md) for what each model is.
