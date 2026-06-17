"""Structured logging + per-run manifest (backend observability for a batch job)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("reels_scrap")


def setup_logging(output_dir: Path, level: int = logging.INFO) -> Path:
    """Console + file logging. Returns the log file path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logfile = output_dir / "run.log"
    log.setLevel(level)
    log.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    fh = logging.FileHandler(logfile)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(ch)
    log.addHandler(fh)
    log.propagate = False
    return logfile


@dataclass
class ReelOutcome:
    id: str
    url: str = ""
    stages: dict[str, str] = field(default_factory=dict)  # stage -> ok|skip|error
    errors: dict[str, str] = field(default_factory=dict)  # stage -> message

    def mark(self, stage: str, status: str, error: str | None = None):
        self.stages[stage] = status
        if error:
            self.errors[stage] = error


@dataclass
class RunReport:
    """Accumulates per-reel, per-stage outcomes; written to run_report.json."""

    started_at: str
    config_path: str
    source_type: str
    reels: dict[str, ReelOutcome] = field(default_factory=dict)

    def reel(self, reel_id: str, url: str = "") -> ReelOutcome:
        if reel_id not in self.reels:
            self.reels[reel_id] = ReelOutcome(id=reel_id, url=url)
        return self.reels[reel_id]

    def summary(self) -> dict:
        total = len(self.reels)
        errored = sum(1 for r in self.reels.values() if r.errors)
        return {"total_reels": total, "with_errors": errored, "clean": total - errored}

    def write(self, output_dir: Path) -> Path:
        payload = {
            "started_at": self.started_at,
            "finished_at": datetime.now(tz=timezone.utc).isoformat(),
            "config": self.config_path,
            "source_type": self.source_type,
            "summary": self.summary(),
            "reels": {
                rid: {"url": o.url, "stages": o.stages, "errors": o.errors}
                for rid, o in self.reels.items()
            },
        }
        out = output_dir / "run_report.json"
        out.write_text(json.dumps(payload, indent=2))
        return out


def new_report(config_path: str, source_type: str) -> RunReport:
    return RunReport(
        started_at=datetime.now(tz=timezone.utc).isoformat(),
        config_path=config_path,
        source_type=source_type,
    )
