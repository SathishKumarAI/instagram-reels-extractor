"""Numbers and downloads: /api/stats and the csv / md / xlsx exports.

The only place that prices tokens. `cost_usd` on a record is real when the CLI
reported it; everything else here is an estimate and says so.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...config import Config
from ...models import Reel
from ..deps import load_reels
from ..schemas import CategoryStat, Stats

# rough USD per 1M tokens by model family (Claude). Used for an estimate only.
PRICES = {"opus": (15.0, 75.0), "sonnet": (3.0, 15.0), "haiku": (0.8, 4.0)}


def price(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for k, v in PRICES.items():
        if k in m:
            return v
    return PRICES["sonnet"]


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    def _export_reels(ids: str | None) -> list[Reel]:
        """All reels, or just the given comma-separated ids (order preserved)."""
        reels = load_reels(cfg)
        if not ids:
            return reels
        want = [i for i in (x.strip() for x in ids.split(",")) if i]
        by_id = {r.id: r for r in reels}
        return [by_id[i] for i in want if i in by_id]

    @router.get("/api/stats", response_model=Stats)
    def stats() -> Stats:
        from collections import Counter, defaultdict

        pin, pout = price(cfg.extract.vision_model)
        reels = load_reels(cfg)
        cats: dict[str, dict] = defaultdict(lambda: {"reels": 0, "in": 0, "out": 0, "cost": 0.0})
        tags: Counter = Counter()
        tin = tout = 0
        tcost = 0.0
        for r in reels:
            g = r.genre or "uncategorized"
            i, o = int(r.tokens.get("input", 0)), int(r.tokens.get("output", 0))
            # real cost from the CLI envelope when present, else estimate from tokens
            c = r.tokens.get("cost_usd")
            c = float(c) if c else round(i / 1e6 * pin + o / 1e6 * pout, 4)
            cats[g]["reels"] += 1
            cats[g]["in"] += i
            cats[g]["out"] += o
            cats[g]["cost"] += c
            tin += i
            tout += o
            tcost += c
            tags.update(r.tags)

        categories = [
            CategoryStat(genre=g, reels=v["reels"], tokens_in=v["in"], tokens_out=v["out"],
                         cost_usd=round(v["cost"], 2))
            for g, v in sorted(cats.items(), key=lambda kv: -kv[1]["reels"])
        ]
        return Stats(
            total_reels=len(reels), tokens_in=tin, tokens_out=tout,
            cost_usd=round(tcost, 2),
            cost_note=("real cost from claude-cli when available (mostly cached CLI "
                       "system-prompt/tools, not reel content); $0 on subscription. "
                       "Set ANTHROPIC_API_KEY for the ~15x-cheaper API backend."),
            categories=categories, top_tags=[[t, n] for t, n in tags.most_common(30)],
        )

    @router.get("/api/export.csv")
    def export_csv(ids: str | None = None):
        import csv
        import io

        from fastapi.responses import Response

        cols = ["id", "title", "author", "genre", "tags", "likes", "comments",
                "views", "duration", "tokens_in", "tokens_out", "summary",
                "transcript", "url"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in _export_reels(ids):
            w.writerow([
                r.id, r.title, r.author, r.genre, ", ".join(r.tags),
                r.likes or "", r.comments or "", r.views or "",
                r.duration or "", r.tokens.get("input", 0), r.tokens.get("output", 0),
                (r.summary or "").replace("\n", " "),
                (r.transcript_text or "").replace("\n", " "), r.url,
            ])
        return Response(
            content=buf.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=reels.csv"},
        )

    @router.get("/api/export.md")
    def export_md(ids: str | None = None):
        from fastapi.responses import Response

        lines = ["# Reels export\n"]
        by_genre: dict[str, list] = {}
        for r in _export_reels(ids):
            by_genre.setdefault(r.genre or "uncategorized", []).append(r)
        for g in sorted(by_genre):
            lines.append(f"\n## {g}\n")
            for r in by_genre[g]:
                tags = " ".join(f"#{t}" for t in r.tags)
                lines.append(f"- **[{r.title or r.id}]({r.url})** — {r.author}  {tags}")
                if r.summary:
                    lines.append(f"  - {r.summary}")
        return Response("\n".join(lines), media_type="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=reels.md"})

    @router.get("/api/export.xlsx")
    def export_xlsx(ids: str | None = None):
        try:
            from openpyxl import Workbook
        except ImportError as e:
            raise HTTPException(
                501, "xlsx export needs openpyxl — `pip install openpyxl` (or use export.csv)"
            ) from e
        import io

        from fastapi.responses import Response

        wb = Workbook()
        ws = wb.active
        ws.title = "reels"
        ws.append(["id", "title", "author", "genre", "tags", "likes", "comments",
                   "tokens_in", "tokens_out", "summary", "url"])
        for r in _export_reels(ids):
            ws.append([r.id, r.title, r.author, r.genre, ", ".join(r.tags),
                       r.likes or 0, r.comments or 0, r.tokens.get("input", 0),
                       r.tokens.get("output", 0), (r.summary or "")[:1000], r.url])
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=reels.xlsx"},
        )

    return router
