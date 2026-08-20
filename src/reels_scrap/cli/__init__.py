"""CLI assembly. Every command lives in one of the modules registered below.

Each module exposes `register(app)` and declares its commands inside it, so
command names stay exactly what the function is called — no group prefixes, no
renames — and adding a command means editing one small file.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from . import bench, corpus, pipeline, serve, sources
from .common import console

__all__ = ["app", "console", "main"]

load_dotenv()
app = typer.Typer(add_completion=False, help="Instagram reels -> text -> PDF -> docs.")

for _module in (pipeline, corpus, sources, bench, serve):
    _module.register(app)


def main():
    app()


if __name__ == "__main__":
    main()
