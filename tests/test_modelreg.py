"""The model registry: parses, reports installed vs missing, generates Modelfiles."""

from __future__ import annotations

from reels_scrap import modelreg


def test_registry_parses(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(
        "models:\n"
        "  a-model:\n"
        "    tag: fam:8b\n"
        "    num_ctx: 16384\n"
        "    vram_gb: 8\n"
        "    role: newer generation\n"
        "  prebuilt:\n"
        "    tag: fam:7b-q8_0\n"
        "    build: reels-vision\n",
        encoding="utf-8",
    )
    reg = modelreg.load_registry(p)
    assert [e.name for e in reg] == ["a-model", "prebuilt"]
    assert (reg[0].tag, reg[0].num_ctx) == ("fam:8b", 16384)
    assert reg[0].built_name == "a-model"        # defaults to the profile name
    assert reg[1].built_name == "reels-vision"   # unless it was built by hand


def test_status_marks_installed(monkeypatch, tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text("models:\n  here:\n    tag: fam:8b\n  gone:\n    tag: fam:2b\n", encoding="utf-8")
    monkeypatch.setattr(modelreg, "installed_models", lambda: {"here", "fam:8b"})
    rows = modelreg.status(modelreg.load_registry(p))
    assert {r["name"]: r["installed"] for r in rows} == {"here": True, "gone": False}


def test_installed_models_survives_no_ollama(monkeypatch):
    monkeypatch.setattr(modelreg.shutil, "which", lambda _: None)
    assert modelreg.installed_models() == set()   # everything reads as missing, no crash


def test_modelfile_raises_context(tmp_path):
    e = modelreg.ModelEntry(name="m", tag="fam:8b", num_ctx=32768, role="r", notes="n")
    text = modelreg.write_modelfile(e, tmp_path).read_text(encoding="utf-8")
    assert "FROM fam:8b" in text and "num_ctx 32768" in text


def test_pull_reports_bad_tag_instead_of_raising(monkeypatch, tmp_path):
    monkeypatch.setattr(modelreg.shutil, "which", lambda _: "ollama")
    monkeypatch.setattr(modelreg, "_run", lambda cmd, timeout: (1, "pull model manifest: file does not exist"))
    r = modelreg.pull(modelreg.ModelEntry(name="nope", tag="nope:9b"))
    assert r["ok"] is False and "nope:9b" in r["error"]


def test_pull_leaves_prebuilt_model_alone(monkeypatch):
    monkeypatch.setattr(modelreg.shutil, "which", lambda _: "ollama")
    monkeypatch.setattr(modelreg, "_run", lambda cmd, timeout: (0, ""))
    r = modelreg.pull(modelreg.ModelEntry(name="reels-vision", tag="x:1b", build="reels-vision"))
    assert r["ok"] and "pre-built" in r["skipped"]


def test_as_profiles_are_runnable_shapes(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text("models:\n  m:\n    tag: fam:8b\n    num_ctx: 32768\n", encoding="utf-8")
    prof = modelreg.as_profiles(modelreg.load_registry(p))
    assert prof["m"]["kind"] == "local" and prof["m"]["model"] == "m"
    assert prof["m"]["base_url"].endswith("/v1")
