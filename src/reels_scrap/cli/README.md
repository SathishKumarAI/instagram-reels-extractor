# cli/ — one file per command group

Read this table instead of the code.

| Change | File |
|---|---|
| `run`, `ingest-cmd`, `extract-cmd`, `render-cmd`, `collection`, `fetch-collection`, `consolidate` | `pipeline.py` |
| `index`, `search`, `knowledge`, `ask` | `corpus.py` |
| `add-source`, `list-sources`, `sync`, `discover`, `login` | `sources.py` |
| `bench sample|run|report`, `models list|pull` | `bench.py` |
| `serve` | `serve.py` |
| Console, `load_reels`, `open_in_browser`, `browser_spec` | `common.py` |
| Which modules are registered, and in what order | `__init__.py` |

## Rules that keep the table true

- Each module exposes `register(app)` and declares its commands **inside** it.
  Typer derives the command name from the function name, so a moved function
  keeps its CLI name — `extract_cmd` is `extract-cmd` wherever it lives.
- `__main__.py` exists so `python -m reels_scrap.cli …` keeps working. That is the
  form CLAUDE.md, the scheduled tasks and every runbook use; a package without it
  fails with "cannot be directly executed".
- Heavy imports stay inside the command body. `--help` must not import torch.
- The stdout UTF-8 reconfigure lives at the top of `common.py`, before `Console()`
  is built — on Windows the ✓/✗ marks and any emoji caption kill a cp1252 stream.

## Traps

- **`sync` runs two guards before spending an Instagram request** — GPU busy, and a
  cookie probe. Both exist because the failure they catch is expensive and looks
  like something else (240s timeouts per reel; 20 identical source errors).
- Exit codes are load-bearing: **3** means the GPU was busy or contended, **2** an
  invalid flag, **1** nothing to do. The scheduled sync distinguishes them.
