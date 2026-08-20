"""Everything that talks to Instagram: sources, sync, discover, login.

`sync` is the entry point that gets used daily. Both guards it runs before
spending a request — GPU busy, dead cookie — exist because the failure they catch
is expensive and looks like something else.
"""

from __future__ import annotations

import typer

from ..config import Config
from .common import browser_spec, console, open_in_browser


def register(app: typer.Typer) -> None:
    @app.command(name="add-source")
    def add_source_cmd(
        url: str = typer.Argument(..., help="Saved-collection URL (or reel-urls file for type=urls)"),
        name: str = typer.Option("", "--name", "-n", help="friendly name (defaults to slug)"),
        type: str = typer.Option("collection", "--type", "-t", help="collection | saved | urls"),
        sources: str = typer.Option("sources.json", "--sources", help="registry file"),
    ):
        """Register an Instagram source in sources.json for incremental `sync`."""
        from ..sources import add_source

        s = add_source(url, name=name or None, type=type, path=sources)
        console.print(f"[green]✓[/] source [bold]{s.name}[/] ({s.type}) → {sources}")

    @app.command(name="list-sources")
    def list_sources_cmd(sources: str = typer.Option("sources.json", "--sources")):
        """Show the registered sources."""
        from ..sources import load_sources

        rows = load_sources(sources)
        if not rows:
            console.print(
                "[yellow]no sources registered. Add one with `reels-scrap add-source <url>`.[/]"
            )
            raise typer.Exit(1)
        for s in rows:
            flag = "[green]on[/]" if s.enabled else "[dim]off[/]"
            console.print(f"  {flag} [bold]{s.name}[/] ({s.type})  {s.url}")

    @app.command()
    def sync(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        sources: str = typer.Option("sources.json", "--sources"),
        browser: str = typer.Option(None, "--browser", "-b",
                                    help="chrome | chrome:Default — defaults to config auth"),
        build_docs: bool = typer.Option(True, "--docs/--no-docs", help="rebuild docs after sync"),
        retry_failed: bool = typer.Option(False, "--retry-failed",
                                          help="re-attempt dead-lettered ids"),
        only: list[str] = typer.Option(None, "--only", help="limit to named source(s); repeatable"),
        claude_only: bool = typer.Option(
            False, "--claude-only/--full",
            help="Claude vision only — skip CPU whisper transcript + OCR (faster)",
        ),
        backend: str = typer.Option(
            None, "--backend", "-B",
            help="override vision backend: claude-cli | api | local (your GPU box)",
        ),
        open_index: bool = typer.Option(False, "--open", help="open the master index when done"),
    ):
        """Incrementally sync every enabled source: fetch latest reels, dedup against
        what's already downloaded, ingest only the new ones, refresh docs + state.

        Idempotent — re-run any time; nothing is re-downloaded and no duplicates are
        created. This is the "every run gets the latest reels" entry point.

        --claude-only skips the CPU-heavy transcript/OCR stages and uses only Claude
        vision — much faster; flip back with --full.
        """
        cfg = Config.load(config)
        if claude_only:
            cfg.extract.transcript = False
            cfg.extract.ocr = False
            cfg.extract.vision = True
            console.print("[cyan]claude-only mode[/] — transcript/OCR off, vision on")
        if backend:
            if backend not in {"claude-cli", "api", "local"}:
                console.print(f"[red]invalid --backend {backend!r}[/] (claude-cli|api|local)")
                raise typer.Exit(2)
            if backend == "local" and not cfg.extract.vision_local.base_url:
                console.print("[red]--backend local needs extract.vision_local.base_url in config[/]")
                raise typer.Exit(2)
            cfg.extract.vision_backend = backend
            console.print(f"[cyan]vision backend[/] → {backend}"
                          + (f" ({cfg.extract.vision_local.model})" if backend == "local" else ""))
        from ..ingest.collection import session_ok
        from ..sources import local_gpu_blockers, poll_all

        # a busy GPU makes local vision time out on every reel (240s instead of ~8s)
        # and dead-letter it — check before spending an Instagram request on anything
        busy = local_gpu_blockers(cfg)
        for why in busy:
            console.print(f"[red]gpu busy:[/] {why}")
        if busy:
            console.print("[dim]sync is incremental — wait for the GPU and re-run, "
                          "or REELS_IGNORE_GPU=1 to run anyway[/]")
            raise typer.Exit(3)

        # probe once up front: an expired cookie fails all 20 sources identically, and
        # 20 identical errors hide the one-line real cause (re-export the cookie file)
        spec = browser_spec(cfg, browser)
        ok, why = session_ok(spec)
        if ok:
            console.print(f"[green]auth[/] {why} ({spec})")
        else:
            console.print(f"[red]auth: {why}[/]")
            console.print("[dim]every source will fail until this is fixed — "
                          "re-export cookies.txt (see docs/PRIVACY.md)[/]")

        from ..modelreg import GpuContended

        try:
            results = poll_all(cfg, config, sources_file=sources, browser=spec,
                               build_docs=build_docs, retry_failed=retry_failed,
                               only=only or None)
        except GpuContended as e:
            console.print(f"[red]gpu contended:[/] {e}")
            console.print("[dim]what landed is saved — sync is incremental, "
                          "re-run when the card is free[/]")
            raise typer.Exit(3) from e
        if not results:
            console.print(
                "[yellow]no enabled sources. Add one with `reels-scrap add-source <url>`.[/]"
            )
            raise typer.Exit(1)

        console.rule("[bold green]sync")
        total_new = 0
        for r in results:
            total_new += r.ingested
            if r.rate_limited:
                console.print(f"  [yellow]⏳[/] {r.name}: {r.error}")
            elif r.error:
                console.print(f"  [red]✗[/] {r.name}: {r.error}")
            else:
                console.print(
                    f"  [green]✓[/] [bold]{r.name}[/]  current={r.current} "
                    f"new={r.new} ingested={r.ingested} deduped={r.skipped}"
                )
        console.print(f"\n[cyan]{total_new}[/] new reel(s) ingested across {len(results)} source(s).")
        if open_index and build_docs:
            open_in_browser(cfg.output_dir / "collections" / "index.html")

    @app.command(name="discover")
    def discover_cmd(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        browser: str = typer.Option(None, "--browser", "-b"),
        max_requests: int = typer.Option(40, "--max-requests", help="hard ceiling for this run"),
        authors: int = typer.Option(6, "--authors", help="how many saved-from creators to check"),
        hashtags: int = typer.Option(4, "--hashtags", help="how many of your top tags to check"),
        min_score: float = typer.Option(0.35, "--min-score", help="drop candidates below this"),
    ):
        """Propose reels worth saving, from creators you already save and your top tags.

        Reads only, downloads nothing — accepted candidates are queued for the next
        sync. Instagram rate-limits hard, so the run has a request budget and stops on
        the first 429 rather than retrying into a block.
        """
        cfg = Config.load(config)
        from ..discover import discover

        s = discover(cfg, browser=browser_spec(cfg, browser), max_requests=max_requests,
                     authors=authors, hashtags=hashtags, min_score=min_score)
        console.rule("[bold green]discover")
        console.print(f"  found [cyan]{s['found']}[/] · kept [green]{s['kept']}[/] "
                      f"· pending review [bold]{s['pending']}[/]")
        console.print(f"  requests {s['requests_used']}/{s['request_budget']}")
        if s["stopped_early"]:
            console.print(f"  [yellow]stopped early:[/] {s['stopped_early']}")

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
