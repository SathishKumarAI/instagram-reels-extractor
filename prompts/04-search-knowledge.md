# Layer 04 — Search & Knowledge Base

You are a retrieval/knowledge engineer. Your objective is to build the `search/`
package (local fastembed semantic index over reels + facts) and the `knowledge/`
package (deterministic aggregation grouped by genre/topic, with optional cached
Claude synthesis).

<context>
  <depends_on>
    Layers 00–03 exist. `output/reels/<id>.json` records carry summary, genre,
    hashtags, transcript_text, ocr_text, and provenance facts. Index files go to
    `output/index`, knowledge files to `output/knowledge`, model cache to
    `paths.input_cache`.
  </depends_on>
  <boundary>
    `search` and `knowledge` only READ `Reel` records (and, for chat later, the
    index). They never scrape. Aggregation is pure Python and deterministic;
    synthesis is the only optional LLM step and is cached + opt-in.
  </boundary>
  <embedding_model>
    fastembed, model from `config.search.embed_model`
    (default `BAAI/bge-small-en-v1.5`), cache under `input/cache`. The SAME model
    must be used to build the index and to embed chat questions in Layer 05.
  </embedding_model>
</context>

## Instructions
1. **`search/embed.py`.** Wrap fastembed: `get_embedder(config)` (cached,
   loads `config.search.embed_model` with cache dir under `paths.input_cache`),
   `embed_texts(texts) -> np.ndarray`, and a single `embed_text(text)`. Normalize
   vectors so cosine = dot product.
2. **`search/index.py`.** Build a local index over BOTH reels and individual
   facts so retrieval can cite a precise claim:
   - `build_index(config)`: read all `output/reels/*.json`; for each reel emit
     chunk records: one for the reel (title + summary + caption) and one per
     `Fact` (fact text + its timestamp/frame), each tagged with `reel_id` and a
     `kind` (`reel`|`fact`) and the source `snippet`; embed them; save vectors to
     `output/index/search_index.npz` and the aligned metadata to
     `output/index/search_index.json`.
   - `load_index(config)`: load both; raise `EmptyIndexError` if missing/empty.
   Idempotent + incremental: skip re-embedding chunks whose reel JSON is
   unchanged (hash/mtime check); rebuild changed ones.
3. **`search/query.py`.** `search(query, config, top_k=None) -> list[Hit]`:
   embed the query, cosine-rank against the loaded index, return top-k
   `Hit{reel_id, kind, score, snippet, title, url, timestamp}`. Default
   `top_k = config.search.top_k` (8). Provide a `to_citation(hit)` helper used by
   chat. On empty index raise `EmptyIndexError` (the API maps it to 409).
4. **`knowledge/aggregate.py`.** `aggregate(config) -> Knowledge` (pure,
   deterministic, cheap): read all reels, group by `genre`, then sub-group by
   shared hashtags/topic where present. For each group build a `Topic`:
   `{name, genre, reels: [refs], facts: [provenance facts], summaries: [...]}`.
   Collect each member's summary + facts + a source-reel ref (id, title, url,
   thumbnail). Write `output/knowledge/knowledge.json`. No LLM here.
5. **`knowledge/synthesize.py` (optional, cached).** `synthesize_topic(topic,
   config) -> str`: ONE `claude -p` call producing a short "what this topic
   covers" overview from the topic's summaries + facts. Cache to
   `output/knowledge/<topic-slug>.json`; only regenerate when member reels change
   (hash the member ids + their mtimes). Default OFF
   (`config.knowledge.synthesize`); when enabled, attach `overview` to each
   `Topic`. On `claude -p` failure, leave `overview=null` and record it — never
   fail aggregation.
6. **CLI + pipeline wiring.** Implement `reels-scrap index` (build/refresh the
   search index) and `reels-scrap search "<query>"` (print top-k hits). Make
   `run` call `build_index` then `aggregate` (and `synthesize` if enabled) as its
   final stages, after render. Record counts in the `RunReport`.
7. **Tests.** `tests/test_search.py`: building an index over fixture reels
   produces aligned `.npz` + `.json` with one chunk per reel + per fact; a query
   ranks the semantically-closest fixture first; empty index raises
   `EmptyIndexError`; incremental rebuild skips unchanged reels.
   `tests/test_knowledge.py`: aggregation groups fixtures by genre, each topic
   carries its source-reel refs + provenance facts; synthesis is skipped when the
   toggle is off and cached/short-circuited when member reels are unchanged
   (mock the `claude` subprocess).

## Constraints
- MUST use the SAME embedding model for index build and (later) chat queries —
  read it from `config.search.embed_model`.
- MUST index facts as their own chunks so retrieval can cite a precise claim with
  its timestamp.
- MUST keep aggregation pure/deterministic; synthesis is the only LLM step and is
  cached + opt-in + non-fatal on failure.
- MUST raise `EmptyIndexError` on a missing/empty index (API → 409).
- MUST resolve all paths through `core/paths`; index under `output/index`,
  knowledge under `output/knowledge`, model cache under `input/cache`.
- MUST NOT scrape or re-extract; only read `Reel` records.
- MUST NOT call the LLM during plain aggregation or search.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`search/embed.py`, `search/index.py`, `search/query.py`,
`knowledge/aggregate.py`, `knowledge/synthesize.py`, the CLI + pipeline wiring
additions, and the two test files. End with the commands to add `fastembed` and
run the tests, plus example: `reels-scrap index` then
`reels-scrap search "best resistance band exercises"`.

Reason briefly in a `<thinking>` block first, then output the files.
