"""AI環境診断エンドポイントと auto アナライザーのテスト。"""
from __future__ import annotations


def test_environment_endpoint(client):
    res = client.get("/api/v1/environment")
    assert res.status_code == 200
    env = res.json()
    assert {"analyzers", "segmenters", "bg_removal", "torch",
            "anthropic_key_set", "hints"} <= set(env.keys())
    names = {a["name"] for a in env["analyzers"]}
    assert {"mock", "claude"} <= names
    methods = {s["method"] for s in env["segmenters"]}
    assert "sam2_box" in methods


def test_auto_analyzer_falls_back_to_mock(monkeypatch):
    import app.ai.claude_analyzer as ca
    from app.ai.mock_analyzer import get_analyzer

    monkeypatch.setattr(ca, "claude_available", lambda: (False, "なし"))
    assert get_analyzer("auto").name == "mock"


def test_auto_analyzer_prefers_claude(monkeypatch):
    import app.ai.claude_analyzer as ca
    from app.ai.mock_analyzer import get_analyzer

    class DummyClaude:
        name = "claude"

    monkeypatch.setattr(ca, "claude_available", lambda: (True, ""))
    monkeypatch.setattr(ca, "ClaudeAnalyzer", DummyClaude)
    assert get_analyzer("auto").name == "claude"


def test_analyze_endpoint_accepts_auto(client, project_id):
    """auto 指定でも(キーなし環境では mock として)解析が成功する。"""
    res = client.post(f"/api/v1/projects/{project_id}/analyze",
                      json={"analyzer": "auto"})
    assert res.status_code == 200, res.text
    assert len(res.json()["parts"]) > 0
