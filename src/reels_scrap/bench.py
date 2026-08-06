"""The model bench: one fixed sample of reels, many models, one variant each.

The experiment only means something if the arms differ by exactly one thing — the
model. So the sample is chosen once and reused, and every arm re-runs only the
vision step over the frames already cached on disk. Nothing is re-downloaded and
nothing is re-transcribed between arms.

Failures are data. A model that cannot read a reel gets an error row in
`runs.jsonl`; it never quietly shrinks that model's average.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .models import Reel
from .observability import log

SAMPLE_FILE = "bench/sample.json"
RUNS_FILE = "bench/runs.jsonl"


def bench_dir(cfg: Config) -> Path:
    p = cfg.output_dir / "bench"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class Sample:
    reel_ids: list[str]
    strata: dict[str, int]
    seed: int
    created_at: str

    def to_json(self) -> str:
        return json.dumps(
            {"reel_ids": self.reel_ids, "strata": self.strata,
             "seed": self.seed, "created_at": self.created_at},
            indent=2,
        )


def _usable(cfg: Config) -> list[Reel]:
    """Reels a model can actually be run over — the video is what frames come from."""
    out = []
    for p in sorted(cfg.data_dir.glob("*.json")):
        try:
            r = Reel.load(p)
        except Exception:                      # a corrupt record is not the experiment
            continue
        if r.video_path and (cfg.data_dir / r.video_path).exists():
            out.append(r)
    return out


def build_sample(cfg: Config, n: int = 30, seed: int = 0) -> Sample:
    """A genre-stratified, seeded sample. Same seed + same corpus -> same ids.

    Stratified rather than uniform because the corpus is 34% educational and 1%
    news: a uniform draw of 30 would routinely contain no news reel at all, and a
    model's weakness on one genre would be invisible.
    """
    reels = _usable(cfg)
    if not reels:
        raise RuntimeError("no reels with video on disk — nothing to bench")

    by_genre: dict[str, list[Reel]] = {}
    for r in reels:
        by_genre.setdefault(r.genre or "other", []).append(r)

    rng = random.Random(seed)
    total = len(reels)
    picked: list[str] = []
    strata: dict[str, int] = {}
    # largest genres first, so rounding leftovers land on the genres that can pay
    for genre, group in sorted(by_genre.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        want = max(1, round(n * len(group) / total))
        chosen = rng.sample(sorted(g.id for g in group), min(want, len(group)))
        picked.extend(chosen)
        strata[genre] = len(chosen)

    # rounding up per genre overshoots; trim deterministically from the largest strata
    while len(picked) > n:
        biggest = max(strata, key=lambda g: (strata[g], g))
        victim = sorted(i for i in picked if i in {r.id for r in by_genre[biggest]})[-1]
        picked.remove(victim)
        strata[biggest] -= 1

    return Sample(
        reel_ids=sorted(picked),
        strata={k: v for k, v in sorted(strata.items()) if v},
        seed=seed,
        created_at=datetime.now(tz=UTC).isoformat(),
    )


def save_sample(cfg: Config, s: Sample) -> Path:
    p = cfg.output_dir / SAMPLE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.to_json(), encoding="utf-8")
    return p


def load_sample(cfg: Config) -> Sample:
    p = cfg.output_dir / SAMPLE_FILE
    if not p.exists():
        raise FileNotFoundError(f"no bench sample at {p} — run `reels-scrap bench sample` first")
    d = json.loads(p.read_text(encoding="utf-8"))
    return Sample(d["reel_ids"], d.get("strata", {}), int(d.get("seed", 0)), d.get("created_at", ""))


def _log_run(cfg: Config, row: dict) -> None:
    p = cfg.output_dir / RUNS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _release_gpu(cfg: Config) -> None:
    """Ask ollama to unload — 16GB fits one model, and the next arm needs the room."""
    base = (cfg.extract.vision_local.base_url or "").rstrip("/")
    if not base:
        return
    import urllib.error
    import urllib.request

    body = json.dumps({"model": cfg.extract.vision_local.model, "keep_alive": 0}).encode()
    url = base.removesuffix("/v1") + "/api/generate"
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.debug("gpu release skipped: %s", e)


def run(
    profiles: list[str],
    base_config: str = "config.yaml",
    force: bool = False,
    progress: Callable[[str, str, int, int, str], None] | None = None,
) -> dict:
    """Run every profile over the stored sample. One model resident at a time."""
    from .extract.vision import run_variant
    from .profiles import resolve_profile

    base = Config.load(base_config)
    sample = load_sample(base)
    summary: dict[str, dict] = {}

    for profile in profiles:
        cfg = resolve_profile(profile, base_config)
        done = failed = skipped = 0
        for i, rid in enumerate(sample.reel_ids, 1):
            path = base.data_dir / f"{rid}.json"
            if not path.exists():
                continue
            reel = Reel.load(path)
            if not force and profile in (reel.variants or {}):
                skipped += 1
                if progress:
                    progress(profile, rid, i, len(sample.reel_ids), "skip")
                continue

            t0 = time.time()
            try:
                variant = run_variant(reel, cfg, cfg.extract.vision_backend)
                # re-load: the run took a while and the pipeline may have written
                reel = Reel.load(path)
                reel.variants = {**(reel.variants or {}), profile: variant}
                reel.save(base.data_dir)
                done += 1
                _log_run(base, {"profile": profile, "reel_id": rid, "ok": True,
                                "seconds": round(time.time() - t0, 2),
                                "facts": len(variant.get("facts") or []),
                                "model": variant.get("model", ""),
                                "at": datetime.now(tz=UTC).isoformat()})
                if progress:
                    progress(profile, rid, i, len(sample.reel_ids), "ok")
            except Exception as e:                      # one arm failing is data, not a stop
                failed += 1
                _log_run(base, {"profile": profile, "reel_id": rid, "ok": False,
                                "seconds": round(time.time() - t0, 2),
                                "error": str(e)[:300],
                                "at": datetime.now(tz=UTC).isoformat()})
                log.warning("bench %s/%s failed: %s", profile, rid, e)
                if progress:
                    progress(profile, rid, i, len(sample.reel_ids), "fail")

        summary[profile] = {"done": done, "failed": failed, "skipped": skipped}
        _release_gpu(cfg)

    return {"sample": len(sample.reel_ids), "profiles": summary}


def run_stats(cfg: Config) -> dict:
    """Per-profile attempt counts from the run log — including the arms that failed.

    Only the LAST attempt at each (profile, reel) counts. The log is append-only
    and an arm may be re-run — after a fix, or with `--force` — so counting every
    line would report 60 attempts for a 30-reel arm and average in results that
    were superseded.
    """
    p = cfg.output_dir / RUNS_FILE
    if not p.exists():
        return {}
    latest: dict[tuple[str, str], dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        latest[(row.get("profile", ""), row.get("reel_id", ""))] = row

    ok, fail, secs = Counter(), Counter(), Counter()
    for (prof, _), row in latest.items():
        (ok if row.get("ok") else fail)[prof] += 1
        secs[prof] += float(row.get("seconds") or 0)
    return {
        prof: {"ok": ok[prof], "failed": fail[prof],
               "avg_seconds": round(secs[prof] / max(1, ok[prof] + fail[prof]), 2)}
        for prof in set(ok) | set(fail)
    }
