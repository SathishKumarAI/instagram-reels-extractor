"""The GPU guard: a local-vision sync must not start onto a busy card.

Catches the 2026-08-19 failure — another project's `gemma4:12b` was resident, our
9.4GB model spilled to CPU, and every reel read-timed out at 240s.
"""
from __future__ import annotations

from reels_scrap import modelreg

PS = """NAME          ID              SIZE      PROCESSOR    CONTEXT    UNTIL
gemma4:12b    4eb23ef187e2    8.1 GB    100% GPU     8192       Stopping...
"""

# what a contended card looks like: 3 of 29 layers pushed to CPU
PS_SPLIT = """NAME                   ID              SIZE     PROCESSOR          CONTEXT    UNTIL
reels-vision:latest    65768bcd2e53    10 GB    17%/83% CPU/GPU    32768      4 minutes from now
"""


def test_parse_ps_reads_name_size_and_processor():
    assert modelreg._parse_ps(PS) == [("gemma4:12b", "8.1 GB", "100% GPU")]
    assert modelreg._parse_ps(PS_SPLIT) == [
        ("reels-vision:latest", "10 GB", "17%/83% CPU/GPU")
    ]


def test_processor_of_matches_the_latest_suffix(monkeypatch):
    monkeypatch.setattr(modelreg, "resident_models",
                        lambda: modelreg._parse_ps(PS_SPLIT))
    assert modelreg.processor_of("reels-vision") == "17%/83% CPU/GPU"
    assert modelreg.processor_of("gemma4:12b") == ""    # not loaded


def test_parse_smi_converts_mib_to_gb():
    used, total, util = modelreg._parse_smi("13567, 16303, 78\n")
    assert round(used, 1) == 13.2
    assert round(total, 1) == 15.9
    assert util == 78


def test_parse_smi_survives_junk():
    assert modelreg._parse_smi("") is None
    assert modelreg._parse_smi("[N/A], [N/A], [N/A]") is None


def _patch(monkeypatch, resident, state):
    monkeypatch.delenv("REELS_IGNORE_GPU", raising=False)
    monkeypatch.setattr(modelreg, "resident_models", lambda: resident)
    monkeypatch.setattr(modelreg, "gpu_state", lambda: state)


def test_foreign_resident_model_blocks(monkeypatch):
    _patch(monkeypatch, [("gemma4:12b", "8.1 GB", "100% GPU")],(13.2, 15.9, 10))
    why = modelreg.gpu_blockers("reels-vision", need_gb=9.4)
    assert any("gemma4:12b" in w for w in why)
    assert any("free" in w for w in why)          # 2.7GB free, needs ~11.4GB


def test_our_own_model_resident_is_not_a_blocker(monkeypatch):
    _patch(monkeypatch, [("reels-vision:latest", "9.4 GB", "100% GPU")], (10.0, 15.9, 12))
    assert modelreg.gpu_blockers("reels-vision", need_gb=9.4) == []


def test_idle_card_is_clear(monkeypatch):
    _patch(monkeypatch, [], (1.5, 15.9, 4))
    assert modelreg.gpu_blockers("reels-vision", need_gb=9.4) == []


def test_busy_card_blocks_even_with_memory_free(monkeypatch):
    _patch(monkeypatch, [], (1.5, 15.9, 92))      # someone training, little VRAM held
    assert modelreg.gpu_blockers("reels-vision", need_gb=9.4) == ["GPU is 92% busy — "
                                                                 "another job is running"]


def test_env_override_lets_it_run(monkeypatch):
    _patch(monkeypatch, [("gemma4:12b", "8.1 GB", "100% GPU")],(13.2, 15.9, 92))
    monkeypatch.setenv("REELS_IGNORE_GPU", "1")
    assert modelreg.gpu_blockers("reels-vision", need_gb=9.4) == []


def test_remote_endpoint_is_not_checked(monkeypatch):
    """nvidia-smi here says nothing about a GPU box across the LAN."""
    from reels_scrap.config import Config
    from reels_scrap.sources import local_gpu_blockers

    _patch(monkeypatch, [("gemma4:12b", "8.1 GB", "100% GPU")],(13.2, 15.9, 92))
    cfg = Config()
    cfg.extract.vision = True
    cfg.extract.vision_backend = "local"
    cfg.extract.vision_local.model = "reels-vision"

    cfg.extract.vision_local.base_url = "http://gpu-box:8000/v1"
    assert local_gpu_blockers(cfg) == []

    cfg.extract.vision_local.base_url = "http://127.0.0.1:11434/v1"
    assert local_gpu_blockers(cfg)


def test_with_retry_does_not_retry_a_fatal(monkeypatch):
    """The 2026-08-19 waste: 9 attempts x 240s per reel, all failing identically."""
    from reels_scrap.modelreg import GpuContended
    from reels_scrap.ratelimit import with_retry

    calls = []

    def boom():
        calls.append(1)
        raise GpuContended("17%/83% CPU/GPU")

    try:
        with_retry(boom, attempts=3, backoff=0, fatal=(GpuContended,))
    except GpuContended:
        pass
    assert calls == [1]                      # once, not three times


def test_with_retry_still_retries_everything_else():
    from reels_scrap.ratelimit import with_retry

    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "ok"

    assert with_retry(flaky, attempts=3, backoff=0) == "ok"
    assert len(calls) == 3


def test_claude_backend_skips_the_check(monkeypatch):
    from reels_scrap.config import Config
    from reels_scrap.sources import local_gpu_blockers

    _patch(monkeypatch, [("gemma4:12b", "8.1 GB", "100% GPU")],(13.2, 15.9, 92))
    cfg = Config()
    cfg.extract.vision = True
    cfg.extract.vision_backend = "claude-cli"
    assert local_gpu_blockers(cfg) == []
