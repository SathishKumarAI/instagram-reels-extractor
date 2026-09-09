"""A sync must not start on a dead Instagram session.

Catches the 2026-09-08 waste: the probe said "every source will fail until this is
fixed", `sync` ran all 20 sources anyway, and every one returned
`Exceeded 30 redirects.` — 20 Instagram requests spent while logged out, 0 reels.
"""
from __future__ import annotations

import json

from typer.testing import CliRunner

from reels_scrap.ingest import collection

runner = CliRunner()


def _probe(monkeypatch, ok: bool, why: str = "session ok"):
    monkeypatch.delenv("REELS_IGNORE_AUTH", raising=False)
    monkeypatch.setattr(collection, "session_ok", lambda browser="chrome": (ok, why))


def test_live_session_is_not_a_blocker(monkeypatch):
    _probe(monkeypatch, True)
    assert collection.auth_blockers("cookies.txt") == []


def test_dead_session_blocks(monkeypatch):
    _probe(monkeypatch, False, "network error: Exceeded 30 redirects.")
    assert collection.auth_blockers("cookies.txt") == [
        "network error: Exceeded 30 redirects."
    ]


def test_rate_limited_blocks_too(monkeypatch):
    """More requests are the last thing an HTTP 429 needs."""
    _probe(monkeypatch, False, "rate-limited (HTTP 429) — session may still be fine")
    assert collection.auth_blockers("cookies.txt")


def test_env_override_lets_it_run(monkeypatch):
    _probe(monkeypatch, False, "session expired (HTTP 401)")
    monkeypatch.setenv("REELS_IGNORE_AUTH", "1")
    assert collection.auth_blockers("cookies.txt") == []


def _config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(json.dumps({
        "extract": {"vision": True, "vision_backend": "claude-cli"},
        "auth": {"cookies_file": "cookies.txt"},
        "paths": {"data_dir": str(tmp_path / "data"), "output_dir": str(tmp_path / "out")},
    }), encoding="utf-8")
    return p


def test_sync_exits_4_and_polls_nothing_when_the_session_is_dead(monkeypatch, tmp_path):
    from reels_scrap import sources as sources_mod
    from reels_scrap.cli import app

    _probe(monkeypatch, False, "network error: Exceeded 30 redirects.")
    polled = []
    monkeypatch.setattr(sources_mod, "poll_all", lambda *a, **k: polled.append(1) or [])

    r = runner.invoke(app, ["sync", "-c", str(_config(tmp_path))])

    assert r.exit_code == 4, r.output          # 4 = auth, distinct from 3 (GPU), 1, 2
    assert polled == []                        # not one Instagram request was spent
    assert "Exceeded 30 redirects" in r.output


def test_sync_proceeds_when_the_session_is_live(monkeypatch, tmp_path):
    from reels_scrap import sources as sources_mod
    from reels_scrap.cli import app

    _probe(monkeypatch, True)
    polled = []
    monkeypatch.setattr(sources_mod, "poll_all", lambda *a, **k: polled.append(1) or [])

    r = runner.invoke(app, ["sync", "-c", str(_config(tmp_path))])

    assert polled == [1]                       # it ran
    assert r.exit_code == 1                    # …and found no enabled sources
