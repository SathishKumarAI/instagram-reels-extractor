"""Model-vs-model: the stored-variant diff, single-reel compare, batch, scoreboard.

Two different costs live here and the distinction is the point:
`GET /reels/{id}/variants/diff` reads variants already on disk ($0, instant),
`POST /reels/{id}/compare` re-runs the models (~30s, ~$0.34).
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException

from ...config import Config
from ...models import Reel
from ..deps import reel_or_404, safe_id

# module-level status for the single background batch comparison
_BATCH: dict = {"running": False, "done": 0, "total": 0, "current": "",
                "backends": [], "errors": []}


def variant_meta(name: str, v: dict) -> dict:
    """The parts of a stored variant the reader draws. Claim text only, no frames."""
    return {
        "name": name,
        "backend": v.get("backend", ""),
        "model": v.get("model", ""),
        "summary": v.get("summary", ""),
        "tags": v.get("tags") or [],
        "structured": v.get("structured") or {},
        "facts": [f.get("text", "") for f in (v.get("facts") or [])],
        "elapsed_s": v.get("elapsed_s"),
        "cost_usd": float((v.get("tokens") or {}).get("cost_usd") or 0),
        "created_at": v.get("created_at", ""),
    }


def build(cfg: Config, config_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/api/reels/{reel_id}/variants/diff")
    def variants_diff(reel_id: str, a: str = "", b: str = "") -> dict:
        """Diff two variants **already stored** on the reel. Read-only, $0, instant.

        `POST /api/reels/{id}/compare` re-runs the models; this does not. 641 of the
        674 reels already carry both a Claude and a local arm, so the reader wants
        the difference, not another 30 seconds and another $0.34. With no `a`/`b`,
        picks the reference arm plus whatever else is stored.
        """
        from ...compare import diff_facts

        variants = reel_or_404(cfg, reel_id).variants or {}
        names = sorted(variants)
        if a not in variants:
            a = "claude-cli" if "claude-cli" in variants else (names[0] if names else "")
        if b not in variants or b == a:
            b = next((n for n in names if n != a), "")
        out = {
            "reel_id": reel_id, "available": names, "a": a, "b": b,
            "variants": {n: variant_meta(n, variants[n]) for n in (a, b) if n},
            "diff": {},
        }
        if a and b:
            out["diff"] = {
                "a": a, "b": b,
                **diff_facts(variants[a].get("facts", []), variants[b].get("facts", [])),
            }
        return out

    @router.post("/api/reels/{reel_id}/compare")
    def compare_reel_ep(reel_id: str, body: dict | None = None) -> dict:
        """Run the named backends over one reel, store both variants, return the diff.

        Synchronous: claude-cli is ~30s and local ~5s, so the UI waits with a spinner
        rather than growing a second job system for a single-reel action.
        """
        from ...compare import compare_reel

        backends = (body or {}).get("backends") or ["claude-cli", "local"]
        if not 1 <= len(backends) <= 2:
            raise HTTPException(400, "pass 1 or 2 backends")
        try:
            return compare_reel(safe_id(reel_id), backends, base_config=config_path)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e

    @router.get("/api/profiles")
    def list_vision_profiles() -> list[dict]:
        """Model profiles this machine can run — the Compare tab's picker.

        Merges the declared/implicit profiles with the model registry, so a model
        that is in the plan but not pulled yet shows as not installed rather than
        silently failing at run time.
        """
        from ...modelreg import status
        from ...profiles import list_profiles

        reg = {r["name"]: r for r in status()}
        out = []
        for name in list_profiles(config_path):
            r = reg.get(name)
            declared = cfg.extract.vision_profiles.get(name)
            if declared is not None:
                kind = declared.kind
            elif r is not None or name == "local":
                kind = "local"          # registry models all run on the local endpoint
            else:
                kind = name             # claude-cli / api — the cloud arms
            model = (declared.model if declared else "") or (r["tag"] if r else "")
            out.append({
                "name": name,
                "kind": kind,
                "model": model,
                # a cloud arm needs no download; a local one must be pulled first
                "installed": bool(r["installed"]) if r is not None else True,
                "notes": (declared.notes if declared else "") or (r["role"] if r else ""),
            })
        return out

    @router.get("/api/compare/scoreboard")
    def compare_scoreboard() -> dict:
        from ...compare import scoreboard

        return scoreboard(cfg)

    @router.get("/api/compare/status")
    def compare_status() -> dict:
        return dict(_BATCH)

    @router.post("/api/compare/batch")
    def compare_batch(body: dict | None = None) -> dict:
        """Compare N reels in the background. The scoreboard is only meaningful over
        a sample, not the one reel you happened to open."""
        import random

        if _BATCH["running"]:
            raise HTTPException(409, "a batch comparison is already running")
        n = int((body or {}).get("n") or 10)
        backends = (body or {}).get("backends") or ["claude-cli", "local"]
        only_missing = bool((body or {}).get("only_missing", True))

        ids = [p.stem for p in cfg.data_dir.glob("*.json")]
        if only_missing:
            ids = [i for i in ids
                   if set(backends) - set(Reel.load(cfg.data_dir / f"{i}.json").variants or {})]
        random.shuffle(ids)
        ids = ids[:max(1, min(n, 200))]
        if not ids:
            raise HTTPException(409, "nothing left to compare with those backends")

        def _job():
            from ...compare import compare_reel

            for done, rid in enumerate(ids, 1):
                if not _BATCH["running"]:      # cancelled
                    break
                try:
                    compare_reel(rid, backends, base_config=config_path)
                except Exception as ex:
                    _BATCH["errors"].append(f"{rid}: {str(ex)[:150]}")
                _BATCH.update(done=done, current=rid)
            _BATCH.update(running=False, current="")

        _BATCH.update(running=True, done=0, total=len(ids), current="", errors=[],
                      backends=backends)
        threading.Thread(target=_job, daemon=True).start()
        return dict(_BATCH)

    @router.post("/api/compare/cancel")
    def compare_cancel() -> dict:
        _BATCH["running"] = False
        return dict(_BATCH)

    return router
