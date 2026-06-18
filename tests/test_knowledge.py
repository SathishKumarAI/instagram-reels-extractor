from reels_scrap.knowledge import build_knowledge, load_knowledge


def test_aggregates_by_genre(cfg):
    kb = build_knowledge(cfg)
    assert kb.total_reels == 2
    names = {t.name for t in kb.topics}
    assert {"educational", "product"} <= names
    edu = next(t for t in kb.topics if t.name == "educational")
    assert edu.reel_count == 1
    assert any("coolify" in f.text for f in edu.facts)
    assert "homelab" in edu.hashtags


def test_knowledge_is_cached(cfg):
    build_knowledge(cfg)
    assert (cfg.knowledge_dir / "knowledge.json").exists()
    kb = load_knowledge(cfg)  # reads cache, no rebuild
    assert kb.total_reels == 2
