"""Render a self-contained, professional HTML document from a set of reels.

One collection -> one HTML file. Thumbnails are embedded as base64 data URIs so
the file is portable (open it anywhere, no assets folder). This module is
deliberately dependency-free (stdlib only) and consumes plain reel JSON dicts, so
it can render whatever the extractors have already written to `data/` without
importing the pipeline or its heavy ML deps.

    from reels_scrap.render.consolidated import render_doc, render_index
    html = render_doc(reels, DocMeta(title="Front-End", source_url=url, slug="front-end"))
"""
from __future__ import annotations

import base64
import html
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

GENRE_ORDER = ["product", "tutorial", "educational", "news", "other"]
GENRE_LABEL = {
    "product": "Products & Tools",
    "tutorial": "Tutorials & Walkthroughs",
    "educational": "Explainers & Concepts",
    "news": "News & Signals",
    "other": "Other",
}


@dataclass
class DocMeta:
    """Header/identity for one consolidated collection document."""

    title: str
    slug: str
    source_url: str = ""
    subtitle: str = ""


@dataclass
class CollectionCard:
    """One collection as it appears on the master index."""

    slug: str
    title: str
    count: int
    updated: str = ""
    source_url: str = ""
    thumbs: list[str] = field(default_factory=list)  # up to 3 data URIs


# ---------------------------------------------------------------- helpers


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def data_uri(path: str | Path | None) -> str | None:
    if not path:
        return None
    path = str(path)
    if not os.path.exists(path):
        return None
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as fh:
        return f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"


def _int(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


def _ts(seconds) -> str:
    try:
        s = int(float(seconds))
        return f"{s // 60}:{s % 60:02d}"
    except (TypeError, ValueError):
        return "—"


def _date(iso) -> str:
    if not iso:
        return ""
    s = str(iso)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except ValueError:
        return s[:10]


def _norm_genre(g) -> str:
    g = (g or "other").lower()
    return g if g in GENRE_LABEL else "other"


LANG_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ur": "Urdu", "bn": "Bengali",
    "pa": "Punjabi", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German", "ar": "Arabic",
    "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "id": "Indonesian",
}


def _lang(code: str) -> str:
    return LANG_NAMES.get((code or "").lower(), (code or "").upper() or "another language")


def _quality_badge(d: dict) -> str:
    """A small warning when the transcript was machine-translated, so the reader
    knows the English is second-hand and should verify against the reel."""
    if not d.get("transcript_translated"):
        return ""
    return (
        f"<span class='badge warn' title='Spoken in {esc(_lang(d.get('transcript_language')))}; "
        "auto-translated to English by Whisper — verify against the reel'>"
        f"⚠ translated from {esc(_lang(d.get('transcript_language')))}</span>"
    )


# ---------------------------------------------------------------- fragments


def _structured(struct: dict) -> str:
    if not struct:
        return ""
    rows = []
    for key, val in struct.items():
        label = esc(key.replace("_", " ").title())
        if isinstance(val, list):
            if not val:
                continue
            body = "<ul class='mini'>" + "".join(f"<li>{esc(v)}</li>" for v in val) + "</ul>"
        elif isinstance(val, dict):
            body = "".join(f"<div><b>{esc(k)}</b> {esc(v)}</div>" for k, v in val.items())
        else:
            sval = str(val).strip()
            if not sval:
                continue
            if key.lower() == "link" and " " not in sval:
                href = sval if sval.startswith("http") else f"https://{sval}"
                body = f"<a class='ext' href='{esc(href)}' target='_blank' rel='noopener'>{esc(sval)}</a>"
            else:
                body = esc(sval)
        rows.append(f"<div class='field'><dt>{label}</dt><dd>{body}</dd></div>")
    return f"<dl class='fields'>{''.join(rows)}</dl>" if rows else ""


def _facts(facts: list) -> str:
    if not facts:
        return ""
    rows = []
    for f in facts:
        if isinstance(f, dict):
            rows.append(f"<tr><td class='ts'>{_ts(f.get('timestamp'))}</td><td>{esc(f.get('text'))}</td></tr>")
        else:
            rows.append(f"<tr><td class='ts'>—</td><td>{esc(f)}</td></tr>")
    return (
        "<details class='facts'><summary>Key facts with provenance "
        f"<span class='muted'>({len(facts)})</span></summary>"
        "<table><thead><tr><th>At</th><th>Fact (grounded in that frame)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></details>"
    )


def _card(d: dict, data_dir: Path) -> str:
    rid = d.get("id", "")
    url = d.get("url") or f"https://www.instagram.com/reel/{rid}/"
    thumb = data_uri(data_dir / (d.get("thumbnail_path") or "")) if d.get("thumbnail_path") else None
    if thumb:
        img = (
            f"<a class='thumb' href='{esc(url)}' target='_blank' rel='noopener'>"
            f"<img src='{thumb}' alt='{esc(d.get('title'))}' loading='lazy'>"
            f"<span class='play' aria-hidden='true'>▶</span></a>"
        )
    else:
        img = "<div class='thumb noimg' aria-hidden='true'>▶</div>"

    meta = []
    if d.get("likes") is not None:
        meta.append(f"<span>♥ {_int(d['likes'])}</span>")
    if d.get("comments") is not None:
        meta.append(f"<span>💬 {_int(d['comments'])}</span>")
    if d.get("views") is not None:
        meta.append(f"<span>▶ {_int(d['views'])}</span>")
    if d.get("duration"):
        meta.append(f"<span>⏱ {int(d['duration'])}s</span>")
    if _date(d.get("timestamp")):
        meta.append(f"<span>{esc(_date(d.get('timestamp')))}</span>")

    summary = f"<p class='summary'>{esc(d.get('summary'))}</p>" if d.get("summary") else ""
    return f"""
    <article class="card" id="{esc(rid)}">
      {img}
      <div class="body">
        <div class="eyebrow">
          <span class="author">{esc(d.get('author') or 'Unknown')}</span>
          <span class="genre-tag">{esc(_norm_genre(d.get('genre')))}</span>
        </div>
        <h3 class="title">{esc(d.get('title') or rid)}</h3>
        <div class="meta">{''.join(meta)}{_quality_badge(d)}</div>
        {summary}
        {_structured(d.get('structured') or {})}
        {_facts(d.get('facts') or [])}
        <a class="watch" href="{esc(url)}" target="_blank" rel="noopener">Watch reel on Instagram ↗</a>
      </div>
    </article>"""


# ---------------------------------------------------------------- styles

CSS = """
:root{
  --ground:#0f1420;--panel:#171d2b;--panel-2:#1e2536;--line:#2a3348;
  --ink:#e7ecf6;--muted:#8a93a8;--faint:#5d6785;
  --accent:#e1306c;--accent-soft:#f472a3;--cyan:#38bdf8;
  --mono:ui-monospace,"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
  line-height:1.55;font-size:16px;-webkit-font-smoothing:antialiased}
a{color:var(--accent-soft);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:960px;margin:0 auto;padding:0 24px}
header.masthead{border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,#141a29,var(--ground));padding:52px 0 40px}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent-soft);margin:0 0 14px}
h1{font-size:clamp(30px,5vw,46px);line-height:1.05;margin:0 0 16px;text-wrap:balance;
  font-weight:800;letter-spacing:-.02em}
.lede{color:var(--muted);max-width:60ch;margin:0 0 22px}
.srcbar{font-family:var(--mono);font-size:12.5px;color:var(--faint);
  display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.srcbar a{color:var(--cyan)}
.pill{background:var(--panel-2);border:1px solid var(--line);border-radius:999px;
  padding:4px 12px;color:var(--muted)}
nav.toc{position:sticky;top:0;z-index:5;background:rgba(15,20,32,.92);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:12px 0}
nav.toc ul{list-style:none;display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0}
nav.toc a{font-family:var(--mono);font-size:12px;color:var(--muted);
  border:1px solid var(--line);border-radius:6px;padding:5px 11px;display:inline-block}
nav.toc a:hover{color:var(--ink);border-color:var(--accent);text-decoration:none}
nav.toc .n{color:var(--faint)}
section.genre{padding:44px 0 8px}
.genre-head{display:flex;align-items:baseline;gap:14px;margin:0 0 24px;
  border-bottom:1px solid var(--line);padding-bottom:12px}
.genre-head h2{font-size:22px;margin:0;letter-spacing:-.01em}
.genre-head .count{font-family:var(--mono);font-size:12px;color:var(--faint)}
.card{display:grid;grid-template-columns:220px 1fr;gap:24px;background:var(--panel);
  border:1px solid var(--line);border-radius:14px;padding:20px;margin:0 0 22px;scroll-margin-top:70px}
.thumb{position:relative;display:block;border-radius:10px;overflow:hidden;
  aspect-ratio:9/16;background:var(--panel-2);align-self:start}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb .play{position:absolute;inset:0;display:grid;place-items:center;font-size:34px;
  color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.6);opacity:.9}
.thumb.noimg{display:grid;place-items:center;aspect-ratio:9/16;color:var(--faint);font-size:34px}
.body{min-width:0}
.eyebrow{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}
.author{font-family:var(--mono);font-size:12px;color:var(--accent-soft);letter-spacing:.02em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.genre-tag{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.1em;
  color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:2px 8px;flex:none}
.title{font-size:19px;line-height:1.25;margin:0 0 10px;font-weight:700;text-wrap:balance}
.meta{display:flex;flex-wrap:wrap;gap:14px;font-family:var(--mono);font-size:12px;
  color:var(--muted);margin-bottom:14px;font-variant-numeric:tabular-nums}
.summary{margin:0 0 14px;color:#d3dae8}
.badge{font-family:var(--mono);font-size:10.5px;letter-spacing:.02em;border-radius:5px;padding:2px 8px}
.badge.warn{color:#fbbf24;border:1px solid #6b4e12;background:rgba(251,191,36,.08)}
dl.fields{margin:0 0 14px;border-top:1px solid var(--line);padding-top:12px}
.field{display:grid;grid-template-columns:120px 1fr;gap:12px;padding:4px 0;align-items:start}
.field dt{font-family:var(--mono);font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--faint);margin:0}
.field dd{margin:0;color:#dfe5f0;min-width:0;overflow-wrap:anywhere}
ul.mini{margin:0;padding-left:18px}
ul.mini li{margin:2px 0}
a.ext{font-family:var(--mono);font-size:13px;color:var(--cyan);overflow-wrap:anywhere}
details.facts{margin:0 0 16px;border:1px solid var(--line);border-radius:8px;background:var(--panel-2);padding:0 14px}
details.facts summary{cursor:pointer;padding:11px 0;font-size:13px;font-weight:600;color:var(--ink);
  list-style:none;display:flex;align-items:center;gap:8px}
details.facts summary::before{content:"▸";color:var(--accent);font-size:11px}
details[open].facts summary::before{content:"▾"}
details.facts .muted{color:var(--faint);font-weight:400;font-family:var(--mono);font-size:11px}
details.facts table{width:100%;border-collapse:collapse;font-size:13.5px;margin:2px 0 14px}
details.facts th{text-align:left;font-family:var(--mono);font-size:10.5px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--faint);border-bottom:1px solid var(--line);padding:6px 8px}
details.facts td{padding:7px 8px;border-bottom:1px solid rgba(42,51,72,.5);vertical-align:top;color:#d3dae8}
details.facts td.ts{font-family:var(--mono);color:var(--accent-soft);white-space:nowrap;font-variant-numeric:tabular-nums}
a.watch{display:inline-block;font-family:var(--mono);font-size:12.5px;font-weight:600;
  color:var(--accent-soft);border:1px solid var(--accent);border-radius:7px;padding:8px 15px;margin-top:4px}
a.watch:hover{background:var(--accent);color:#fff;text-decoration:none}
footer{border-top:1px solid var(--line);margin-top:40px;padding:30px 0 60px;
  font-family:var(--mono);font-size:12px;color:var(--faint);text-align:center}
/* index */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:22px;padding:44px 0}
.col{display:block;background:var(--panel);border:1px solid var(--line);border-radius:14px;
  overflow:hidden;color:inherit}
.col:hover{border-color:var(--accent);text-decoration:none}
.col .strip{display:grid;grid-template-columns:1fr 1fr 1fr;height:150px;background:var(--panel-2)}
.col .strip img{width:100%;height:100%;object-fit:cover}
.col .strip .ph{display:grid;place-items:center;color:var(--faint);font-size:26px}
.col .info{padding:16px 18px}
.col .info h3{margin:0 0 6px;font-size:18px}
.col .info .sub{font-family:var(--mono);font-size:12px;color:var(--faint);
  display:flex;gap:12px;flex-wrap:wrap}
@media (max-width:640px){.card{grid-template-columns:1fr}.thumb{max-width:200px}.field{grid-template-columns:1fr;gap:2px}}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"
    )


# ---------------------------------------------------------------- public API


def render_doc(reels: list[dict], meta: DocMeta, data_dir: str | Path = "data") -> str:
    """Full standalone HTML for one collection. `reels` are raw JSON dicts."""
    data_dir = Path(data_dir)
    groups: dict[str, list[dict]] = {}
    for d in reels:
        groups.setdefault(_norm_genre(d.get("genre")), []).append(d)
    ordered = [g for g in GENRE_ORDER if g in groups] + [g for g in groups if g not in GENRE_ORDER]

    toc = "".join(
        f"<li><a href='#g-{g}'>{esc(GENRE_LABEL[g])} <span class='n'>{len(groups[g])}</span></a></li>"
        for g in ordered
    )
    sections = []
    for g in ordered:
        cards = "".join(_card(d, data_dir) for d in groups[g])
        sections.append(
            f"<section class='genre' id='g-{g}'><div class='wrap'>"
            f"<div class='genre-head'><h2>{esc(GENRE_LABEL[g])}</h2>"
            f"<span class='count'>{len(groups[g])} reel{'s' if len(groups[g]) != 1 else ''}</span></div>"
            f"{cards}</div></section>"
        )

    n = len(reels)
    authors = len({d.get("author") for d in reels if d.get("author")})
    src = (
        f"<a href='{esc(meta.source_url)}' target='_blank' rel='noopener'>Open collection ↗</a>"
        if meta.source_url
        else ""
    )
    subtitle = meta.subtitle or (
        f"Every reel from the <strong>{esc(meta.title)}</strong> collection, extracted into structured "
        "notes — transcript, on-screen text, and AI vision distilled into a summary, typed fields, and "
        "timestamped facts. Thumbnails embedded; each card links back to the source reel."
    )
    body = f"""
<header class="masthead"><div class="wrap">
  <p class="kicker">Instagram Saved Collection · Consolidated Research Doc</p>
  <h1>{esc(meta.title)} — {n} Saved Reel{'s' if n != 1 else ''}</h1>
  <p class="lede">{subtitle}</p>
  <div class="srcbar">
    <a href="index.html">← All collections</a>
    <span class="pill">{n} reels</span><span class="pill">{authors} creators</span>
    <span class="pill">{len(ordered)} genres</span>{src}
  </div>
</div></header>
<nav class="toc"><div class="wrap"><ul>{toc}</ul></div></nav>
{''.join(sections)}
<footer><div class="wrap">Generated locally by reels-scrap · thumbnails embedded · facts grounded in source frames</div></footer>"""
    return _page(f"{meta.title} — Saved Reels", body)


def render_index(cards: list[CollectionCard]) -> str:
    """Master index over all collection docs."""
    cards = sorted(cards, key=lambda c: c.title.lower())
    total = sum(c.count for c in cards)
    tiles = []
    for c in cards:
        thumbs = c.thumbs[:3]
        cells = "".join(f"<img src='{t}' alt=''>" for t in thumbs)
        cells += "".join("<div class='ph'>▶</div>" for _ in range(3 - len(thumbs)))
        upd = f"<span>updated {esc(c.updated)}</span>" if c.updated else ""
        tiles.append(
            f"<a class='col' href='{esc(c.slug)}.html'>"
            f"<div class='strip'>{cells}</div>"
            f"<div class='info'><h3>{esc(c.title)}</h3>"
            f"<div class='sub'><span>{c.count} reels</span>{upd}</div></div></a>"
        )
    body = f"""
<header class="masthead"><div class="wrap">
  <p class="kicker">Local Research Library</p>
  <h1>Saved Reel Collections</h1>
  <p class="lede">{len(cards)} collection{'s' if len(cards) != 1 else ''} · {total} reels extracted and consolidated.
  Each opens a self-contained document with summaries, structured fields, timestamped facts, and links back to every reel.</p>
</div></header>
<div class="wrap"><div class="grid">{''.join(tiles) or "<p class='lede'>No collections yet. Run <code>reels-scrap collection &lt;url&gt;</code>.</p>"}</div></div>
<footer><div class="wrap">Generated locally by reels-scrap</div></footer>"""
    return _page("Saved Reel Collections", body)
