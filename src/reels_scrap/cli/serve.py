"""`serve` — the local API + built UI. Binds 127.0.0.1 by default; see docs/PRIVACY.md."""

from __future__ import annotations

import typer

from .common import console


def register(app: typer.Typer) -> None:
    @app.command()
    def serve(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        host: str = typer.Option("127.0.0.1", "--host"),
        port: int = typer.Option(8000, "--port", "-p"),
        reload: bool = typer.Option(False, "--reload"),
    ):
        """Launch the research API (Knowledge Base + Research Chat) + UI if built."""
        import uvicorn

        from ..api import create_app

        console.print(f"[green]serving[/] http://{host}:{port}  (API under /api)")
        uvicorn.run(create_app(config), host=host, port=port, reload=reload)
