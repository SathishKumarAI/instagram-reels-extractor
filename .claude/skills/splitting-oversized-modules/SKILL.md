---
name: splitting-oversized-modules
description: Use when a Python file in this repo passes ~500 lines, when one file holds several unrelated jobs, when a change means scrolling past code it does not touch, or when asked to modularise, split, or reorganise a module.
---

# Splitting an oversized module

The target is that changing one thing means opening one small file. A split that
also changes behaviour is two mistakes at once — **move code, edit nothing**.

## Split by concern, not by line count

Ask what each block *owns*. Two done in this repo:

| Was | Became |
|---|---|
| `extract/vision.py` 646 lines | `prompts.py` (what the model is told) · `normalise.py` (how the answer is read) · `vision.py` (backends, retry, provenance) |
| `api/app.py` 939 lines, 37 routes in one function | `routes/<group>.py` each `build(cfg, config_path) -> APIRouter` · `deps.py` · `app.py` assembly only |

A helper used by one group stays in that group. A shared-helpers module exists
only for what two or more need, and stays short.

## Keep the old import path working

Callers, scripts and tests import private names. Re-export them from the original
module and list them in `__all__` so ruff does not strip them:

```python
from .normalise import apply as _apply
from .prompts import prompt_header as _prompt_header

__all__ = ["_apply", "_prompt_header", "add_summary", "run_variant"]
```

**Check what monkeypatches what before moving a function.** Tests patch
`vision._via_local`; if the caller resolves that name from another module, the
patch silently misses. Look it up per call rather than hoisting it.

## Verify against a contract, not a vibe

Passing tests only prove the tested paths. Diff the module's public surface:

- **HTTP:** compare the OpenAPI path set before and after —
  `{(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops}`.
  It must be identical: none added, none lost.
- **Library:** compare `dir(module)` / the `__all__` set.
- **Then hit it live** against the real corpus (`TestClient`, one CLI run) — route
  registration is not behaviour.

## Finish the job

- `README.md` in the directory, first section a **change → file table**. If the
  repo already has one, update it in the same commit.
- Update `CLAUDE.md` where it names a moved symbol. A stale map costs more than none.
- One commit, `refactor(scope):`, body saying **no logic changed** and quoting the
  contract diff and the test count.

## Red flags

| Thought | Reality |
|---|---|
| "I'll tidy this while I'm in here" | Then the diff no longer proves behaviour is unchanged. Separate commit. |
| "Tests pass, it's fine" | Tests cover a subset. Diff the surface. |
| "I'll fix the imports later" | A broken re-export breaks a script nobody runs until 3am. |
| "The whole file is one concern" | Then it is a big concern, not a split — say so and stop. |
