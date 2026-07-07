"""テスト共通フィクスチャ。

outputs を一時ディレクトリに向けてから app を import する。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))


@pytest.fixture(autouse=True)
def isolated_outputs(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "outputs_root", tmp_path / "outputs")
    monkeypatch.setattr(settings, "db_path", tmp_path / "outputs" / "als.sqlite3")
    from app.db.database import init_db

    init_db()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app, raise_server_exceptions=False)


def make_test_character(width: int = 512, height: int = 768) -> bytes:
    """透明背景の簡易キャラ画像(頭・体・目・口)を生成する。"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 体
    d.rectangle([width * 0.35, height * 0.38, width * 0.65, height * 0.95],
                fill=(80, 100, 200, 255))
    # 頭
    d.ellipse([width * 0.32, height * 0.05, width * 0.68, height * 0.38],
              fill=(255, 220, 190, 255))
    # 髪
    d.ellipse([width * 0.30, height * 0.02, width * 0.70, height * 0.22],
              fill=(120, 70, 40, 255))
    # 目
    d.ellipse([width * 0.39, height * 0.18, width * 0.47, height * 0.23],
              fill=(255, 255, 255, 255))
    d.ellipse([width * 0.53, height * 0.18, width * 0.61, height * 0.23],
              fill=(255, 255, 255, 255))
    d.ellipse([width * 0.41, height * 0.19, width * 0.45, height * 0.225],
              fill=(40, 90, 40, 255))
    d.ellipse([width * 0.55, height * 0.19, width * 0.59, height * 0.225],
              fill=(40, 90, 40, 255))
    # 口
    d.ellipse([width * 0.45, height * 0.28, width * 0.55, height * 0.31],
              fill=(200, 80, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def character_png() -> bytes:
    return make_test_character()


@pytest.fixture
def project_id(client, character_png) -> str:
    res = client.post(
        "/api/v1/projects",
        data={"name": "test_vtuber"},
        files={"image": ("chara.png", character_png, "image/png")},
    )
    assert res.status_code == 200, res.text
    return res.json()["project_id"]
