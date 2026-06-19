"""Concurrency + retry guards for throughput-bottleneck stages.

The vision LLM (`claude -p`) is the limiter when scaling toward ~100 reels/hr:
parallel invocations throttle and fail with empty stderr. So we gate vision to a
small global concurrency (a process-wide semaphore) and retry with exponential
backoff, while transcript/OCR keep running in parallel across worker threads.

For the cloud-future, swap this in-process semaphore for a distributed limiter
(e.g. Redis token bucket) — the call sites don't change.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

from .observability import log

T = TypeVar("T")

_VISION_SEM: threading.Semaphore | None = None
_VISION_LIMIT = 0
_LOCK = threading.Lock()


def vision_semaphore(limit: int) -> threading.Semaphore:
    """Process-wide semaphore sized to `limit` (created once)."""
    global _VISION_SEM, _VISION_LIMIT
    with _LOCK:
        if _VISION_SEM is None:
            _VISION_SEM = threading.Semaphore(limit)
            _VISION_LIMIT = limit
        elif limit != _VISION_LIMIT:
            log.warning("vision concurrency already set to %d; ignoring %d", _VISION_LIMIT, limit)
    return _VISION_SEM


def with_retry(
    fn: Callable[[], T],
    attempts: int,
    backoff: float,
    label: str = "",
) -> T:
    """Call fn(); retry on Exception up to `attempts` with exponential backoff."""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts:
                wait = backoff * (2 ** (i - 1))
                log.warning("%s failed (attempt %d/%d): %s — retry in %.0fs",
                            label or "call", i, attempts, str(e)[:120], wait)
                time.sleep(wait)
    assert last is not None
    raise last
