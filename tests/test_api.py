"""API tests via TestClient. Search/chat are monkeypatched to stay offline."""

from __future__ import annotations

from fastapi.testclient import TestClient

import reels_scrap.api.app as appmod


def _client(cfg, monkeypatch, config_path):
    # create_app loads its own Config; point it at our temp config file
    return TestClient(appmod.create_app(config_path))


def test_health_and_reels(cfg, tmp_path):
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    assert client.get("/api/health").json()["reels"] == 2
    reels = client.get("/api/reels").json()
    assert {r["id"] for r in reels} == {"AAA", "BBB"}
    assert client.get("/api/reels/AAA").json()["genre"] == "educational"
    assert client.get("/api/reels/NOPE").status_code == 404


def test_provenance_and_collections(cfg, tmp_path):
    """M1/M4: the UI must be able to say who wrote a record and which shelf it is on."""
    from reels_scrap.collections import Manifest, save_manifest
    from reels_scrap.models import Reel

    r = Reel.load(tmp_path / "data" / "AAA.json")
    r.tokens = {"input": 10, "output": 5, "backend": "local", "model": "reels-vision"}
    r.save(tmp_path / "data")
    save_manifest(tmp_path / "output", Manifest(slug="ai", title="Ai", reel_ids=["AAA"]))
    save_manifest(tmp_path / "output", Manifest(slug="books", title="Books", reel_ids=["AAA"]))

    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    summary = {x["id"]: x for x in client.get("/api/reels").json()}
    assert (summary["AAA"]["backend"], summary["AAA"]["model"]) == ("local", "reels-vision")
    assert summary["AAA"]["collections"] == ["ai", "books"]
    assert summary["BBB"]["model"] == ""       # no provenance stored -> no badge

    detail = client.get("/api/reels/AAA").json()
    assert detail["collections"] == ["ai", "books"]
    assert detail["tokens"]["model"] == "reels-vision"


def test_profiles_endpoint_marks_uninstalled_models(cfg, tmp_path, monkeypatch):
    """The picker must not offer a model that would fail at run time."""
    import reels_scrap.modelreg as modelreg

    monkeypatch.setattr(modelreg, "installed_models", lambda: {"here"})
    monkeypatch.setattr(modelreg, "load_registry", lambda path=modelreg.REGISTRY_FILE: [
        modelreg.ModelEntry(name="here", tag="fam:8b", role="installed one"),
        modelreg.ModelEntry(name="gone", tag="fam:2b", role="not pulled yet"),
    ])
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    rows = {p["name"]: p for p in client.get("/api/profiles").json()}
    assert rows["here"]["installed"] is True and rows["here"]["kind"] == "local"
    assert rows["gone"]["installed"] is False
    assert rows["claude-cli"]["installed"] is True and rows["claude-cli"]["kind"] == "claude-cli"


def test_knowledge_endpoint(cfg, tmp_path):
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    kb = client.get("/api/knowledge").json()
    assert kb["total_reels"] == 2
    assert any(t["name"] == "product" for t in kb["topics"])


def test_search_missing_index_409(cfg, tmp_path):
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    # no index built in temp dir -> 409
    assert client.get("/api/search", params={"q": "x"}).status_code == 409


def test_search_hit_carries_its_collection(cfg, tmp_path, monkeypatch):
    """M7: a hit says which shelf it came off, like every other reel surface does."""
    import reels_scrap.search as search_mod
    from reels_scrap.collections import Manifest, save_manifest

    save_manifest(tmp_path / "output", Manifest(slug="ai", title="Ai", reel_ids=["AAA"]))

    monkeypatch.setattr(search_mod, "search", lambda c, q, k=8: [
        {"reel_id": "AAA", "title": "Homelab repos", "url": "u", "kind": "fact",
         "text": "coolify", "score": 0.9, "timestamp": None},
        {"reel_id": "BBB", "title": "A gadget", "url": "u", "kind": "summary",
         "text": "gadget", "score": 0.4, "timestamp": None},
    ])
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    hits = client.get("/api/search", params={"q": "coolify"}).json()
    assert hits[0]["collections"] == ["ai"]
    assert hits[1]["collections"] == []       # on no shelf -> no chip, not a crash


def test_variants_diff_is_read_only(cfg, tmp_path):
    """M2: diff what is already stored — no model runs, no cost, no re-extraction."""
    from reels_scrap.models import Reel

    r = Reel.load(tmp_path / "data" / "AAA.json")
    r.variants = {
        "claude-cli": {
            "backend": "claude-cli", "model": "claude-sonnet-4-6", "summary": "long one",
            "tags": ["homelab"], "elapsed_s": 30.0, "tokens": {"cost_usd": 0.34},
            "facts": [{"text": "coolify is a self-hostable Heroku alternative"},
                      {"text": "the repo has 30k stars"}],
        },
        "local": {
            "backend": "local", "model": "reels-vision", "summary": "short one",
            "tags": ["homelab"], "elapsed_s": 5.0, "tokens": {},
            "facts": [{"text": "COOLIFY, a self hostable Heroku alternative"}],
        },
    }
    r.save(tmp_path / "data")

    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    d = client.get("/api/reels/AAA/variants/diff").json()
    assert (d["a"], d["b"]) == ("claude-cli", "local")     # reference arm is 'a' by default
    assert d["available"] == ["claude-cli", "local"]
    assert len(d["diff"]["shared"]) == 1                   # same claim, different dress
    assert d["diff"]["only_a"] == ["the repo has 30k stars"]
    assert d["diff"]["only_b"] == []
    assert d["variants"]["local"]["cost_usd"] == 0.0
    assert d["variants"]["claude-cli"]["elapsed_s"] == 30.0

    # a reel with no variants answers, it does not 500
    empty = client.get("/api/reels/BBB/variants/diff").json()
    assert empty["available"] == [] and empty["diff"] == {}
    assert client.get("/api/reels/NOPE/variants/diff").status_code == 404


def test_chat_endpoint(cfg, tmp_path, monkeypatch):
    from reels_scrap.chat import rag

    monkeypatch.setattr(
        rag, "semantic_search",
        lambda c, q, k=8: [{"reel_id": "AAA", "title": "Homelab repos",
                            "url": "u", "kind": "fact", "text": "coolify",
                            "score": 0.8, "timestamp": None}],
    )
    monkeypatch.setattr(rag, "claude_text", lambda *a, **k: "answer [AAA]")
    from reels_scrap.collections import Manifest, save_manifest

    save_manifest(tmp_path / "output", Manifest(slug="ai", title="Ai", reel_ids=["AAA"]))

    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    r = client.post("/api/chat", json={"question": "what?", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "answer [AAA]"
    assert body["citations"][0]["reel_id"] == "AAA"
    # M7: an answer says which shelf it drew from
    assert body["citations"][0]["collections"] == ["ai"]


def test_sync_rejects_unknown_and_uninstalled_models(cfg, tmp_path, monkeypatch):
    """The UI is not the only guard: the API must refuse a model it cannot run."""
    import reels_scrap.modelreg as modelreg

    monkeypatch.setattr(modelreg, "installed_models", lambda: set())
    monkeypatch.setattr(modelreg, "load_registry", lambda path=modelreg.REGISTRY_FILE: [
        modelreg.ModelEntry(name="not-pulled", tag="fam:8b"),
    ])
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))

    r = client.post("/api/sync", json={"backend": "no-such-model"})
    assert r.status_code == 400 and "claude-cli" in r.json()["detail"]

    r = client.post("/api/sync", json={"backend": "not-pulled"})
    assert r.status_code == 400 and "models pull not-pulled" in r.json()["detail"]
