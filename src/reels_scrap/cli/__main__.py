"""`python -m reels_scrap.cli …` — the invocation every doc and scheduled task uses.

A package needs this file; the old single-module cli.py did not. Without it the
documented command dies with "cannot be directly executed" and every runbook,
`scripts/setup-windows.ps1` task and CLAUDE.md snippet breaks at once.
"""

from . import main

main()
