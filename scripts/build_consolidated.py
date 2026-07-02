#!/usr/bin/env python3
"""Build the consolidated local docs without the full CLI/env.

Thin wrapper over `reels_scrap.docs` — the real logic lives in the package
(`render/consolidated.py`, `docs.py`, `collections.py`). Handy while the ML/CLI
deps aren't installed: this path only needs stdlib + pydantic.

    PYTHONPATH=src python3 scripts/build_consolidated.py [config.yaml]

Prefer `reels-scrap consolidate` once the package is installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reels_scrap.config import Config  # noqa: E402
from reels_scrap.docs import rebuild_all  # noqa: E402


def main() -> None:
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    docs, index = rebuild_all(Config.load(config))
    if not docs:
        print("nothing in data/ to consolidate.")
        return
    for d in docs:
        print(f"✓ {d}")
    print(f"✓ index → {index}")


if __name__ == "__main__":
    main()
