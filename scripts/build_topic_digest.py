#!/usr/bin/env python3
"""Digest every extracted reel into a single "what did I save?" reference doc.

Groups the tools, fonts and themes/design resources mentioned across the whole
archive — pulled from the vision-extracted structured fields, provenance facts
and captions — into one markdown file with a link back to each source reel.

    python scripts/build_topic_digest.py [--data data] [--out output/tools-fonts-themes.md]

Re-runnable: it only reads the extracted sidecars, so run it again after a sync.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# Buckets, most specific first — a mention lands in the first bucket that matches.
BUCKETS: list[tuple[str, re.Pattern]] = [
    ("Fonts & typography", re.compile(
        r"\b(font|fonts|typeface|typograph\w*|google fonts|fontshare|typewolf|"
        r"satoshi|poppins|montserrat|helvetica|geist|inter\b|serif|sans-serif)\b", re.IGNORECASE)),
    ("Themes, palettes & color", re.compile(
        r"\b(theme|themes|colou?r scheme|colorscheme|palette|swatch|catppuccin|dracula|"
        r"nord\b|tokyo ?night|gruvbox|icon pack|wallpaper|dark mode)\b", re.IGNORECASE)),
    ("Design & UI resources", re.compile(
        r"\b(figma|ui kit|ui/ux|wireframe|mockup|component library|shadcn|tailwind|"
        r"animation|framer|webflow|design system|illustration|3d)\b", re.IGNORECASE)),
    ("Tools & apps", re.compile(r".", re.DOTALL)),  # catch-all
]

URL = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9-]+\.[a-z]{2,}(?:/[^\s,)\]]*)?)", re.IGNORECASE)
# Bare words that are never a useful "resource" on their own.
NOISE = re.compile(r"^(the|a|an|it|this|that|and|or|link in bio|dm|comment)$", re.IGNORECASE)


def load_collections(out_dir: Path) -> dict[str, list[str]]:
    """reel id -> the saved collections it belongs to."""
    membership: dict[str, list[str]] = defaultdict(list)
    for f in sorted((out_dir / "collections").glob("*.json")):
        try:
            m = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        title = m.get("title") or m.get("slug") or f.stem
        for rid in m.get("reel_ids", []):
            membership[rid].append(title)
    return membership


def mentions(d: dict) -> list[str]:
    """Every named resource this reel points at, from the structured extraction."""
    s = d.get("structured") or {}
    items: list[str] = []
    if isinstance(s, dict):
        for key in ("tools", "resources", "links"):
            items += [str(v) for v in (s.get(key) or []) if v]
        if s.get("name"):
            items.append(f"{s['name']}" + (f" — {s['link']}" if s.get("link") else ""))
    for fact in d.get("facts") or []:
        text = fact.get("text", "") if isinstance(fact, dict) else str(fact)
        if URL.search(text) and len(text) < 200:
            items.append(text.strip())
    return [i.strip() for i in items if i.strip() and not NOISE.match(i.strip())]


def bucket_for(text: str) -> str:
    for name, pattern in BUCKETS:
        if pattern.search(text):
            return name
    return BUCKETS[-1][0]


# Catppuccin Mocha, matching the collection docs.
HTML_SHELL = """<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tools, fonts &amp; themes</title>
<style>
:root {{ --base:#1e1e2e; --mantle:#181825; --surface:#313244; --text:#cdd6f4;
        --subtext:#a6adc8; --mauve:#cba6f7; --blue:#89b4fa; --green:#a6e3a1; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:2rem 1.25rem 4rem; background:var(--base); color:var(--text);
       font:16px/1.6 ui-sans-serif,system-ui,'Inter',sans-serif; }}
main {{ max-width:52rem; margin:0 auto; }}
h1 {{ color:var(--mauve); font-size:1.9rem; margin:0 0 .25rem; }}
h2 {{ color:var(--green); font-size:1.25rem; margin:2.5rem 0 1rem;
     border-bottom:1px solid var(--surface); padding-bottom:.4rem;
     position:sticky; top:0; background:var(--base); }}
p {{ color:var(--subtext); }}
p strong a {{ color:var(--blue); text-decoration:none; }}
p strong a:hover {{ text-decoration:underline; }}
p:has(strong) {{ margin:1.4rem 0 .35rem; color:var(--text); }}
em {{ color:var(--mauve); font-style:normal; font-size:.85rem; }}
ul {{ margin:.25rem 0 0; padding-left:1.1rem; }}
li {{ color:var(--subtext); margin:.15rem 0; }}
</style>
<main>
{body}
</main>
"""


def render_html(md_text: str) -> str:
    """Self-contained dark HTML view of the digest — links stay clickable."""
    import markdown

    return HTML_SHELL.format(body=markdown.markdown(md_text, extensions=["extra"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--output-dir", default="output")
    ap.add_argument("--out", default="output/tools-fonts-themes.md")
    args = ap.parse_args()

    data_dir, out_dir = Path(args.data), Path(args.output_dir)
    collections = load_collections(out_dir)
    grouped: dict[str, list[dict]] = defaultdict(list)
    reels = 0

    for f in sorted(data_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        found = mentions(d)
        if not found:
            continue
        reels += 1
        # Context = the reel's own text, so a font reel files its tools under fonts.
        context = " ".join(str(d.get(k) or "") for k in ("title", "summary", "caption"))
        for item in dict.fromkeys(found):  # de-dupe, keep order
            grouped[bucket_for(item + " " + context)].append({
                "item": item,
                "reel": d.get("id", f.stem),
                "url": d.get("url", ""),
                "title": (d.get("title") or "").strip(),
                "collections": collections.get(d.get("id", f.stem), []),
            })

    lines = [
        "# Tools, fonts & themes across the saved archive",
        "",
        f"Built from {reels} extracted reels. Each entry links back to the reel it came from.",
        "",
    ]
    for name, _ in BUCKETS:
        rows = grouped.get(name) or []
        if not rows:
            continue
        lines += [f"## {name}  ({len(rows)})", ""]
        by_reel: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_reel[r["reel"]].append(r)
        for rid, rs in by_reel.items():
            head = rs[0]
            where = f" · _{', '.join(head['collections'])}_" if head["collections"] else ""
            lines.append(f"**[{head['title'] or rid}]({head['url']})**{where}")
            lines += [f"- {r['item']}" for r in rs]
            lines.append("")
    md = "\n".join(lines) + "\n"
    Path(args.out).write_text(md)
    html_path = Path(args.out).with_suffix(".html")
    html_path.write_text(render_html(md))
    print(f"wrote {args.out} + {html_path} — "
          f"{sum(len(v) for v in grouped.values())} entries from {reels} reels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
