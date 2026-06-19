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
    import reels_scrap.chat.rag as rag

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
