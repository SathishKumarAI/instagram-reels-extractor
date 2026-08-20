# Prompt 06 — run the experiment

Written before running phase 6 (`docs/research/PLAN.md`). This one is an operating
procedure, not a code prompt: the code was already built and checked in phases 1-5.

---

**Role.** You are running an experiment on a single-GPU workstation. The result
is only worth the GPU hours if the arms are comparable and the failures are
visible.

<setup>
- Sample: 30 reels, seeded 0, genre-stratified
  (educational 9, entertainment 9, tutorial 6, product 4, news 1, other 1),
  fixed in `output/bench/sample.json`.
- Reference arm: `claude-cli` (claude-sonnet-4-6).
- Control arm: the existing `local` variants, written by `reels-vision`
  (qwen2.5vl 7B q8) during the corpus backfill — same frames, already on disk.
- Candidate arms: whatever `models.yaml` entries are pulled by run time.
- One model resident at a time; the runner releases the GPU between arms.
</setup>

<procedure>
1. `bench sample -n 30 --seed 0` — once. Never re-sample between arms.
2. `bench run -p claude-cli` — the cloud reference. No GPU, so it may overlap
   with downloads.
3. `bench run -p <local arms>` — serialised, resumable, skipping stored pairs.
4. `bench report` — metrics, agreement, attempts, then the written analysis.
5. Record in the report what did **not** run and why.
</procedure>

<must>
- Report the arms that failed or never ran; a missing model is a stated gap, not
  an omission.
- State the sample size next to every average.
- Quote real claims in the narrative — no unsupported characterisation of a model.
</must>

<must-not>
- Do not re-sample, re-download frames, or re-transcribe between arms.
- Do not run two models on the GPU at once.
- Do not present a partial run as a complete one.
</must-not>

---

## Outcome

`docs/research/BENCH-<date>.md` plus the raw `output/bench/runs.jsonl` behind it.
