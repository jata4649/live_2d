"""パーツ分け精度向上(人物範囲フィット + 色ベース分離)のテスト。"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.image_processing.character_bounds import character_bbox, fit_bbox
from app.tests.conftest import make_test_character


# ---------------------------------------------------------------- 人物範囲検出

def test_character_bbox_from_alpha():
    """透明背景画像: 人物の不透明領域のバウンディングボックスを検出する。"""
    rgba = np.zeros((200, 300, 4), np.uint8)
    rgba[50:180, 100:220] = [200, 150, 120, 255]
    bbox = character_bbox(rgba)
    assert bbox == [100, 50, 120, 130]


def test_character_bbox_from_bg_color():
    """不透明画像: 四隅の背景色との色差で人物を検出する。"""
    rgba = np.full((200, 300, 4), [240, 240, 240, 255], np.uint8)
    rgba[40:190, 80:240] = [90, 60, 40, 255]
    bbox = character_bbox(rgba)
    assert bbox is not None
    x, y, w, h = bbox
    assert abs(x - 80) <= 2 and abs(y - 40) <= 2
    assert abs(w - 160) <= 4 and abs(h - 150) <= 4


def test_character_bbox_none_for_noisy_corners():
    """四隅の色が不揃い(写真背景など)なら None を返す。"""
    rng = np.random.default_rng(0)
    rgba = rng.integers(0, 255, (100, 100, 4), dtype=np.uint8)
    rgba[:, :, 3] = 255
    assert character_bbox(rgba) is None


def test_fit_bbox_affine():
    # テンプレート範囲 (0,0,100,100) → 実範囲 (50,20,200,300)
    assert fit_bbox([10, 10, 20, 20], [0, 0, 100, 100], [50, 20, 200, 300]) == [
        70, 50, 40, 60,
    ]


# ---------------------------------------------------------------- 解析フィット

def test_analyze_fits_template_to_character(client):
    """余白の大きい画像でも、bbox が人物範囲内に収まるよう再配置される。"""
    # 512x768 のキャラを 1024x1024 キャンバスの左上寄りに配置
    chara = Image.open(io.BytesIO(make_test_character())).convert("RGBA")
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.paste(chara, (60, 120))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")

    res = client.post(
        "/api/v1/projects",
        data={"name": "offset_chara"},
        files={"image": ("c.png", buf.getvalue(), "image/png")},
    )
    pid = res.json()["project_id"]
    res = client.post(f"/api/v1/projects/{pid}/analyze", json={"analyzer": "mock"})
    parts = {p["id"]: p for p in res.json()["parts"]}

    # キャラの頭部は元画像の y 0.02-0.38 → キャンバス上では y 135〜412 付近
    face = parts["face_base"]["segmentation"]["bbox"]
    fx, fy, fw, fh = face
    # 人物範囲(x 60〜572+α, y 120〜850 付近)の中に face bbox が収まる
    assert 60 <= fx and fx + fw <= 640
    assert 120 <= fy and fy + fh <= 500
    # フィットなしの旧挙動(キャンバス比率: x=0.34*1024=348)とは異なる位置
    assert fx != round(0.34 * 1024)


# ---------------------------------------------------------------- 色ベース分離

def test_grabcut_color_separation_for_inner_parts():
    """不透明領域の内部パーツ(肌の上の目)は色で分離される。"""
    from app.models.parts import SegmentationMethod
    from app.models.segmentation import SegmentationTask
    from app.segmentation.manual_box_segmenter import ManualBoxSegmenter

    # 肌色の顔の上に緑の目。bbox は目より一回り大きく、bbox 内は全て不透明。
    # 画像を大きめにして bbox が画像の5%以下(小パーツ判定)になるようにする
    rgba = np.zeros((400, 400, 4), np.uint8)
    rgba[20:380, 20:380] = [255, 220, 190, 255]      # 顔(肌)
    rgba[80:110, 70:130] = [30, 120, 40, 255]        # 目(緑)

    seg = ManualBoxSegmenter()
    task = SegmentationTask(
        task_id="t", part_id="eye",
        method=SegmentationMethod.manual_box,
        bbox=[55, 65, 90, 60],  # 目の周囲に肌の余白を含む
    )
    result = seg.segment(rgba, task)

    assert "grabcut_color" in result.method_used
    mask = result.mask > 127
    # 目の中心は前景
    assert mask[95, 100]
    # マスクの大部分が目の色のピクセル(肌を巻き込んでいない)
    green = (rgba[:, :, 1] > 100) & (rgba[:, :, 0] < 100)
    assert (mask & green).sum() / max(1, mask.sum()) > 0.7
    # bbox 全体(90*60)より十分小さい = 矩形をそのまま返していない
    assert mask.sum() < 90 * 60 * 0.9


def test_alpha_path_still_used_for_contour_parts():
    """透過境界を含む輪郭系パーツは従来どおりアルファ切り抜き。"""
    from app.models.parts import SegmentationMethod
    from app.models.segmentation import SegmentationTask
    from app.segmentation.manual_box_segmenter import ManualBoxSegmenter

    rgba = np.zeros((100, 100, 4), np.uint8)
    rgba[40:90, 30:70] = [120, 70, 40, 255]  # 髪の房(周囲は透明)

    seg = ManualBoxSegmenter()
    task = SegmentationTask(
        task_id="t", part_id="hair",
        method=SegmentationMethod.manual_box,
        bbox=[20, 30, 60, 65],
    )
    result = seg.segment(rgba, task)
    assert "alpha" in result.method_used
    assert (result.mask > 127).sum() == 50 * 40
