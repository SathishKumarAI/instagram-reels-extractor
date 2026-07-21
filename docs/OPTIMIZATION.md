# Vision extraction — cost & speed optimization

The vision pass (genre/summary/tags/facts/tokens) is the throughput + cost
bottleneck. Where the cost goes and how to cut it.

## Where the cost is

`vision_backend=claude-cli` (default, no API key) is convenient but **expensive per
reel** (~60–80k input tokens): each frame is an **agentic `Read` tool turn**, plus
the CLI's own system prompt + tool schemas + cache ride along every call. It also
**cannot run in parallel** — 3 concurrent calls throttle (36 ok → 84 fail).

## Optimizations shipped

| Change | Effect |
|--------|--------|
| **Frame caching** (`sample_frames`) | reuse sampled frames on re-extract/backfill → no repeat ffmpeg |
| **`extract.max_frames`** (default 6, was 8) | fewer image reads per reel → faster + cheaper; set 4 for max speed |
| **Sequential claude-cli** (concurrency 1) | reliable — parallel claude-cli throttles (baked into defaults) |
| **`sync --claude-only` / `config-claude.yaml`** | skip CPU whisper/OCR → big wall-clock win |
| **API backend auto-detect** (backfill) | if `ANTHROPIC_API_KEY` set → inline images, **~15× fewer tokens** + real parallelism |

## The big win: API backend

`vision_backend=api` sends frames **inline in one request** — no agentic Read, no CLI
overhead (~2–4k tokens/reel vs 60k+) **and** it parallelizes safely.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# auto-picks api when the key is present, runs 5 in parallel:
python scripts/backfill_vision.py --config config-claude.yaml --backend auto --workers 5
```

Rough per-reel cost: claude-cli ≈ 60–80k in / 1–2k out (subscription, "free" but slow +
serial); api ≈ 2–4k in / 1k out (paid, but ~15× cheaper in tokens, fast, parallel).

## Why "input tokens" look huge (measured)

One real claude-cli vision call (4 downscaled frames):

| Component | Tokens | What it is |
|-----------|--------|-----------|
| fresh input | 15,366 | actual prompt + images |
| **cache_read** | **35,584** | Claude Code's system prompt + tool schemas, reloaded (cached, ~10% price) each call |
| cache_creation | 26,102 | one-time cache write of that machinery |
| output | 1,045 | the JSON reply |
| **real cost** | **$0.38** | reported by the CLI directly |

So ~62k of the ~77k "input" is **CLI machinery, not your reels** — mostly *cached*
(near-free). The metering now stores these **separately** (`input`/`cache_read`/
`cache_creation`/`output`/`cost_usd`) and `/api/stats` uses the CLI's **real
`total_cost_usd`**, so the dashboard stops over-counting cache reads.

**The one real fix:** `vision_backend=api` sends only the images inline — **no CLI
system-prompt/tools overhead at all**. Per-reel ≈ 7-8k tokens, ~$0.02 vs $0.38.
Set `ANTHROPIC_API_KEY` and the `auto` backend uses it (parallel-safe too).

## How to reduce tokens — ranked

| # | Lever | How | Reduction |
|---|-------|-----|-----------|
| 1 | **API backend** | `export ANTHROPIC_API_KEY=…` + `--backend api` | ~15-20× (no agentic Read / CLI overhead) |
| 2 | **Downscale frames** | `extract.frame_max_width: 720` (default) → `512` | ~2-3× (image tokens ∝ pixels) |
| 3 | **Fewer frames** | `extract.max_frames: 4` | ~1.5× |
| 4 | **Cheaper model** | `extract.vision_model: claude-haiku-4-5` | fewer $/token (not fewer tokens) |
| 5 | **Don't re-vision** | backfill skips reels with tags (idempotent) | avoids 100% waste |
| 6 | **Vision off** | `extract.vision: false` | 100% (keep caption+transcript+search) |

Stack 1+2+3 → a reel that cost ~70k tokens via claude-cli drops to ~1-2k via API at
512px/4 frames — and it's parallel. On the flat subscription (claude-cli) tokens are
free-but-slow, so there levers 2+3 mainly buy **speed**; on API they buy **cost**.

## Other levers

- **Cheaper model**: `extract.vision_model: claude-haiku-4-5` for simple reels — faster
  + cheaper than sonnet; keep sonnet for dense/technical reels.
- **Fewer frames**: `max_frames: 4` when reels are short/simple.
- **Skip re-work**: backfill skips reels that already have tags (idempotent).
- **Privacy note**: api and claude-cli both send frames to Anthropic — the one egress
  point. `extract.vision: false` for a fully local run (see `docs/PRIVACY.md`).
