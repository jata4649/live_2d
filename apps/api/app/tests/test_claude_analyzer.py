"""ClaudeAnalyzer のテスト(実APIは呼ばず、フェイククライアントを注入)。"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.ai.claude_analyzer import ClaudeAnalyzer, extract_json
from app.models.project import UserPreferences


class FakeClient:
    """client.messages.stream(...) を模倣し、応答列を順に返す。"""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.requests: list[dict] = []

        outer = self

        class _Messages:
            @contextmanager
            def stream(self, **kwargs):
                outer.requests.append(kwargs)
                text = outer._responses.pop(0)
                message = SimpleNamespace(
                    stop_reason="end_turn",
                    content=[SimpleNamespace(type="text", text=text)],
                )
                yield SimpleNamespace(get_final_message=lambda: message)

        self.messages = _Messages()


def _valid_plan_json(bbox=(10, 20, 30, 40)) -> str:
    return json.dumps({
        "version": "1.0",
        "parts": [{
            "id": "front_hair_01",
            "name_jp": "前髪",
            "name_en": "Front Hair",
            "group": "Hair/Front",
            "z_order": 120,
            "part_type": "hair",
            "segmentation": {"method": "manual_box", "bbox": list(bbox)},
        }],
    })


def _make_images(tmp_path: Path, full=(1024, 1536), working=(512, 768)) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    Image.new("RGBA", full).save(src / "normalized.png")
    Image.new("RGBA", working).save(src / "working.png")
    return src / "normalized.png"


def test_extract_json_strips_fences():
    text = '説明です。\n```json\n{"a": 1}\n```\n以上。'
    assert extract_json(text) == {"a": 1}


def test_extract_json_bare_object():
    assert extract_json('前置き {"a": {"b": 2}} 後置き') == {"a": {"b": 2}}


def test_extract_json_rejects_no_json():
    with pytest.raises(ValueError):
        extract_json("JSONがありません")


def test_analyze_scales_bbox_to_full_resolution(tmp_path):
    """working.png(1/2縮小)を送った場合、bbox は2倍に換算される。"""
    image = _make_images(tmp_path)
    client = FakeClient([_valid_plan_json(bbox=(10, 20, 30, 40))])
    analyzer = ClaudeAnalyzer(client=client)

    plan = analyzer.analyze_character_image(image, UserPreferences())

    assert plan.parts[0].segmentation.bbox == [20, 40, 60, 80]
    # 画像は縮小版が base64 で送られている
    content = client.requests[0]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    # adaptive thinking / モデル指定を確認
    assert client.requests[0]["thinking"] == {"type": "adaptive"}
    assert client.requests[0]["model"] == "claude-opus-4-8"


def test_analyze_retries_on_invalid_json(tmp_path):
    """1回目が不正なら検証エラーをフィードバックして再試行する。"""
    image = _make_images(tmp_path)
    client = FakeClient(["これはJSONではありません", _valid_plan_json()])
    analyzer = ClaudeAnalyzer(client=client)

    plan = analyzer.analyze_character_image(image, UserPreferences())

    assert len(client.requests) == 2
    assert plan.parts[0].id == "front_hair_01"
    # 再試行プロンプトにエラー内容が含まれる
    retry_text = client.requests[1]["messages"][0]["content"][-1]["text"]
    assert "エラー" in retry_text


def test_analyze_fills_missing_file_paths(tmp_path):
    image = _make_images(tmp_path)
    client = FakeClient([_valid_plan_json()])
    plan = ClaudeAnalyzer(client=client).analyze_character_image(
        image, UserPreferences()
    )
    assert plan.parts[0].files.mask_path == "masks/front_hair_01_mask.png"
    assert plan.parts[0].files.layer_path == "layers/front_hair_01.png"


def test_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    from app.ai.claude_analyzer import AnalyzerUnavailableError

    with pytest.raises(AnalyzerUnavailableError):
        ClaudeAnalyzer()


def test_analyzers_endpoint(client):
    res = client.get("/api/v1/analyzers")
    assert res.status_code == 200
    names = {a["name"] for a in res.json()}
    assert names == {"mock", "claude"}
    mock_entry = next(a for a in res.json() if a["name"] == "mock")
    assert mock_entry["available"] is True
