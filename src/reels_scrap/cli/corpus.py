"""Asking the corpus things from the terminal: index, search, knowledge, ask."""

from __future__ import annotations

import typer

from ..config import Config
from .common import console


def register(app: typer.Typer) -> None:
    @app.command()
    def index(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        full: bool = typer.Option(False, "--full",
                                  help="re-embed everything (after a model/schema change)"),
    ):
        """Build/refresh the local semantic search index over all reels.

        Incremental by default — only reels changed since the last index are embedded.
        """
        cfg = Config.load(config)
        from ..search import build_index

        n = build_index(cfg, full=full)
        console.print(f"indexed [green]{n}[/] vectors.")

    @app.command()
    def search(
        query: str = typer.Argument(..., help="Natural-language query"),
        config: str = typer.Option("config.yaml", "--config", "-c"),
        k: int = typer.Option(8, "-k"),
    ):
        """Semantic search across the reel archive."""
        cfg = Config.load(config)
        from ..search import search as do_search

        for m in do_search(cfg, query, k):
            ts = f" @{int(m['timestamp'])}s" if m.get("timestamp") is not None else ""
            console.print(
                f"[dim]{m['score']:.2f}[/] [{m['kind']}{ts}] "
                f"[bold]{m['title'][:50]}[/] — {m['text'][:90]}\n      {m['url']}"
            )

    @app.command(name="knowledge")
    def knowledge_cmd(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        synthesize: bool = typer.Option(False, "--synthesize",
                                        help="Claude topic overviews (costs calls)"),
    ):
        """Rebuild the aggregated Knowledge Base from the reel corpus."""
        cfg = Config.load(config)
        from ..knowledge import build_knowledge

        kb = build_knowledge(cfg)
        if synthesize:
            from ..knowledge.synthesize import synthesize_topics

            synthesize_topics(cfg, kb)
        console.print(f"knowledge: [green]{len(kb.topics)}[/] topics over {kb.total_reels} reels")

    @app.command()
    def ask(
        question: str = typer.Argument(..., help="Research question"),
        config: str = typer.Option("config.yaml", "--config", "-c"),
        k: int = typer.Option(8, "-k"),
    ):
        """Ask the research chat a question from the CLI (RAG + citations)."""
        cfg = Config.load(config)
        from ..chat import answer_question

        a = answer_question(cfg, question, k=k)
        if a.answer:
            console.print(a.answer)
        else:
            console.print(f"[yellow]{a.note}[/]")
        if a.citations:
            console.print("\n[dim]sources:[/]")
            for c in a.citations:
                console.print(f"  [{c.reel_id}] {c.title[:50]} — {c.url}")
