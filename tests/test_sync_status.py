"""Sync tab data: the pipeline stage is read back out of run.log."""

from __future__ import annotations

from reels_scrap.api.app import _stage_and_progress

LOG = [
    "16:07:36 INFO collection 17864519196633026 page 1: +4 (total 4)",
    "16:16:16 INFO [ingest] ingested 0 reels (24 failed)",
    "16:21:12 INFO [process] done DbZL2oEvCEP (6/15)",
]


def test_latest_stage_wins_and_carries_progress():
    assert _stage_and_progress(LOG) == ("process", {"done": 6, "total": 15})


def test_enumerate_before_any_stage_marker():
    assert _stage_and_progress(LOG[:1]) == ("enumerate", {})


def test_no_progress_numbers_is_not_an_error():
    assert _stage_and_progress(["16:30:00 INFO [index] built"]) == ("index", {})


def test_empty_log():
    assert _stage_and_progress([]) == ("", {})
