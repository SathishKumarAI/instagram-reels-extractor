"""Commands that move reels through the pipeline: run, ingest, extract, render,
and the two that turn a saved collection into a local document.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ..config import Config
from .common import browser_spec, console, load_reels, open_in_browser


def register(app: typer.Typer) -> None:
    @app.command()
    def run(config: str = typer.Option("config.yaml", "--config", "-c")):
        """Full pipeline: ingest -> extract -> structure -> render."""
        cfg = Config.load(config)  # fail-fast: invalid config raises here
        from ..pipeline import run_pipeline

        def _progress(stage, cur, total, msg):
            console.print(f"  [{stage}] {msg}")

        reels, report = run_pipeline(cfg, config, progress=_progress)
        if not reels:
            console.print("[red]no reels ingested.[/]")
            raise typer.Exit(1)

        s = report.summary()
        console.rule("[bold green]Done")
        console.print(
            f"  reels: {s['total_reels']}  clean: {s['clean']}  with errors: {s['with_errors']}"
        )
        console.print(f"  markdown: {cfg.output_dir}/markdown")
        console.print(f"  pdfs:     {cfg.output_dir}/pdfs")
        console.print(f"  site:     {cfg.output_dir}/site/index.html")
        console.print(
            f"  report:   {cfg.output_dir}/run_report.json   log: {cfg.output_dir}/run.log"
        )

    @app.command()
    def ingest_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
        """Only ingest (download + metadata)."""
        cfg = Config.load(config)
        from ..ingest import ingest

        reels = ingest(cfg)
        console.print(f"ingested {len(reels)} reels into {cfg.data_dir}")

    @app.command()
    def extract_cmd(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        missing_vision: bool = typer.Option(
            False, "--missing-vision",
            help="only reels whose vision never landed (empty summary + frames on disk)",
        ),
    ):
        """Re-run extraction on already-ingested reels.

        `--missing-vision` is the repair pass for a run that died mid-vision: those
        reels are downloaded, so `sync` no longer counts them as new and would never
        revisit them — they stay summary-less until something looks.
        """
        cfg = Config.load(config)
        from ..extract import extract_all
        from ..modelreg import GpuContended
        from ..sources import local_gpu_blockers

        reels = load_reels(cfg)
        if missing_vision:
            # no video means no frames to look at — a text/carousel record is empty
            # for a reason, not for a lack of trying
            reels = [r for r in reels if not r.summary and r.video_path]
            console.print(f"{len(reels)} reel(s) with no summary")
        busy = local_gpu_blockers(cfg)
        for why in busy:
            console.print(f"[red]gpu busy:[/] {why}")
        if busy:
            raise typer.Exit(3)
        for r in reels:
            console.print(f"• {r.id}")
            try:
                extract_all(r, cfg)
            except GpuContended as e:
                console.print(f"[red]gpu contended:[/] {e}")
                raise typer.Exit(3) from e

    @app.command()
    def render_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
        """Re-render markdown + PDF + site from existing reel data."""
        cfg = Config.load(config)
        from ..render.docs_site import build_site
        from ..render.pdf import render_pdf
        from ..structure import render_markdown

        reels = load_reels(cfg)
        for r in reels:
            render_markdown(r, cfg)
            if cfg.output.pdf:
                render_pdf(r, cfg)
                render_markdown(r, cfg)
        if cfg.output.docs_site:
            build_site(reels, cfg)
        console.print("rendered.")

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
        from ..ingest.collection import fetch_collection

        urls = fetch_collection(url, browser=browser, limit=limit)
        if not urls:
            console.print("[yellow]no reels found in that collection.[/]")
            raise typer.Exit(1)
        if not print_only:
            Path(out).write_text("\n".join(urls) + "\n", encoding="utf-8")
            console.print(f"wrote [green]{len(urls)}[/] URLs -> {out}")
        for u in urls:
            console.print(u)

    @app.command()
    def collection(
        url: str = typer.Argument(..., help="Saved-collection URL or numeric id"),
        config: str = typer.Option("config.yaml", "--config", "-c"),
        browser: str = typer.Option(None, "--browser", "-b",
                                    help="browser to read IG cookies from (chrome | chrome:Default); "
                                         "defaults to config auth"),
        limit: int = typer.Option(200, "--limit"),
        open_doc: bool = typer.Option(True, "--open/--no-open", help="open the doc when built"),
    ):
        """URL -> local document. Fetch a saved collection, extract new reels, build a
        self-contained HTML doc + refresh the index, and open it. Idempotent: re-run
        after saving more reels and only the new ones are downloaded.
        """
        from datetime import date

        from ..collections import Manifest, parse_collection_url, save_manifest
        from ..docs import build_collection_doc, build_master_index
        from ..ingest.collection import fetch_collection
        from ..pipeline import run_pipeline

        cfg = Config.load(config)
        slug, cid = parse_collection_url(url)

        console.print(f"[cyan]fetching collection[/] {slug} ({cid})…")
        reel_urls = fetch_collection(url, browser=browser_spec(cfg, browser), limit=limit)
        if not reel_urls:
            console.print("[yellow]no reels found in that collection.[/]")
            raise typer.Exit(1)
        reel_ids = [u.rstrip("/").rsplit("/", 1)[-1] for u in reel_urls]
        console.print(f"  {len(reel_ids)} reels in collection")

        # Drive the existing pipeline over these URLs (resume skips already-downloaded).
        urls_file = cfg.data_dir / f".collection-{slug}.txt"
        urls_file.write_text("\n".join(reel_urls) + "\n", encoding="utf-8")
        cfg.source.type = "urls"
        cfg.source.urls_file = str(urls_file)
        cfg.source.resume = True
        console.print("[cyan]extracting new reels[/] (resume skips existing)…")
        run_pipeline(cfg, config, progress=lambda s, c, t, m: console.print(f"  [{s}] {m}"))

        m = Manifest(slug=slug, title=slug.replace("-", " ").title(), id=cid, url=url,
                     reel_ids=reel_ids, updated=date.today().isoformat())
        save_manifest(cfg.output_dir, m)
        doc, rendered = build_collection_doc(cfg, m)
        build_master_index(cfg)
        console.print(f"[green]✓[/] {rendered} reels → {doc}")
        if open_doc:
            open_in_browser(doc)

    @app.command()
    def consolidate(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        open_doc: bool = typer.Option(True, "--open/--no-open", help="open the index when built"),
    ):
        """Rebuild every collection document + the index from already-extracted data.

        No network, no re-extraction — use after restyling or when you just want the
        docs regenerated. With no collections yet, builds one 'all-saved' doc from the
        whole data pool.
        """
        cfg = Config.load(config)
        from ..docs import rebuild_all

        docs, index = rebuild_all(cfg)
        if not docs:
            console.print(
                "[yellow]nothing in data/ to consolidate. "
                "Run `reels-scrap collection <url>` first.[/]"
            )
            raise typer.Exit(1)
        console.print(f"[green]✓[/] built {len(docs)} doc(s) + index → {index}")
        if open_doc:
            open_in_browser(index)
