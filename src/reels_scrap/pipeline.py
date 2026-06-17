"""Shared orchestration: ingest -> extract -> structure -> render.

Both the CLI (cli.py) and the Streamlit UI (app.py) call run_pipeline so the
flow lives in exactly one place. An optional progress callback lets a UI report
stage/per-reel progress without the pipeline knowing what a UI is.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .config import Config
from .models import Reel
from .observability import RunReport, log, new_report, setup_logging

# progress(stage: str, current: int, total: int, message: str)
ProgressCB = Callable[[str, int, int, str], None]


def _noop(stage: str, current: int, total: int, message: str) -> None:
    pass


def _process_one(reel: Reel, cfg: Config) -> tuple[str, dict, str | None]:
    """Extract + structure + PDF for one reel. Runs in a worker thread.

    Returns (reel_id, extract_errors, pdf_error). No shared mutable state besides
    thread-safe model caches; each reel writes only its own files.
    """
    from .extract import extract_all
    from .structure import render_markdown

    errs = extract_all(reel, cfg)
    render_markdown(reel, cfg)
    pdf_err = None
    if cfg.output.pdf:
        from .render.pdf import render_pdf

        try:
            render_pdf(reel, cfg)
            render_markdown(reel, cfg)  # re-render so PDF link appears
        except Exception as e:  # noqa: BLE001
            log.error("pdf failed %s: %s", reel.id, e)
            pdf_err = str(e)
    return reel.id, errs, pdf_err


def _prewarm(cfg: Config) -> None:
    """Load heavy models once before fanning out, to avoid load races/duplication."""
    if cfg.extract.transcript:
        from .extract.transcript import _get_model

        _get_model(cfg.extract.whisper_model, cfg.extract.whisper_device)
    if cfg.extract.ocr:
        from .extract.ocr import _get_reader

        _get_reader()


def _record(report: RunReport, cfg: Config, reel_id: str, errs: dict, pdf_err: str | None):
    o = report.reel(reel_id)
    for stage in ("transcript", "ocr", "vision"):
        if getattr(cfg.extract, stage):
            o.mark(stage, "error" if stage in errs else "ok", errs.get(stage))
    o.mark("markdown", "ok")
    if cfg.output.pdf:
        o.mark("pdf", "error" if pdf_err else "ok", pdf_err)


def run_pipeline(
    cfg: Config, config_path: str = "<ui>", progress: ProgressCB | None = None
) -> tuple[list[Reel], RunReport]:
    progress = progress or _noop
    setup_logging(cfg.output_dir)
    report = new_report(config_path, cfg.source.type)

    # 1. ingest
    progress("ingest", 0, 1, "downloading reels…")
    from .ingest import ingest

    reels = ingest(cfg)
    log.info("ingested %d reels", len(reels))
    for r in reels:
        report.reel(r.id, r.url).mark("ingest", "ok")
    progress("ingest", 1, 1, f"ingested {len(reels)} reels")
    if not reels:
        report.write(cfg.output_dir)
        return reels, report

    # 2-4. extract + structure + PDF, per reel (parallel or sequential)
    n = len(reels)
    workers = min(cfg.batch.workers, n)
    by_id = {r.id: r for r in reels}

    if workers > 1:
        _prewarm(cfg)  # load whisper/easyocr once before fan-out
        progress("process", 0, n, f"processing {n} reels with {workers} workers…")
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_process_one, r, cfg): r.id for r in reels}
            for fut in as_completed(futures):
                rid, errs, pdf_err = fut.result()
                _record(report, cfg, rid, errs, pdf_err)
                done += 1
                progress("process", done, n, f"done {rid} ({done}/{n})")
    else:
        for i, r in enumerate(reels, 1):
            progress("process", i, n, f"processing {r.id}")
            rid, errs, pdf_err = _process_one(r, cfg)
            _record(report, cfg, rid, errs, pdf_err)

    # reload reels from disk so they carry fields set inside worker threads
    reels = [Reel.load(cfg.data_dir / f"{rid}.json") for rid in by_id]

    if cfg.output.pdf and cfg.output.combined_pdf:
        from .render.pdf import render_combined

        render_combined(reels, cfg)

    if cfg.output.docs_site:
        progress("site", 0, 1, "building docs site…")
        from .render.docs_site import build_site

        build_site(reels, cfg)
        progress("site", 1, 1, "site built")

    # refresh the semantic search index (best-effort; never fails the run)
    try:
        progress("index", 0, 1, "building search index…")
        from .search import build_index

        build_index(cfg)
        progress("index", 1, 1, "index built")
    except Exception as e:  # noqa: BLE001
        log.warning("search index skipped: %s", e)

    report.write(cfg.output_dir)
    return reels, report
