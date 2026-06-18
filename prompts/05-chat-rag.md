# Layer 05 — Research Chat (RAG)

You are a RAG engineer. Your objective is to build the `chat/` package: answer
research questions over the scraped corpus by embedding the question, retrieving
top-k cited context from the local index, synthesizing a grounded answer via
`claude -p`, and returning the answer plus structured citations — degrading to
retrieved sources when the LLM is unavailable.

<context>
  <depends_on>
    Layers 00–04 exist: `search/embed`, `search/query.search/to_citation`, the
    index under `output/index`, and `Reel` records (for citation metadata).
    Use the SAME embedding model the index was built with
    (`config.search.embed_model`).
  </depends_on>
  <boundary>
    `chat` only READS the index + `Reel` records. It never scrapes or extracts.
    The only external call is one `claude -p` synthesis per question.
  </boundary>
  <claude_backend>
    Default `config.chat.backend = claude-cli`: shell out to `claude -p` with the
    research prompt + cited context (uses the user's subscription, no key).
    Fallback backend `api` uses `ANTHROPIC_API_KEY` with the Anthropic SDK and
    `config.chat.model` (default `claude-sonnet-4-6`).
  </claude_backend>
  <observed_failure_mode>
    The `claude` CLI has been seen to fail with empty stderr (subscription
    throttle). This is the canonical fallback case: return the retrieved sources
    with `answer=null` + a note, never raise to the caller.
  </observed_failure_mode>
</context>

## Instructions
1. **`chat/prompts.py`.** Define the research synthesis prompt as a template
   function `build_chat_prompt(question, context_block) -> str`. The prompt MUST
   instruct Claude to: answer ONLY from the provided context; cite every claim
   inline as `[<reel_id>]`; and say "not in the archive" when the context doesn't
   support an answer. Keep it terse and deterministic.
2. **`chat/rag.py` — the flow.** `answer(question, config) -> ChatResponse`:
   1. embed the question with `search/embed` (same model as the index);
   2. retrieve top-k (`config.chat.top_k`, default 8) via `search/query.search`;
   3. build a **context block**: for each hit a line
      `[<reel_id>] <title> — <fact-or-summary snippet>` (include the timestamp
      for fact hits);
   4. call the configured backend with `build_chat_prompt`:
      - `claude-cli`: `claude -p` with the prompt; capture stdout;
      - `api`: Anthropic SDK with `config.chat.model`;
   5. parse the answer; extract the `[reel_id]` cites and map each back to reel
      metadata (title, url, score, snippet) via `search.to_citation` /
      `Reel.load`;
   6. return `ChatResponse{answer, citations: [{reel_id, title, url, score,
      snippet, timestamp}], note?}`.
3. **Resilience (the spec's required fallback).** If the `claude -p` call fails
   (non-zero exit, empty/garbage output, timeout, or the empty-stderr throttle),
   catch it and return the retrieved hits as citations with `answer=null` and
   `note="synthesis unavailable"`. Same philosophy as the vision-stage skip.
   Log it; never propagate the exception to the API. If the index is empty,
   surface `EmptyIndexError` (the API maps it to 409).
4. **No streaming in v1.** Return a single `ChatResponse`. Leave a `# SSE later`
   note where streaming would hook in, but do not implement it.
5. **Reuse, don't duplicate.** Reuse `search/embed` and `search/query` —
   chat owns no embedding/index logic of its own. The `claude -p` subprocess
   helper should be shared with (or mirror) the vision/synthesis invocation so
   the CLI call site is consistent.
6. **Tests.** `tests/test_chat.py` with the `claude` subprocess mocked:
   - happy path → `answer` non-null, citations resolved from `[reel_id]` cites
     back to fixture reel metadata;
   - context block includes one tagged line per retrieved hit, with timestamps
     for fact hits;
   - CLI-failure path (mock subprocess to fail / empty output) →
     `answer is None`, `note == "synthesis unavailable"`, citations still
     populated from retrieval;
   - empty index raises `EmptyIndexError`.

## Constraints
- MUST ground answers strictly in retrieved context and require inline
  `[reel_id]` citations.
- MUST use the SAME embedding model as the index build.
- MUST degrade on Claude CLI failure to `answer=null` + retrieved sources +
  note — never raise to the API layer.
- MUST default to the `claude-cli` backend; use `api` only when configured.
- MUST reuse `search/embed` + `search/query`; no duplicate retrieval logic.
- MUST resolve all paths through `core/paths`.
- MUST NOT implement streaming, conversation memory, or multi-turn state in v1.
- MUST NOT let unsupported claims through — instruct the model to abstain.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`chat/prompts.py`, `chat/rag.py`, the shared `claude -p` subprocess helper (if
extracted), and `tests/test_chat.py`. Show the exact `claude -p` invocation and
the `ChatResponse` schema. End with the commands to run the tests.

Reason briefly in a `<thinking>` block first, then output the files.
