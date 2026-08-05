# Prompt 09 — the model reference and the tab guide

Written before the docs. Raised by the owner: "provide a section under research
with a detailed explanation how each and every model is working, what kind of
models we have, resource links… and find how each and every tab is working."

---

**Role.** You are documenting a research system for one reader who will come back
to it in three months having forgotten everything, and who wants to reason about
the models rather than just run them.

<context>
Seven models are installed: `reels-vision` (qwen2.5vl 7B q8, the control),
`qwen3-vl` at 8B/4B/2B, `minicpm-v4.5:8b`, `gemma4:12b`, `deepseek-ocr:3b`, plus
the `claude-cli` reference arm. All local ones are served by Ollama on an
OpenAI-compatible endpoint at 32k context, because six 720px frames plus the
prompt overflow the stock 4096. The app has 13 tabs, an API on 127.0.0.1:8000,
and a pipeline of enumerate → download → extract+vision → docs → index.
</context>

<task>
Two documents: `MODELS.md` — what each model is and how it processes a reel; and
`UI-TABS.md` — what each tab does, what it reads, and what it is for.
</task>

<steps>
1. MODELS.md: the pipeline a reel takes through any model; a table of the models
   with family, size, quantisation, context and role in the experiment; a section
   per model explaining its architecture in plain terms and what to expect from
   it here; the knobs that change results (frames, context, max_tokens,
   temperature, two-pass); and links to each model's own page.
2. UI-TABS.md: one section per tab — what it is for, what it reads, the controls
   that matter, and the gotcha worth knowing. Plus the API endpoints behind it.
3. Cross-link both from `docs/research/README.md` and the repo `README`/docs index.
</steps>

<must>
- Every claim about behaviour here is either measured on this machine or marked
  as an expectation.
- Link to primary sources (model cards, papers, Ollama pages), not blog posts.
- Say what a model is bad at, not only what it is for.
</must>

<must-not>
- Do not restate the code; explain what the reader cannot see from it.
- Do not invent benchmark numbers — the bench report is the only source for those.
</must-not>

---

## Outcome

`docs/research/MODELS.md`, `docs/research/UI-TABS.md`, both linked from the
research README and the docs index.
