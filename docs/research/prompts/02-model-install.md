# Prompt 02 — model install

Written before the code for phase 2 (`docs/research/PLAN.md`).

---

**Role.** You are a Python engineer adding an install path for local models on a
single-GPU workstation. The user pays for every gigabyte in disk and in patience,
so nothing downloads without being asked for.

<context>
Ollama serves an OpenAI-compatible API at `127.0.0.1:11434/v1`. A stock model's
context (4096) is too small for the six frames plus prompt this pipeline sends,
which is why the existing `reels-vision` was built from
`scripts/ollama-vision.Modelfile` with `num_ctx` raised. Installed today:
`reels-vision`, `qwen2.5vl:7b-q8_0`, `qwen2.5vl:7b`. GPU: RTX 5070 Ti, 16.3 GB,
one resident model at a time. Profiles (phase 1) name the models the bench runs.
</context>

<task>
A curated registry of vision models and the two commands that install them.
</task>

<steps>
1. `models.yaml` at the repo root: one entry per profile — ollama tag, `num_ctx`,
   approximate VRAM, and **why it is in the set** (the contrast it tests).
2. `reels-scrap models list` — every registry entry with installed / missing,
   read from `ollama list` output. No network call.
3. `reels-scrap models pull <profile|all>` — `ollama pull <tag>`, then
   `ollama create <profile> -f <generated Modelfile>` raising `num_ctx`.
   Print the tag and size before each pull.
4. `models sync-config` — write the registry's entries into
   `config-local.yaml`'s `extract.vision_profiles`, so a pulled model is
   immediately runnable by name.
</steps>

<must>
- Every pull is an explicit command. Nothing pulls implicitly during a run.
- A bad ollama tag fails loudly, naming the tag.
- `models list` works with ollama not running (everything reads as missing).
- Generated Modelfiles are written under `scripts/modelfiles/` and are readable.
- One offline test: registry parses, and `list` marks installed vs missing from a
  stubbed `ollama list`.
</must>

<must-not>
- Do not shell out with a string built from user input without splitting args.
- Do not delete or overwrite the existing `reels-vision` model.
- Do not add a Python dependency for something `subprocess` already does.
</must-not>

---

## Outcome

`models.yaml`, `src/reels_scrap/modelreg.py`, `reels-scrap models list|pull|sync-config`,
generated Modelfiles under `scripts/modelfiles/`, `tests/test_modelreg.py`.
