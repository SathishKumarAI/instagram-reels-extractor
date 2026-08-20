# Local vision backend (your own GPU box)

Run the vision stage on a **self-hosted, open-weights** model instead of Claude.
Same output for every reel — genre, summary, tags, facts, tokens — just produced
by a model you host. Frames stay on your LAN; **no data egress** (except the
optional Claude fallback, which is logged).

## Which model

**[Kimi-VL-A3B-Instruct](https://huggingface.co/moonshotai/Kimi-VL-A3B-Instruct)** —
open-weights (Modified MIT), MoE vision-language model, ~2.8 B *active* params,
128K context, native-resolution vision. Compact enough for a modest GPU box,
competitive with GPT-4o-mini / Qwen2.5-VL-7B. Any OpenAI-compatible vision model
works (Qwen2.5-VL, Llama-3.2-Vision, …) — just set `model` + `base_url`.

## Serve it (pick one)

**vLLM (recommended — best Kimi-VL support):**

```bash
# on the GPU box
pip install vllm
vllm serve moonshotai/Kimi-VL-A3B-Instruct \
  --trust-remote-code --port 8000
# exposes an OpenAI-compatible API at http://<gpu-box>:8000/v1
```

**Ollama (simplest; use a model in its registry, e.g. qwen2.5-vl):**

```bash
ollama pull qwen2.5-vl:7b
ollama serve            # OpenAI-compatible API at http://<gpu-box>:11434/v1
```

## Point the pipeline at it

Edit `config-local.yaml` (or any config's `extract.vision_local`):

```yaml
extract:
  vision_backend: local
  vision_local:
    base_url: "http://gpu-box:8000/v1"          # your endpoint
    model: "moonshotai/Kimi-VL-A3B-Instruct"    # or qwen2.5-vl:7b for Ollama
    api_key: ""                                  # usually none
    timeout: 120
  vision_local_fallback: true                    # false = strict local, never egress
```

## Choose the backend at run time

Three surfaces, all pick the same knob:

| Surface | How |
|---------|-----|
| **Config** | `reels-scrap sync -c config-local.yaml` (or set `vision_backend: local`) |
| **CLI flag** | `reels-scrap sync --backend local` / `--backend claude-cli` (overrides config) |
| **Web UI** | Sources page → **Vision backend** toggle → *Local GPU box* / *Claude code* |

## What you get per reel

- **Same schema** as the Claude path (`_apply` is shared) — `genre`, `summary`,
  `tags`, `structured`, `facts` (with frame + timestamp provenance).
- **Tokens** from the endpoint's `usage` (`prompt_tokens`/`completion_tokens`);
  `cost_usd = 0` (your hardware).
- **Provenance**: each reel's `tokens.backend` records which model produced it
  (`local`, `claude-cli`, `api`, or `local->claude-cli` when a reel fell back).

## Failure & fallback

Local calls retry `vision_max_retries` times (exponential backoff). If the
endpoint is down or returns malformed JSON, the reel **falls back to `claude-cli`**
so it still gets extracted — and that fallback is logged (`… falling back to
claude-cli (frames egress to Claude)`). Set `vision_local_fallback: false` to
dead-letter instead and keep the machine strictly local.
