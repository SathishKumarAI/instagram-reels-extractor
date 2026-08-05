# Prompt 05 — Compare tab picks from N profiles

Written before the code for phase 5 (`docs/research/PLAN.md`).

---

**Role.** You are extending a working React + FastAPI surface. The tab already
compares two models; it must now compare any two of many, without growing a
second UI.

<context>
`POST /api/reels/{id}/compare` takes `backends: [a, b]` and already routes through
`resolve_profile`, so any profile name works server-side today. The Compare tab
(`web/src/views/ComparePage.tsx`) hard-codes `["claude-cli", "local"]` in
`api.compare()` and renders `Metric`, `VariantCard` and `Diff` from the returned
`CompareResult`. The scoreboard endpoint returns one row per stored variant key.
</context>

<task>
Let the user choose which two models to run, from the profiles the machine
actually has.
</task>

<steps>
1. `GET /api/profiles` → `[{name, kind, model, installed, notes}]`, merging the
   declared profiles with the model registry so the UI can grey out what is not
   pulled yet.
2. Two selects on the Compare tab, defaulting to the current pair, feeding the
   existing compare and batch calls.
3. The scoreboard table already renders whatever rows it receives — confirm it
   does not assume two.
</steps>

<must>
- A profile that is declared but not installed is visibly not runnable.
- The default pair still works with no interaction, so the tab does not regress.
- `tsc -b` stays clean.
</must>

<must-not>
- Do not add a state library, a new route, or a second comparison surface.
- Do not let the picker offer a name the server cannot resolve.
</must-not>

---

## Outcome

`GET /api/profiles` in `api/app.py`, `api.profiles()` in `web/src/lib/api.ts`,
two selects in `ComparePage.tsx`.
