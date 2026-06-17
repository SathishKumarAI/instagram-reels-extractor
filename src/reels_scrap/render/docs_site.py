"""Build a professional mkdocs-material docs site: page-per-reel + master index."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from ..config import Config
from ..models import Reel

MKDOCS_YML = {
    "site_name": "Instagram Reels Archive",
    "site_description": "Reels transcribed, summarized, and documented.",
    "theme": {
        "name": "material",
        "palette": [
            {
                "scheme": "slate",
                "primary": "deep purple",
                "accent": "purple",
                "toggle": {"icon": "material/weather-night", "name": "Light"},
            },
            {
                "scheme": "default",
                "primary": "deep purple",
                "accent": "purple",
                "toggle": {"icon": "material/weather-sunny", "name": "Dark"},
            },
        ],
        "features": ["navigation.instant", "navigation.top", "search.suggest", "content.code.copy"],
    },
    "markdown_extensions": ["tables", "admonition", "attr_list", "md_in_html"],
}


def _index_markdown(reels: list[Reel]) -> str:
    lines = [
        "# Instagram Reels Archive",
        "",
        f"**{len(reels)}** reels archived. Each page has caption, transcript, "
        "on-screen text, AI summary, and a downloadable PDF.",
        "",
        "| Title | Author | Date | Page | PDF |",
        "|-------|--------|------|------|-----|",
    ]
    for r in sorted(reels, key=lambda x: (x.timestamp or x.scraped_at) or 0, reverse=True):
        date = r.timestamp.strftime("%Y-%m-%d") if r.timestamp else "—"
        title = (r.title or r.id).replace("|", "\\|")[:60]
        page = f"[open](reels/{r.id}.md)"
        pdf = f"[PDF](pdfs/{r.id}.pdf)" if r.pdf_path else "—"
        lines.append(f"| {title} | {r.author or '—'} | {date} | {page} | {pdf} |")
    lines.append("")
    return "\n".join(lines)


def build_site(reels: list[Reel], cfg: Config) -> Path:
    out_root = cfg.output_dir
    src = out_root / "site_src"
    docs = src / "docs"
    reels_dir = docs / "reels"
    pdfs_dir = docs / "pdfs"
    for d in (reels_dir, pdfs_dir):
        d.mkdir(parents=True, exist_ok=True)

    md_dir = out_root / "markdown"
    nav_reels = []
    for r in reels:
        # copy per-reel markdown into site
        src_md = md_dir / f"{r.id}.md"
        if src_md.exists():
            shutil.copy(src_md, reels_dir / f"{r.id}.md")
        # copy pdf + thumbnail into site
        if r.pdf_path and Path(r.pdf_path).exists():
            shutil.copy(r.pdf_path, pdfs_dir / f"{r.id}.pdf")
        if r.thumbnail_path:
            thumb = cfg.data_dir / r.thumbnail_path
            if thumb.exists():
                (reels_dir / "assets").mkdir(exist_ok=True)
                shutil.copy(thumb, reels_dir / "assets" / r.thumbnail_path)
        nav_reels.append({r.title[:50] or r.id: f"reels/{r.id}.md"})

    (docs / "index.md").write_text(_index_markdown(reels))

    cfg_yml = dict(MKDOCS_YML)
    cfg_yml["docs_dir"] = "docs"
    cfg_yml["site_dir"] = str((out_root / "site").resolve())
    cfg_yml["nav"] = [{"Home": "index.md"}, {"Reels": nav_reels}]
    (src / "mkdocs.yml").write_text(yaml.safe_dump(cfg_yml, sort_keys=False))

    subprocess.run(
        ["mkdocs", "build", "-f", str(src / "mkdocs.yml"), "--quiet"], check=True
    )
    return out_root / "site"
