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


def test_knowledge_endpoint(cfg, tmp_path):
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    kb = client.get("/api/knowledge").json()
    assert kb["total_reels"] == 2
    assert any(t["name"] == "product" for t in kb["topics"])


def test_search_missing_index_409(cfg, tmp_path):
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    # no index built in temp dir -> 409
    assert client.get("/api/search", params={"q": "x"}).status_code == 409


def test_chat_endpoint(cfg, tmp_path, monkeypatch):
    from reels_scrap.chat import rag

    monkeypatch.setattr(
        rag, "semantic_search",
        lambda c, q, k=8: [{"reel_id": "AAA", "title": "Homelab repos",
                            "url": "u", "kind": "fact", "text": "coolify",
                            "score": 0.8, "timestamp": None}],
    )
    monkeypatch.setattr(rag, "claude_text", lambda *a, **k: "answer [AAA]")
    client = TestClient(appmod.create_app(str(tmp_path / "config.yaml")))
    r = client.post("/api/chat", json={"question": "what?", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "answer [AAA]"
    assert body["citations"][0]["reel_id"] == "AAA"
