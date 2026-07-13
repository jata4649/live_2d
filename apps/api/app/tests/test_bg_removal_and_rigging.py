"""背景除去(rembg 統合)とリギング設計書強化のテスト。"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.models.parts import Part, PartsPlan, PartType, SegmentationSpec
from app.models.project import UserPreferences


# ---------------------------------------------------------------- 背景除去

def _opaque_character_jpg() -> bytes:
    """背景つき(完全不透明)のキャラ画像 JPG。"""
    img = Image.new("RGB", (400, 600), (240, 240, 240))
    d = np.asarray(img).copy()
    d[100:500, 150:250] = [120, 70, 40]  # 人物っぽい矩形
    buf = io.BytesIO()
    Image.fromarray(d).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_bg_removal_generates_alpha(client, monkeypatch):
    """rembg が使える環境では、不透明画像にアルファが生成される。"""
    import app.image_processing.bg_removal as bg

    def fake_removal(img: Image.Image) -> Image.Image:
        mask = np.zeros((img.height, img.width), np.uint8)
        mask[100:500, 150:250] = 255
        return Image.fromarray(mask, "L")

    monkeypatch.setattr(bg, "bg_removal_available", lambda: (True, ""))
    monkeypatch.setattr(bg, "_run_removal", fake_removal)

    res = client.post(
        "/api/v1/projects",
        data={"name": "jpg_chara"},
        files={"image": ("c.jpg", _opaque_character_jpg(), "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source_image"]["has_alpha"] is True

    from app.core.paths import ProjectPaths
    with Image.open(ProjectPaths(body["project_id"]).normalized_image) as img:
        rgba = np.asarray(img.convert("RGBA"))
    assert rgba[300, 200, 3] == 255  # 人物は不透明
    assert rgba[50, 50, 3] == 0      # 背景は透明


def test_bg_removal_skipped_when_unavailable(client, monkeypatch):
    """rembg 未導入なら従来どおり(不透明のまま)動作する。"""
    import app.image_processing.bg_removal as bg

    monkeypatch.setattr(bg, "bg_removal_available", lambda: (False, "未導入"))
    res = client.post(
        "/api/v1/projects",
        data={"name": "jpg_plain"},
        files={"image": ("c.jpg", _opaque_character_jpg(), "image/jpeg")},
    )
    assert res.status_code == 200
    assert res.json()["source_image"]["has_alpha"] is False


def test_bg_removal_rejects_degenerate_masks(monkeypatch):
    """全消し/全残しの結果は失敗とみなし None を返す(従来動作へ)。"""
    import app.image_processing.bg_removal as bg

    rgba = np.full((100, 100, 4), [200, 200, 200, 255], np.uint8)
    monkeypatch.setattr(
        bg, "_run_removal",
        lambda img: Image.fromarray(np.zeros((100, 100), np.uint8), "L"),
    )
    assert bg.remove_background(rgba) is None


# ---------------------------------------------------------------- リギング強化

def _plan_with_physics() -> PartsPlan:
    parts = [
        Part(id="face_base", name_jp="顔", part_type=PartType.face, z_order=70,
             segmentation=SegmentationSpec(bbox=[100, 50, 200, 250]),
             live2d={"parent_deformer_hint": "D_Head", "usage": ["ParamAngleX"]}),
        Part(id="front_hair", name_jp="前髪", part_type=PartType.hair, z_order=110,
             segmentation=SegmentationSpec(bbox=[90, 30, 220, 150]),
             live2d={"parent_deformer_hint": "D_Hair_Front",
                     "physics_hint": "hair_soft"}),
        Part(id="body_base", name_jp="体", part_type=PartType.body, z_order=10,
             segmentation=SegmentationSpec(bbox=[120, 280, 160, 500]),
             live2d={"parent_deformer_hint": "D_Body"}),
    ]
    return PartsPlan(version="1.0", parts=parts)


def test_rigging_plan_mermaid_and_physics():
    from app.services.rigging_plan_service import render_rigging_plan

    md = render_rigging_plan(_plan_with_physics(), UserPreferences())

    # Mermaid ツリー: 使用デフォーマのみ + 中間ノード
    assert "```mermaid" in md
    assert "D_Head --> D_Hair_Front" in md
    assert "D_Body --> D_Head" in md
    assert "Root --> D_Body" in md
    assert "D_Eye_L" not in md.split("```mermaid")[1].split("```")[0]  # 未使用は出ない

    # 物理テーブル: bbox 比から振り子の長さが算出される
    # canvas_h = max(y+h) = 780, 前髪 bh=150 → 5 + 20*150/780 ≈ 9
    assert "| 前髪(`front_hair`) | hair_soft | 9 | 0.90 | 0.75 |" in md


def test_rigging_plan_reflects_face_range():
    from app.models.project import FaceRange
    from app.services.rigging_plan_service import render_rigging_plan

    small = render_rigging_plan(
        _plan_with_physics(), UserPreferences(face_range=FaceRange.small)
    )
    large = render_rigging_plan(
        _plan_with_physics(), UserPreferences(face_range=FaceRange.large)
    )
    assert "| ParamAngleX | 顔の左右回転 | -15〜15 |" in small
    assert "| ParamAngleX | 顔の左右回転 | -40〜40 |" in large
