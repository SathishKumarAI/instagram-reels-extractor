"""Structure stage: Reel -> per-reel markdown (+ json sidecar already saved)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Config
from .models import Reel

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["regex_hash"] = lambda t: f"#{t}"
    env.filters["regex_at"] = lambda t: f"@{t}"

    def fmt_ts(seconds):
        if seconds is None:
            return "—"
        s = int(seconds)
        return f"{s // 60}:{s % 60:02d}"

    env.filters["fmt_ts"] = fmt_ts
    env.filters["is_list"] = lambda v: isinstance(v, (list, tuple))
    return env


def render_markdown(reel: Reel, cfg: Config) -> Path:
    """Write output/markdown/<id>.md. Returns path."""
    md_dir = cfg.output_dir / "markdown"
    md_dir.mkdir(parents=True, exist_ok=True)

    # relative links from markdown dir to data/output assets
    thumb_rel = ""
    if reel.thumbnail_path:
        thumb_rel = f"../../{cfg.paths.data_dir}/{reel.thumbnail_path}"
    pdf_rel = ""
    if reel.pdf_path:
        pdf_rel = f"../pdfs/{Path(reel.pdf_path).name}"

    tmpl = _env().get_template("reel.md.j2")
    text = tmpl.render(reel=reel, thumb_rel=thumb_rel, pdf_rel=pdf_rel)

    out = md_dir / f"{reel.id}.md"
    out.write_text(text)
    reel.markdown_path = str(out)
    reel.save(cfg.data_dir)
    return out
