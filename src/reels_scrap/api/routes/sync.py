"""Sources, sync runs and what the Sync tab draws.

`run.log` is the shared signal: a sync started from the CLI writes it too, so the
UI follows either. `_SYNC` is module-level because there is exactly one sync at a
time — a second POST /api/sync is a 409, not a queue.
"""

from __future__ import annotations

import json as _json
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ...config import Config

# pipeline stages in run order, as they appear in run.log progress lines
STAGES = ["enumerate", "ingest", "process", "site", "index"]
_STAGE_RE = re.compile(r"\[(ingest|process|site|index)\]")
_COUNT_RE = re.compile(r"\((\d+)/(\d+)\)")

# module-level status for the single background sync (polled by the UI)
_SYNC: dict = {"running": False, "backend": "", "ingested": 0, "sources": 0, "error": ""}


class SourceIn(BaseModel):
    url: str
    name: str = ""
    type: str = "collection"


class SyncIn(BaseModel):
    backend: str = "claude-cli"       # any profile name — see GET /api/profiles
    browser: str = "chrome"
    only: list[str] | None = None
    # skip the GPU transcript + OCR stages. Off by default: a UI-started sync used
    # to silently produce thinner records than the same sync from the CLI, and
    # missing audio was the single biggest cause of vague summaries.
    fast: bool = False


def _log_tail(cfg: Config, lines: int) -> tuple[list[str], float | None]:
    """Last N lines of run.log + seconds since it was last written.

    Every sync writes it — CLI runs included — so the UI can follow a sync it
    did not start itself.
    """
    p = cfg.output_dir / "run.log"
    if not p.exists():
        return [], None
    tail = p.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    return tail, time.time() - p.stat().st_mtime


def _stage_and_progress(tail: list[str]) -> tuple[str, dict]:
    """Newest stage marker in the log wins; `(i/n)` on that line is its progress."""
    for line in reversed(tail):
        m = _STAGE_RE.search(line)
        if m:
            c = _COUNT_RE.search(line)
            return m.group(1), ({"done": int(c.group(1)), "total": int(c.group(2))} if c else {})
        if "collection " in line and " page " in line:
            return "enumerate", {}
    return "", {}


def _sync_sources(cfg: Config) -> list[dict]:
    """Per-source outcome of the last sync, from output/sources_state.json."""
    from ...sources import load_state

    return [
        {
            "name": name,
            "last_run": s.get("last_run"),
            "runs": s.get("runs", 0),
            "current": s.get("last_current", 0),
            "new": s.get("last_new", 0),
            "ingested": s.get("last_ingested", 0),
            "failed": len(s.get("failed_ids", [])),
            "error": s.get("error") or "",
        }
        for name, s in sorted(load_state(cfg.output_dir).items())
    ]


def _run_report(cfg: Config) -> dict:
    """Per-stage ok/error tallies from the last pipeline run."""
    p = cfg.output_dir / "run_report.json"
    if not p.exists():
        return {}
    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    stages: dict[str, dict[str, int]] = {}
    for o in data.get("reels", {}).values():
        for stage, status in o.get("stages", {}).items():
            stages.setdefault(stage, {}).setdefault(status, 0)
            stages[stage][status] += 1
    return {
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "summary": data.get("summary", {}),
        "stages": stages,
    }


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sources")
    def list_sources_ep() -> list[dict]:
        from dataclasses import asdict

        from ...sources import load_sources, load_state

        state = load_state(cfg.output_dir)
        out = []
        for s in load_sources():
            d = asdict(s)
            st = state.get(s.name, {})
            d["last_run"] = st.get("last_run")
            d["reels"] = st.get("last_current")
            out.append(d)
        return out

    @router.post("/api/sources")
    def add_source_ep(body: SourceIn) -> dict:
        from dataclasses import asdict

        from ...sources import add_source

        try:
            s = add_source(body.url, name=body.name or None, type=body.type)
        except Exception as e:
            raise HTTPException(400, f"invalid source: {e}") from e
        return asdict(s)

    @router.post("/api/sources/{name}/toggle")
    def toggle_source_ep(name: str) -> dict:
        from dataclasses import asdict

        from ...sources import load_sources, save_sources

        rows = load_sources()
        hit = next((s for s in rows if s.name == name), None)
        if not hit:
            raise HTTPException(404, f"no source {name}")
        hit.enabled = not hit.enabled
        save_sources(rows)
        return asdict(hit)

    @router.get("/api/report")
    def report() -> dict:
        """Last run's per-reel stage report (ingest/transcript/vision ok/error)."""
        p = cfg.output_dir / "run_report.json"
        if not p.exists():
            return {"reels": {}, "note": "no run yet"}
        return _json.loads(p.read_text(encoding="utf-8"))

    @router.get("/api/sync/status")
    def sync_status(lines: int = 150) -> dict:
        """Everything the Sync tab draws: pipeline stage, per-source outcome,
        last run report and a live log tail.

        `live` is true for a sync started here OR one started from the CLI — the
        log file is the shared signal, so the UI follows either.
        """
        tail, age = _log_tail(cfg, max(1, min(lines, 1000)))
        stage, progress = _stage_and_progress(tail)
        return {
            **_SYNC,
            "live": bool(_SYNC["running"] or (age is not None and age < 60)),
            "log_age_sec": age,
            "stages": STAGES,
            "stage": stage,
            "progress": progress,
            "log": tail,
            "source_state": _sync_sources(cfg),
            "report": _run_report(cfg),
        }

    @router.post("/api/sync")
    def sync_ep(body: SyncIn) -> dict:
        """Kick off an incremental sync in the background with a chosen vision backend.
        The UI picks Claude-code vs the local GPU box here."""
        from ...modelreg import status as model_status
        from ...profiles import list_profiles

        if _SYNC["running"]:
            raise HTTPException(409, "a sync is already running")
        backend = body.backend
        known = list_profiles(config_path)
        if backend not in known:
            raise HTTPException(400, f"unknown model {backend!r} — known: {', '.join(known)}")

        # a registry model that was never pulled would fail per reel, mid-run
        missing = {r["name"] for r in model_status() if not r["installed"]}
        if backend in missing:
            raise HTTPException(
                400, f"model {backend!r} is not installed — run `reels-scrap models pull {backend}`"
            )

        def _job():
            from ...compare import cfg_for_backend
            from ...sources import poll_all
            c = cfg_for_backend(backend, config_path)
            if body.fast:
                c.extract.transcript = c.extract.ocr = False
            c.extract.vision = True
            try:
                results = poll_all(c, config_path, browser=body.browser or "chrome",
                                   only=body.only or None)
                _SYNC.update(
                    running=False,
                    ingested=sum(r.ingested for r in results),
                    sources=len(results),
                    error="",
                )
            except Exception as ex:
                _SYNC.update(running=False, error=str(ex)[:300])

        if backend == "local":
            # the endpoint lives in config-local.yaml, not config.yaml — cfg_for_backend
            # is the one place that knows that, and the Compare tab already used it
            from ...compare import cfg_for_backend

            if not cfg_for_backend("local", config_path).extract.vision_local.base_url:
                raise HTTPException(
                    400,
                    "backend=local needs extract.vision_local.base_url — set it in "
                    "config-local.yaml (see docs/LOCAL-VISION.md)",
                )

        _SYNC.update(running=True, backend=backend, ingested=0, sources=0, error="")
        threading.Thread(target=_job, daemon=True).start()
        return dict(_SYNC)

    @router.post("/api/ingest")
    def ingest_url(body: dict, bg: BackgroundTasks) -> dict:
        """Quick-add a single reel URL — downloads + caption in the background (no vision)."""
        url = (body or {}).get("url", "").strip()
        if not re.match(r"^https?://(www\.)?instagram\.com/(reel|reels|p|tv)/[\w-]+", url):
            raise HTTPException(400, "not an Instagram reel URL")

        def _job(u: str):
            import tempfile

            from ...config import Config as _C
            from ...pipeline import run_pipeline
            c = _C.load(config_path)
            c.extract.transcript = c.extract.ocr = c.extract.vision = False  # fast caption-only
            c.output.pdf = c.output.docs_site = False
            f = Path(tempfile.mkstemp(suffix=".txt", dir=c.data_dir)[1])
            f.write_text(u + "\n", encoding="utf-8")
            c.source.type = "urls"
            c.source.urls_file = str(f)
            c.source.resume = True
            try:
                run_pipeline(c, config_path)
            finally:
                f.unlink(missing_ok=True)

        bg.add_task(_job, url)
        return {"accepted": url,
                "note": "downloading in background; refresh in a moment. "
                        "Run sync/backfill for AI extraction."}

    return router
