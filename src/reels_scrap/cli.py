"""CLI: run the full pipeline or individual stages from config.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from .config import Config
from .models import Reel

# Windows console/redirect defaults to cp1252 and dies on the ✓/✗ marks (and on any
# emoji in a caption). Do this before Console() is built so rich picks it up — it is
# what `PYTHONUTF8=1` was papering over.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

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
def index(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    full: bool = typer.Option(False, "--full", help="re-embed everything (after a model/schema change)"),
):
    """Build/refresh the local semantic search index over all reels.

    Incremental by default — only reels changed since the last index are embedded.
    """
    cfg = Config.load(config)
    from .search import build_index

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
        Path(out).write_text("\n".join(urls) + "\n", encoding="utf-8")
        console.print(f"wrote [green]{len(urls)}[/] URLs -> {out}")
    for u in urls:
        console.print(u)


def _open_in_browser(path: Path) -> None:
    import webbrowser

    webbrowser.open(path.resolve().as_uri())


def _browser_spec(cfg: Config, override: str | None = None) -> str:
    """The browser (and profile) to read Instagram cookies from: `chrome` or
    `chrome:Default`.

    An explicit --browser wins, then an exported `auth.cookies_file` (the only
    path that works on Windows once Chrome 127+ encrypts cookies app-bound),
    then config `auth`. Naming the profile matters — without one yt-dlp picks the
    most-recently-used profile, which is often not the one logged into Instagram.
    """
    spec = override or cfg.auth.cookies_file
    if not spec:
        name = cfg.auth.cookies_from_browser or "chrome"
        spec = f"{name}:{cfg.auth.browser_profile}" if cfg.auth.browser_profile else name
    if spec.endswith(".txt"):
        # the yt-dlp download path reads cfg.auth directly, not this spec — point
        # it at the same file so enumerate and download use one set of cookies
        cfg.auth.cookies_file = spec
    return spec


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

    from .collections import Manifest, parse_collection_url, save_manifest
    from .docs import build_collection_doc, build_master_index
    from .ingest.collection import fetch_collection
    from .pipeline import run_pipeline

    cfg = Config.load(config)
    slug, cid = parse_collection_url(url)

    console.print(f"[cyan]fetching collection[/] {slug} ({cid})…")
    reel_urls = fetch_collection(url, browser=_browser_spec(cfg, browser), limit=limit)
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
        _open_in_browser(doc)


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
    from .docs import rebuild_all

    docs, index = rebuild_all(cfg)
    if not docs:
        console.print("[yellow]nothing in data/ to consolidate. Run `reels-scrap collection <url>` first.[/]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/] built {len(docs)} doc(s) + index → {index}")
    if open_doc:
        _open_in_browser(index)


bench_app = typer.Typer(help="Model bench: one fixed sample of reels, many models, one report.")
app.add_typer(bench_app, name="bench")


@bench_app.command("sample")
def bench_sample(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    n: int = typer.Option(30, "--n", help="reels in the sample"),
    seed: int = typer.Option(0, "--seed", help="same seed + same corpus = same sample"),
) -> None:
    """Pick the fixed sample every model arm will be run over."""
    from .bench import build_sample, save_sample

    cfg = Config.load(config)
    s = build_sample(cfg, n=n, seed=seed)
    p = save_sample(cfg, s)
    console.print(f"[green]✓[/] {len(s.reel_ids)} reels → {p}")
    for genre, count in s.strata.items():
        console.print(f"    {genre:<16} {count}")


@bench_app.command("run")
def bench_run(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    profiles: list[str] = typer.Option(None, "--profile", "-p",
                                       help="profile name; repeatable. Omit for every installed one"),
    force: bool = typer.Option(False, "--force", help="re-run pairs that already have a variant"),
) -> None:
    """Run each profile over the stored sample. One model resident at a time."""
    from .bench import run as bench_run_all
    from .modelreg import status

    picks = list(profiles or [])
    if not picks:
        picks = [r["name"] for r in status() if r["installed"]]
        if not picks:
            console.print("[red]no installed models[/] — `reels-scrap models pull all`")
            raise typer.Exit(1)
    console.print(f"[cyan]bench[/] {len(picks)} arm(s): {', '.join(picks)}")

    def _p(profile: str, rid: str, i: int, total: int, state: str) -> None:
        mark = {"ok": "[green]✓[/]", "fail": "[red]✗[/]", "skip": "[dim]·[/]"}[state]
        console.print(f"  {mark} {profile} [{i}/{total}] {rid}")

    out = bench_run_all(picks, base_config=config, force=force, progress=_p)
    for name, s in out["profiles"].items():
        console.print(f"  [bold]{name}[/]: {s['done']} run, {s['skipped']} already stored, "
                      f"{s['failed']} failed")


@bench_app.command("report")
def bench_report(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    analysis: bool = typer.Option(True, "--analysis/--no-analysis",
                                  help="have Claude explain the differences (costs a call)"),
    examples: int = typer.Option(40, "--examples", help="disagreeing claims to feed the analysis"),
) -> None:
    """Write the metrics table and the why-they-differ analysis to docs/research/."""
    from .benchreport import write_report

    cfg = Config.load(config)
    p = write_report(cfg, with_analysis=analysis, examples=examples)
    console.print(f"[green]✓[/] {p}")


models_app = typer.Typer(help="Local vision models: what the bench can run, and how to install it.")
app.add_typer(models_app, name="models")


@models_app.command("list")
def models_list() -> None:
    """Every registry model, and whether it is installed. Reads ollama, not the network."""
    from .modelreg import status

    rows = status()
    if not rows:
        console.print("[yellow]no models.yaml at the repo root[/]")
        raise typer.Exit(1)
    for r in rows:
        mark = "[green]installed[/]" if r["installed"] else "[dim]missing[/]"
        console.print(
            f"  {mark:>22}  [bold]{r['name']}[/] ({r['tag']}, ~{r['vram_gb']}GB) — {r['role']}"
        )
    console.print(
        f"\n  {sum(r['installed'] for r in rows)}/{len(rows)} installed. "
        "Pull one with `reels-scrap models pull <name>`."
    )


@models_app.command("pull")
def models_pull(
    name: str = typer.Argument(..., help="registry model name, or 'all'"),
    yes: bool = typer.Option(False, "--yes", "-y", help="skip the download confirmation"),
) -> None:
    """Download a model and rebuild it at the context our frames need."""
    from .modelreg import load_registry, pull

    reg = load_registry()
    picks = reg if name == "all" else [e for e in reg if e.name == name]
    if not picks:
        console.print(f"[red]no model {name!r} in models.yaml[/] — try `models list`")
        raise typer.Exit(1)

    total = sum(e.vram_gb for e in picks)
    console.print(f"About to download {len(picks)} model(s), ~{total:.1f}GB:")
    for e in picks:
        console.print(f"  · [bold]{e.name}[/] ← {e.tag} (~{e.vram_gb}GB, ctx {e.num_ctx})")
    if not yes and not typer.confirm("Proceed?", default=False):
        raise typer.Exit(1)

    for e in picks:
        console.print(f"[cyan]pulling[/] {e.tag} …")
        r = pull(e)
        if r.get("skipped"):
            console.print(f"  [dim]skipped {e.name}: {r['skipped']}[/]")
        elif r["ok"]:
            console.print(f"  [green]✓[/] {e.name} ready ({r.get('modelfile', '')})")
        else:
            console.print(f"  [red]✗[/] {e.name}: {r['error']}")


@app.command(name="add-source")
def add_source_cmd(
    url: str = typer.Argument(..., help="Saved-collection URL (or reel-urls file for type=urls)"),
    name: str = typer.Option("", "--name", "-n", help="friendly name (defaults to slug)"),
    type: str = typer.Option("collection", "--type", "-t", help="collection | saved | urls"),
    sources: str = typer.Option("sources.json", "--sources", help="registry file"),
):
    """Register an Instagram source in sources.json for incremental `sync`."""
    from .sources import add_source

    s = add_source(url, name=name or None, type=type, path=sources)
    console.print(f"[green]✓[/] source [bold]{s.name}[/] ({s.type}) → {sources}")


@app.command(name="list-sources")
def list_sources_cmd(sources: str = typer.Option("sources.json", "--sources")):
    """Show the registered sources."""
    from .sources import load_sources

    rows = load_sources(sources)
    if not rows:
        console.print("[yellow]no sources registered. Add one with `reels-scrap add-source <url>`.[/]")
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
    retry_failed: bool = typer.Option(False, "--retry-failed", help="re-attempt dead-lettered ids"),
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
    from .ingest.collection import session_ok
    from .sources import poll_all

    # probe once up front: an expired cookie fails all 20 sources identically, and
    # 20 identical errors hide the one-line real cause (re-export the cookie file)
    spec = _browser_spec(cfg, browser)
    ok, why = session_ok(spec)
    if ok:
        console.print(f"[green]auth[/] {why} ({spec})")
    else:
        console.print(f"[red]auth: {why}[/]")
        console.print("[dim]every source will fail until this is fixed — "
                      "re-export cookies.txt (see docs/PRIVACY.md)[/]")

    results = poll_all(cfg, config, sources_file=sources, browser=spec,
                       build_docs=build_docs, retry_failed=retry_failed,
                       only=only or None)
    if not results:
        console.print("[yellow]no enabled sources. Add one with `reels-scrap add-source <url>`.[/]")
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
        _open_in_browser(cfg.output_dir / "collections" / "index.html")


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
    from .discover import discover

    s = discover(cfg, browser=_browser_spec(cfg, browser), max_requests=max_requests,
                 authors=authors, hashtags=hashtags, min_score=min_score)
    console.rule("[bold green]discover")
    console.print(f"  found [cyan]{s['found']}[/] · kept [green]{s['kept']}[/] "
                  f"· pending review [bold]{s['pending']}[/]")
    console.print(f"  requests {s['requests_used']}/{s['request_budget']}")
    if s["stopped_early"]:
        console.print(f"  [yellow]stopped early:[/] {s['stopped_early']}")


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
