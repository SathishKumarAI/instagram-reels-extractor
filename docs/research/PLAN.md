# Plan — vision model bench

Design: `../superpowers/specs/2026-08-05-vision-model-bench-design.md`.
Each phase writes its prompt to `prompts/` **before** its code, ships one runnable
check, and updates the Status column here.

| # | Phase | Ships | Check | Status |
|---|---|---|---|---|
| 1 | Model profiles | `src/reels_scrap/profiles.py`, `vision_profiles` config, variants keyed by profile | declared profile wins; implicit `local`/`claude-cli` still resolve; unknown name raises | done 2026-08-05 |
| 2 | Model install | `models.yaml`, `reels-scrap models list|pull`, generated 32k Modelfiles | registry parses; `list` marks installed vs missing without touching the network | done 2026-08-05 |
| 3 | Bench sample + run | `src/reels_scrap/bench.py`, `bench sample`, `bench run` | same seed → same sample; stored pairs skipped; a failing arm records an error row and the run continues | done 2026-08-05 |
| 4 | Scoreboard + report | per-profile scoreboard, `bench report` → `BENCH-<date>.md` | scoreboard groups by profile; report renders from a fake corpus with the analysis pass stubbed | done 2026-08-05 |
| 5 | UI | Compare tab picks from N profiles | `tsc -b` clean; picker lists declared profiles | done 2026-08-05 |
| 6 | Run the experiment | 7 models pulled, 30-reel sample × 7 local arms + the Claude reference, written analysis | `docs/research/BENCH-2026-08-06.md`, numbers from `runs.jsonl` | done 2026-08-06 |

## Phase order rationale

Profiles first because everything else keys off a profile name — the bench, the
scoreboard and the UI all break if that contract changes later. Install second so
the arms exist before the runner needs them. The experiment runs last, on code
that has already been checked, because a 3.5-hour GPU run is an expensive place to
discover a bug.

## Decisions taken (and by whom)

- Research bench before production switching — owner, 2026-08-05.
- Curated model set with explicit pulls, no auto-download — owner, 2026-08-05.
- 30 reels, stratified — owner, 2026-08-05.
- Metrics **plus** a written analysis, not metrics alone — owner, 2026-08-05.
- Test every model in the shortlist, treat it as a research project — owner, 2026-08-05.
