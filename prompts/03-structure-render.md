# Layer 03 — Structure & Render

You are a docs-rendering engineer. Your objective is to turn enriched `Reel`
records into human-readable artifacts: per-reel Markdown (jinja2), per-reel PDF
(weasyprint + CSS), and a static mkdocs-material site with a page per reel plus a
master index.

<context>
  <depends_on>
    Layers 00–02 exist. Each `Reel` in `output/reels/<id>.json` now has
    metadata, transcript, ocr_text, summary, genre, structured fields, and
    provenance-bearing facts. Render outputs go to `output/markdown`,
    `output/pdfs`, `output/site` via `core/paths`.
  </depends_on>
  <boundary>
    `structure/markdown.py` + `render/` only READ `Reel` records and write files.
    No scraping, no extraction, no LLM calls. Renderers set `reel.markdown_path`
    / `reel.pdf_path` back on the record so the API/UI can link to them.
  </boundary>
  <facts_are_the_point>
    The facts table (claim + clickable timestamp) is the centerpiece of every
    rendered reel — it's how a reader verifies a claim against the source clip.
  </boundary>
</context>

## Instructions
1. **`structure/markdown.py`.** `render_markdown(reel, config) -> Path` using
   jinja2 templates (under a package `templates/` dir). The page MUST include:
   title + author + link to the original reel; embedded/linked thumbnail; the
   AI summary; a **facts table** (`claim | timestamp | frame`) where timestamps
   are shown as `m:ss`; the genre + a typed-fields block rendered from
   `reel.structured`; the transcript (collapsible), OCR text, caption, hashtags,
   and stats. Write to `output/markdown/<id>.md` and set `reel.markdown_path`
   (relative to data_dir). Keep templates readable and reusable by the site step.
2. **`render/pdf.py`.** `render_pdf(reel, config) -> Path` with weasyprint:
   render the same content via an HTML jinja2 template + a CSS stylesheet
   (Catppuccin-Mocha-friendly, print-safe) to `output/pdfs/<id>.pdf`. Set
   `reel.pdf_path`. Support `config.output.combined_pdf`: when true, also emit one
   merged PDF with per-reel bookmarks/outline.
3. **`render/docs_site.py`.** `build_site(config) -> Path`: generate an
   mkdocs-material site under `output/site`:
   - write the per-reel Markdown into the mkdocs `docs/` source (reuse
     `structure/markdown.py` output);
   - generate a master `index.md` grouping reels by genre with links + a stats
     summary;
   - emit a generated `mkdocs.yml` (material theme, Catppuccin Mocha palette,
     search plugin, nav built from the reels);
   - run the mkdocs build to produce the static site.
   Guard the whole step behind `config.output.docs_site`.
4. **Pipeline wiring.** Add a `structure_and_render(reel, config)` step that runs
   `render_markdown`, then (if `config.output.pdf`) `render_pdf`, saving the
   updated `Reel` (with render paths) back to `output/reels/<id>.json`. After all
   reels are processed, `run` calls `build_site` once if enabled. Record
   successes/failures in the `RunReport`.
5. **Tests.** `tests/test_render.py`: rendering a sample `Reel` produces Markdown
   containing the facts table with `m:ss` timestamps and the typed-fields block;
   `render_markdown` sets `reel.markdown_path`; PDF render writes a non-empty file
   (can assert file exists + >0 bytes, weasyprint mocked or real if available);
   `build_site` index groups by genre. Use a fixture `Reel` with at least one
   fact carrying a timestamp.

## Constraints
- MUST only read `Reel` records and write files — no scraping/extraction/LLM.
- MUST render the facts table with human-readable `m:ss` timestamps and the
  frame index, preserving provenance.
- MUST set `reel.markdown_path` / `reel.pdf_path` (relative to data_dir) and
  persist them.
- MUST gate PDF/site/combined-PDF behind their `config.output.*` toggles.
- MUST resolve all paths through `core/paths`; outputs only under `output/`.
- MUST use Catppuccin Mocha styling for the PDF CSS and the mkdocs palette.
- MUST NOT duplicate template logic between the Markdown, PDF, and site steps —
  share jinja2 templates/partials.

## Output format
Paste-ready files, each in a fenced block headed by its path, in this order:
`structure/markdown.py`, the jinja2 template(s) under `templates/`,
`render/pdf.py`, the PDF CSS, `render/docs_site.py`, the pipeline wiring
addition, and `tests/test_render.py`. End with the commands to add deps
(`jinja2`, `weasyprint`, `mkdocs-material`) and run the tests.

Reason briefly in a `<thinking>` block first, then output the files.
