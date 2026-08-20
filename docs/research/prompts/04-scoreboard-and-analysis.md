# Prompt 04 — scoreboard + why-they-differ analysis

Written before the code for phase 4 (`docs/research/PLAN.md`). The analysis
prompt this phase *ships* (the one sent to Claude at report time) is quoted at the
bottom — it is the deliverable, not an implementation detail.

---

**Role.** You are turning stored model outputs into evidence a person can act on.
A number without its denominator, or a claim about a model that no quoted example
supports, is a defect.

<context>
Each reel now stores one variant per profile: `summary`, `tags`, `facts`,
`structured`, `tokens`, `elapsed_s`. `compare.scoreboard(cfg)` already aggregates
per variant key and `compare.diff_facts(a, b)` matches claims by containment,
returning `shared / only_a / only_b`. `output/bench/runs.jsonl` holds one row per
attempt including failures.
</context>

<task>
A per-model scoreboard measured against a named reference arm, and a written
report that explains the differences from quoted claims.
</task>

<steps>
1. Extend the scoreboard: per profile, add agreement against a reference arm
   (default `claude-cli`) — shared claims, claims only that model made, claims
   only the reference made, and the reels both arms covered.
2. Fold in `runs.jsonl` so failed attempts appear next to the averages.
3. `write_report(cfg, with_analysis, examples)` writes
   `docs/research/BENCH-<date>.md`: run metadata, the metrics table, per-model
   agreement, then the analysis.
4. The analysis pass sends a bounded, stratified set of *actual disagreeing
   claims* and asks for per-model explanations. It must degrade to metrics-only
   when Claude is unavailable.
</steps>

<must>
- Every average states how many reels it came from.
- A model with no overlap with the reference reports "no overlap", never 0.0.
- The analysis prompt sends claim text only — no frames, no captions, no ids that
  identify an account.
- Report generation is testable offline with the analysis stubbed.
</must>

<must-not>
- Do not average away a failed arm.
- Do not let the written narrative introduce a claim that no example supports.
</must-not>

---

## The shipped analysis prompt

Sent by `benchreport.analyse()` with `{examples}` filled from real disagreements:

> You are analysing why different vision-language models describe the same short
> video differently.
>
> Each example below is one reel. `reference` is what a large cloud model
> (claude-sonnet-4-6) extracted; `candidate` is what a smaller local model
> extracted from the identical frames and transcript. `only_reference` are claims
> the reference made that the candidate did not; `only_candidate` the reverse.
>
> <examples>{examples}</examples>
>
> For each model named in the examples, answer in at most 120 words:
> 1. What kind of claim does it systematically miss? Quote one.
> 2. What does it add that the reference did not? Quote one, and say whether it
>    looks grounded in the frames or invented.
> 3. The single most likely mechanical cause — resolution of on-screen text,
>    context length, instruction following, or world knowledge.
>
> Then, in at most 150 words, state what the evidence supports about which model
> to use for this corpus, and what it does not support.
>
> MUST: ground every statement in a quoted claim from the examples.
> MUST NOT: speculate about training data, or rank models on anything the
> examples do not show.

---

## Outcome

`src/reels_scrap/benchreport.py`, scoreboard extended in `compare.py`,
`reels-scrap bench report`, `tests/test_benchreport.py`.
