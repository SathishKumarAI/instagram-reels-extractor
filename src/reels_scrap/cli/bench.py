"""The research sub-apps: `bench` (one sample, many models) and `models` (install).

Both are `typer.Typer` groups rather than flat commands because they are a
workflow — sample, run, report — not single actions.
"""

from __future__ import annotations

import typer

from ..config import Config
from .common import console


def register(app: typer.Typer) -> None:
    bench_app = typer.Typer(
        help="Model bench: one fixed sample of reels, many models, one report."
    )
    app.add_typer(bench_app, name="bench")

    models_app = typer.Typer(
        help="Local vision models: what the bench can run, and how to install it."
    )
    app.add_typer(models_app, name="models")

    @bench_app.command("sample")
    def bench_sample(
        config: str = typer.Option("config.yaml", "--config", "-c"),
        n: int = typer.Option(30, "--n", help="reels in the sample"),
        seed: int = typer.Option(0, "--seed", help="same seed + same corpus = same sample"),
    ) -> None:
        """Pick the fixed sample every model arm will be run over."""
        from ..bench import build_sample, save_sample

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
        from ..bench import run as bench_run_all
        from ..modelreg import status

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
        from ..benchreport import write_report

        cfg = Config.load(config)
        p = write_report(cfg, with_analysis=analysis, examples=examples)
        console.print(f"[green]✓[/] {p}")

    @models_app.command("list")
    def models_list() -> None:
        """Every registry model, and whether it is installed. Reads ollama, not the network."""
        from ..modelreg import status

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
        from ..modelreg import load_registry, pull

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
