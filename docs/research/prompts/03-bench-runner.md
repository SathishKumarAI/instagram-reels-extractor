# Prompt 03 — bench sample + runner

Written before the code for phase 3 (`docs/research/PLAN.md`).

---

**Role.** You are building an experiment harness, not a feature. The output is
evidence someone will act on, so a result that looks clean but hides a failed arm
is worse than no result.

<context>
674 reels on disk as `data/<id>.json` (`Reel` pydantic model). Frames are cached
under `output/frames/<id>/` and transcripts are stored on the record, so the
vision step can be re-run without re-downloading or re-transcribing anything.
`extract.vision.run_variant(reel, cfg, backend) -> dict` runs one model over one
reel and returns the variant shape (`summary`, `tags`, `facts`, `structured`,
`tokens`, `elapsed_s`, `frames`, …). Profiles (phase 1) resolve a name to a
Config. One 16.3GB GPU: exactly one model resident at a time.
</context>

<task>
Pick a fixed sample once, then run any set of profiles over exactly that sample,
resumably.
</task>

<steps>
1. `sample(cfg, n, seed)` — stratified over genre × collection so the sample looks
   like the corpus, deterministic for a seed, written to `output/bench/sample.json`
   with the strata counts that produced it.
2. `run(profiles, sample, force=False)` — for each profile, for each reel: skip if
   `reel.variants[profile]` exists, else run the vision step and store the variant
   under the profile name.
3. Append one row per attempt to `output/bench/runs.jsonl`: profile, reel id, ok,
   seconds, error. A failed arm must be visible in the data, never a silently
   thinner average.
4. Profiles run one at a time, in order, and the runner releases the GPU between
   profiles (`keep_alive=0`) so the next model can load.
5. Progress goes to a callback so the CLI can print it and a future UI can poll it.
</steps>

<must>
- Same seed and same corpus produce the same sample.
- Re-running is safe and cheap: stored pairs are skipped unless `--force`.
- One model failing a reel records the error and continues to the next reel.
- Every arm sees identical input — reuse cached frames, never re-sample them.
- Tests run offline with the vision call stubbed.
</must>

<must-not>
- Do not run models concurrently — 16GB fits one.
- Do not mutate any field of the reel other than `variants`.
- Do not silently shrink the sample when a genre is thin; report what it took.
</must-not>

---

## Outcome

`src/reels_scrap/bench.py`, `reels-scrap bench sample|run|report`,
`tests/test_bench.py`. Sample and run log live under `output/bench/`.
