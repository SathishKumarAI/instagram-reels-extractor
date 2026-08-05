# Prompt 01 — model profiles

Written before the code for phase 1 (`docs/research/PLAN.md`). Reusable: point it
at any codebase where one setting has quietly become an enum that must grow.

---

**Role.** You are a Python engineer working in an existing, working codebase. Your
edits must not break records that already exist on disk.

<context>
`extract.vision_backend` is a closed set: `auto | claude-cli | api | local`.
`local` means exactly one endpoint, `extract.vision_local` (`base_url`, `model`,
`api_key`, `timeout`, `max_tokens`), which only `config-local.yaml` carries.
`reel.variants` is a dict keyed by that backend string, so a second local model
would overwrite the first. `compare.cfg_for_backend(backend, base_config)`
already special-cases `local` by loading `config-local.yaml`; the sync endpoint
and the CLI call the same idea in their own words.
674 reels on disk, 641 with variants under the keys `claude-cli` and `local`.
</context>

<task>
Let the project run **many named models**, keyed by profile name, without a
corpus migration and without breaking any existing caller.
</task>

<steps>
1. Add `extract.vision_profiles: dict[str, VisionProfileCfg]` to the config.
   A profile carries: `kind` (local | claude-cli | api), `model`, `base_url`,
   `api_key`, `num_ctx`, `max_tokens`, `timeout`, `notes`.
2. Write `src/reels_scrap/profiles.py` with `resolve_profile(name, base_config)
   -> Config` — a Config whose `extract.*` is set to run exactly that one model.
3. Keep the implicit names working with no config edit: `claude-cli` and `api`
   resolve from the base config, `local` from `extract.vision_local`, falling
   back to `config-local.yaml` exactly as `cfg_for_backend` does today.
4. A declared profile of the same name wins over the implicit one.
5. `list_profiles(base_config)` returns every name that resolves, so the CLI and
   the UI enumerate the same set.
6. Re-export `cfg_for_backend` as an alias so `compare.py`, `cli.py` and the API
   need no behaviour change.
</steps>

<must>
- Unknown profile name raises a clear error naming the known ones.
- A local profile with no `base_url` raises at resolution, not mid-run.
- Existing variant keys (`claude-cli`, `local`) stay valid profile names.
- One runnable test per rule above, offline.
</must>

<must-not>
- Do not migrate or rewrite any reel record.
- Do not change what `vision_backend` means for an existing config.
- Do not add a dependency; `pydantic` and `pyyaml` are already here.
</must-not>

Think about the compatibility rules before writing code, then write the module,
then the tests.

---

## Outcome

`src/reels_scrap/profiles.py` (+ `VisionProfileCfg` in `config.py`,
`tests/test_profiles.py`). `cfg_for_backend` kept as an alias — `compare.py`,
`cli.py` and `api/app.py` were untouched by this phase.
