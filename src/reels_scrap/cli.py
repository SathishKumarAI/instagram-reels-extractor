"""CLI: run the full pipeline or individual stages from config.yaml."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from .config import Config
from .models import Reel

load_dotenv()
app = typer.Typer(add_completion=False, help="Instagram reels -> text -> PDF -> docs.")
console = Console()


def _load_reels(cfg: Config) -> list[Reel]:
    """Load previously-ingested reels from data_dir json sidecars."""
    return [Reel.load(p) for p in sorted(cfg.data_dir.glob("*.json"))]


@app.command()
def run(config: str = typer.Option("config.yaml", "--config", "-c")):
    """Full pipeline: ingest -> extract -> structure -> render."""
    cfg = Config.load(config)  # fail-fast: invalid config raises here
    from .pipeline import run_pipeline

    def _progress(stage, cur, total, msg):
        console.print(f"  [{stage}] {msg}")

    reels, report = run_pipeline(cfg, config, progress=_progress)
    if not reels:
        console.print("[red]no reels ingested.[/]")
        raise typer.Exit(1)

    s = report.summary()
    console.rule("[bold green]Done")
    console.print(f"  reels: {s['total_reels']}  clean: {s['clean']}  with errors: {s['with_errors']}")
    console.print(f"  markdown: {cfg.output_dir}/markdown")
    console.print(f"  pdfs:     {cfg.output_dir}/pdfs")
    console.print(f"  site:     {cfg.output_dir}/site/index.html")
    console.print(f"  report:   {cfg.output_dir}/run_report.json   log: {cfg.output_dir}/run.log")


@app.command()
def ingest_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
    """Only ingest (download + metadata)."""
    cfg = Config.load(config)
    from .ingest import ingest

    reels = ingest(cfg)
    console.print(f"ingested {len(reels)} reels into {cfg.data_dir}")


@app.command()
def extract_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
    """Re-run extraction on already-ingested reels."""
    cfg = Config.load(config)
    from .extract import extract_all

    reels = _load_reels(cfg)
    for r in reels:
        console.print(f"• {r.id}")
        extract_all(r, cfg)


@app.command()
def render_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
    """Re-render markdown + PDF + site from existing reel data."""
    cfg = Config.load(config)
    from .render.docs_site import build_site
    from .render.pdf import render_pdf
    from .structure import render_markdown

    reels = _load_reels(cfg)
    for r in reels:
        render_markdown(r, cfg)
        if cfg.output.pdf:
            render_pdf(r, cfg)
            render_markdown(r, cfg)
    if cfg.output.docs_site:
        build_site(reels, cfg)
    console.print("rendered.")


@app.command()
def index(config: str = typer.Option("config.yaml", "--config", "-c")):
    """Build/refresh the local semantic search index over all reels."""
    cfg = Config.load(config)
    from .search import build_index

    n = build_index(cfg)
    console.print(f"indexed [green]{n}[/] vectors.")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language query"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
    k: int = typer.Option(8, "-k"),
):
    """Semantic search across the reel archive."""
    cfg = Config.load(config)
    from .search import search as do_search

    for m in do_search(cfg, query, k):
        ts = f" @{int(m['timestamp'])}s" if m.get("timestamp") is not None else ""
        console.print(
            f"[dim]{m['score']:.2f}[/] [{m['kind']}{ts}] "
            f"[bold]{m['title'][:50]}[/] — {m['text'][:90]}\n      {m['url']}"
        )


@app.command(name="fetch-collection")
def fetch_collection_cmd(
    url: str = typer.Argument(..., help="Saved-collection URL or numeric id"),
    out: str = typer.Option("reels.txt", "--out", "-o", help="write URLs here"),
    browser: str = typer.Option("chrome", "--browser", "-b"),
    limit: int = typer.Option(200, "--limit"),
    print_only: bool = typer.Option(False, "--print-only"),
):
    """Enumerate a named Instagram saved collection into reel URLs.

    Reuses your logged-in browser cookies (no password). Writes one URL per line
    to --out (default reels.txt), ready for `reels-scrap run`.
    """
    from .ingest.collection import fetch_collection

    urls = fetch_collection(url, browser=browser, limit=limit)
    if not urls:
        console.print("[yellow]no reels found in that collection.[/]")
        raise typer.Exit(1)
    if not print_only:
        Path(out).write_text("\n".join(urls) + "\n")
        console.print(f"wrote [green]{len(urls)}[/] URLs -> {out}")
    for u in urls:
        console.print(u)


@app.command()
def serve(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload"),
):
    """Launch the research API (Knowledge Base + Research Chat) + UI if built."""
    import uvicorn

    from .api import create_app

    console.print(f"[green]serving[/] http://{host}:{port}  (API under /api)")
    uvicorn.run(create_app(config), host=host, port=port, reload=reload)


@app.command(name="knowledge")
def knowledge_cmd(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    synthesize: bool = typer.Option(False, "--synthesize", help="Claude topic overviews (costs calls)"),
):
    """Rebuild the aggregated Knowledge Base from the reel corpus."""
    cfg = Config.load(config)
    from .knowledge import build_knowledge

    kb = build_knowledge(cfg)
    if synthesize:
        from .knowledge.synthesize import synthesize_topics

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
    from .chat import answer_question

    a = answer_question(cfg, question, k=k)
    if a.answer:
        console.print(a.answer)
    else:
        console.print(f"[yellow]{a.note}[/]")
    if a.citations:
        console.print("\n[dim]sources:[/]")
        for c in a.citations:
            console.print(f"  [{c.reel_id}] {c.title[:50]} — {c.url}")


@app.command()
def login(username: str = typer.Argument(..., help="Your Instagram username")):
    """Create a local Instagram session (interactive). Password/2FA stay on your machine.

    Stores an encrypted session under ~/.config/instaloader — this code only ever
    LOADS that session, it never reads or stores your password.
    """
    import subprocess

    console.print(
        f"[yellow]Launching interactive login for[/] {username}. "
        "Password is entered locally and never logged."
    )
    rc = subprocess.call(["instaloader", "--login", username])
    if rc == 0:
        console.print(
            f"[green]✓ session saved.[/] Set in config.yaml: "
            f"source.login=true, source.username={username}"
        )
    else:
        console.print(f"[red]login failed (exit {rc}).[/]")
        raise typer.Exit(rc)


def main():
    app()


if __name__ == "__main__":
    main()
