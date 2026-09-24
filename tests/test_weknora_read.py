from common.weknora_read import hybrid_search, list_knowledge_bases


def test_weknora_reads_fail_closed_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("WEKNORA_API_KEY", raising=False)
    assert list_knowledge_bases().startswith("TOOL_ERROR:")
    assert hybrid_search("pyosis", "create_conc").startswith("TOOL_ERROR:")
