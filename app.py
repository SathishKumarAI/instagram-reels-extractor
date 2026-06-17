"""Streamlit UI for reels-scrap. Run: streamlit run app.py

Drives the same pipeline as the CLI (src/reels_scrap/pipeline.py). Paste reel
URLs, pick what to extract, hit Run, read/download results.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from reels_scrap.config import (
    BROWSERS,
    WHISPER_MODELS,
    AuthCfg,
    BatchCfg,
    Config,
    ExtractCfg,
    OutputCfg,
    SourceCfg,
)
from reels_scrap.models import Reel
from reels_scrap.pipeline import run_pipeline

st.set_page_config(page_title="Reels → Docs", page_icon="🎬", layout="wide")
st.title("🎬 Instagram Reels → Text → PDF → Docs")
st.caption("Paste reel URLs, choose what to extract, get markdown + PDF + a docs site.")

# ---------------- sidebar: config ----------------
with st.sidebar:
    st.header("⚙️ Settings")

    st.subheader("Source")
    source_type = st.selectbox("Type", ["urls", "profile", "hashtag", "saved"], index=0)
    target = ""
    if source_type in ("profile", "hashtag"):
        target = st.text_input(
            "Target", placeholder="handle (no @) or hashtag (no #)"
        )
    limit = st.number_input("Limit", 1, 1000, 50)

    st.subheader("🔒 Private access (cookies)")
    use_cookies = st.checkbox("Use browser login for private reels", value=True)
    browser = ""
    if use_cookies:
        browser = st.selectbox(
            "Browser logged into Instagram", sorted(BROWSERS),
            index=sorted(BROWSERS).index("chrome"),
        )
        st.caption("Close the browser before running (cookie DB lock).")

    st.subheader("Extract")
    caption = st.checkbox("Caption + metadata", True)
    transcript = st.checkbox("Audio transcript (Whisper)", True)
    ocr = st.checkbox("On-screen text (OCR)", False)
    vision = st.checkbox("AI visual summary (Claude)", True)
    vision_backend = st.radio(
        "Vision backend", ["claude-cli", "api"], index=0, horizontal=True,
        help="claude-cli = your Claude Code subscription (no API key). api = ANTHROPIC_API_KEY.",
    )
    whisper_model = st.selectbox(
        "Whisper model", sorted(WHISPER_MODELS),
        index=sorted(WHISPER_MODELS).index("base"),
    )
    whisper_language = st.text_input(
        "Force language (blank = auto)", value="en",
        help="Set 'en' to stop multilingual hallucination on music/text reels.",
    )

    st.subheader("Batch")
    workers = st.slider("Parallel workers", 1, 8, 3,
                        help="Process several clips at once. Higher = faster, more CPU + Claude quota burst.")

    st.subheader("Output")
    want_pdf = st.checkbox("PDF per reel", True)
    want_site = st.checkbox("Docs site", True)
    combined = st.checkbox("Combined PDF", False)


tab_run, tab_search = st.tabs(["▶️ Extract", "🔎 Search archive"])

# ---------------- main: input + run ----------------
with tab_run:
    urls_text = ""
    if source_type == "urls":
        urls_text = st.text_area(
            "Reel URLs (one per line)",
            height=140,
            placeholder="https://www.instagram.com/reel/XXXXXXXXX/",
        )
    run = st.button("▶️ Run pipeline", type="primary", use_container_width=True)


def _build_config() -> Config:
    return Config(
        source=SourceCfg(
            type=source_type,
            urls_file="reels.txt",
            target=target,
            limit=int(limit),
        ),
        auth=AuthCfg(cookies_from_browser=browser if use_cookies else ""),
        extract=ExtractCfg(
            caption=caption,
            transcript=transcript,
            ocr=ocr,
            vision=vision,
            vision_backend=vision_backend,
            whisper_model=whisper_model,
            whisper_language=whisper_language.strip(),
        ),
        output=OutputCfg(pdf=want_pdf, docs_site=want_site, combined_pdf=combined),
        batch=BatchCfg(workers=int(workers)),
    )


def _render_results(reels: list[Reel], report, cfg: Config):
    s = report.summary()
    c1, c2, c3 = st.columns(3)
    c1.metric("Reels", s["total_reels"])
    c2.metric("Clean", s["clean"])
    c3.metric("With errors", s["with_errors"])

    if cfg.output.docs_site:
        site_index = cfg.output_dir / "site" / "index.html"
        st.info(f"Docs site built → `{site_index}`  ·  serve: "
                f"`mkdocs serve -f {cfg.output_dir}/site_src/mkdocs.yml`")

    for r in reels:
        with st.expander(f"🎬 {r.title or r.id}  —  @{r.author or '?'}", expanded=False):
            meta = []
            if r.likes is not None:
                meta.append(f"❤️ {r.likes:,}")
            if r.views is not None:
                meta.append(f"👁 {r.views:,}")
            if r.duration:
                meta.append(f"⏱ {r.duration:.0f}s")
            st.caption("  ·  ".join(meta) or "—")
            st.markdown(f"[Original reel]({r.url})")

            if r.summary:
                st.markdown("**Summary**")
                st.write(r.summary)
            if r.caption:
                st.markdown("**Caption**")
                st.write(r.caption)
            if r.transcript_text:
                st.markdown("**Transcript**")
                st.write(r.transcript_text)
            if r.ocr_text:
                st.markdown("**On-screen text**")
                st.write(" · ".join(r.ocr_text))

            cols = st.columns(2)
            if r.pdf_path and Path(r.pdf_path).exists():
                cols[0].download_button(
                    "⬇️ PDF", Path(r.pdf_path).read_bytes(),
                    file_name=f"{r.id}.pdf", mime="application/pdf",
                    key=f"pdf_{r.id}",
                )
            if r.markdown_path and Path(r.markdown_path).exists():
                cols[1].download_button(
                    "⬇️ Markdown", Path(r.markdown_path).read_text(),
                    file_name=f"{r.id}.md", mime="text/markdown",
                    key=f"md_{r.id}",
                )

            errs = report.reel(r.id).errors
            if errs:
                st.warning("Stage errors: " + "; ".join(f"{k}: {v}" for k, v in errs.items()))


with tab_run:
    if run:
        # validate + build config (fail-fast surfaces in the UI)
        try:
            cfg = _build_config()
        except Exception as e:  # noqa: BLE001
            st.error(f"Config error: {e}")
            st.stop()

        if source_type == "urls":
            urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
            if not urls:
                st.error("Paste at least one reel URL.")
                st.stop()
            Path("reels.txt").write_text("\n".join(urls) + "\n")

        bar = st.progress(0.0, text="Starting…")
        status = st.empty()

        def _progress(stage, cur, total, msg):
            frac = (cur / total) if total else 0.0
            bar.progress(min(frac, 1.0), text=f"{stage}: {msg}")
            status.write(f"`{stage}` — {msg}")

        try:
            with st.spinner("Running pipeline… (first Whisper/OCR run downloads models)"):
                reels, report = run_pipeline(cfg, "<ui>", progress=_progress)
        except Exception as e:  # noqa: BLE001
            st.error(f"Pipeline failed: {e}")
            st.exception(e)
            st.stop()

        bar.progress(1.0, text="Done")
        if not reels:
            st.error("No reels ingested. Check URLs / cookies / account access.")
            st.stop()

        st.success(f"Done — {len(reels)} reel(s) processed.")
        _render_results(reels, report, cfg)


# ---------------- search tab ----------------
with tab_search:
    st.subheader("🔎 Semantic search over your reel archive")
    st.caption("Searches summaries, structured fields, transcripts, and individual facts.")
    q = st.text_input("Query", placeholder="e.g. system design caching resources")
    if st.button("Search", use_container_width=True) and q.strip():
        from reels_scrap.search import search as do_search

        try:
            hits = do_search(Config(), q.strip(), k=10)
        except FileNotFoundError:
            st.warning("No index yet — run an extraction first (it builds the index).")
            hits = []
        for h in hits:
            ts = f" · @{int(h['timestamp'])}s" if h.get("timestamp") is not None else ""
            st.markdown(
                f"**{h['score']:.2f}** · `{h['kind']}{ts}` · "
                f"[{h['title'][:60]}]({h['url']})  \n{h['text']}"
            )
            st.divider()
