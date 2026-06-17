"""Per-reel PDF via weasyprint (markdown -> HTML -> PDF). Optional combined PDF."""

from __future__ import annotations

import re
from pathlib import Path

import markdown as md

from ..config import Config
from ..models import Reel

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"
CSS_PATH = TEMPLATES_DIR / "pdf.css"

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def _md_to_html(md_text: str, title: str) -> str:
    body_md = _FRONTMATTER.sub("", md_text, count=1)
    body = md.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"])
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{body}</body></html>"


def render_pdf(reel: Reel, cfg: Config) -> Path:
    from weasyprint import CSS, HTML

    if not reel.markdown_path or not Path(reel.markdown_path).exists():
        raise FileNotFoundError(f"markdown missing for {reel.id}")

    pdf_dir = cfg.output_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    out = pdf_dir / f"{reel.id}.pdf"

    md_text = Path(reel.markdown_path).read_text()
    html = _md_to_html(md_text, reel.title)
    # base_url = markdown dir so relative ../../data/<thumb> resolves
    base = Path(reel.markdown_path).parent
    HTML(string=html, base_url=str(base)).write_pdf(
        str(out), stylesheets=[CSS(str(CSS_PATH))]
    )
    reel.pdf_path = str(out)
    reel.save(cfg.data_dir)
    return out


def render_combined(reels: list[Reel], cfg: Config) -> Path | None:
    from pypdf import PdfWriter

    pdfs = [r.pdf_path for r in reels if r.pdf_path and Path(r.pdf_path).exists()]
    if not pdfs:
        return None
    out = cfg.output_dir / "all_reels.pdf"
    writer = PdfWriter()
    for r in reels:
        if r.pdf_path and Path(r.pdf_path).exists():
            writer.append(r.pdf_path, outline_item=r.title[:80])
    with out.open("wb") as f:
        writer.write(f)
    return out
