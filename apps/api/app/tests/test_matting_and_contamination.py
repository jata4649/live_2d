"""アルファマッティング(ソフトエッジ)と混入検出のテスト。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.models.parts import (
    Part,
    PartsPlan,
    PartType,
    SegmentationSpec,
)


# ---------------------------------------------------------------- ソフトエッジ

def _hair_like_image(size: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """アンチエイリアスされた斜めエッジを持つ画像と、それを跨ぐ2値マスク。"""
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[:, :, 3] = 255
    yy, xx = np.mgrid[0:size, 0:size]
    # 斜めの境界: 左上=髪(暗)、右下=背景(明)。境界2px はグラデーション
    d = (xx + yy) - size
    hair = np.clip(0.5 - d / 4.0, 0, 1)  # 1=髪, 0=背景
    rgba[:, :, 0] = (120 * hair + 240 * (1 - hair)).astype(np.uint8)
    rgba[:, :, 1] = (70 * hair + 240 * (1 - hair)).astype(np.uint8)
    rgba[:, :, 2] = (40 * hair + 240 * (1 - hair)).astype(np.uint8)
    mask = np.where(d < 0, 255, 0).astype(np.uint8)  # 硬い2値マスク
    return rgba, mask


def test_soft_edge_alpha_creates_intermediate_values():
    from app.image_processing.matting import soft_edge_alpha

    rgba, mask = _hair_like_image()
    out = soft_edge_alpha(rgba, mask)

    # 境界帯に中間アルファ(0でも255でもない値)が生まれる
    intermediate = ((out > 16) & (out < 240)).sum()
    assert intermediate > 100
    # マスク深部(境界から十分内側/外側)は変化しない
    assert out[10, 10] == 255
    assert out[190, 190] == 0
    # 元の2値マスクとの面積が大きくズレない(±10%)
    assert abs(int(out.astype(np.int64).sum()) - int(mask.astype(np.int64).sum())) \
        < 0.1 * mask.astype(np.int64).sum() + 1


def test_soft_edge_alpha_keeps_transparent_pixels():
    from app.image_processing.matting import soft_edge_alpha

    rgba, mask = _hair_like_image()
    rgba[:, :100, 3] = 0  # 左半分は元画像が透明
    out = soft_edge_alpha(rgba, mask)
    assert out[:, :100].max() == 0


def test_soft_edge_alpha_noop_for_empty_and_full():
    from app.image_processing.matting import soft_edge_alpha

    rgba, _ = _hair_like_image()
    empty = np.zeros((200, 200), np.uint8)
    full = np.full((200, 200), 255, np.uint8)
    assert (soft_edge_alpha(rgba, empty) == empty).all()
    assert (soft_edge_alpha(rgba, full) == full).all()


def test_generate_layer_applies_soft_edges(client, project_id):
    """レイヤー生成でソフトエッジが適用され、境界に連続アルファが乗る。"""
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run/face_base")
    assert res.status_code == 200, res.text
    res = client.post(f"/api/v1/projects/{project_id}/layers/generate/face_base")
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------- 混入検出

def _setup_contamination_project(eye_mask_contaminated: bool):
    """肌色の顔 + 緑の目のプロジェクトを直接構築する。"""
    from app.core.paths import ProjectPaths

    project_id = "contam_test"
    paths = ProjectPaths(project_id)
    paths.ensure_dirs()

    size = 400
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[20:380, 20:380] = [255, 220, 190, 255]   # 顔(肌)
    rgba[100:140, 120:200] = [30, 60, 220, 255]   # 目(青)
    Image.fromarray(rgba, "RGBA").save(paths.normalized_image)

    face_mask = np.zeros((size, size), np.uint8)
    face_mask[20:380, 20:380] = 255
    eye_mask = np.zeros((size, size), np.uint8)
    eye_mask[100:140, 120:200] = 255
    if eye_mask_contaminated:
        # 目マスクが下の肌を大きく巻き込んでいる(混入)
        eye_mask[140:200, 120:200] = 255
    Image.fromarray(face_mask, "L").save(paths.mask_png("face_base"))
    Image.fromarray(eye_mask, "L").save(paths.mask_png("eye_l"))

    parts = [
        Part(id="face_base", name_jp="顔", z_order=10, part_type=PartType.face,
             group="Face",
             segmentation=SegmentationSpec(bbox=[20, 20, 360, 360])),
        Part(id="eye_l", name_jp="目", z_order=50, part_type=PartType.eye,
             group="Eye_L",
             segmentation=SegmentationSpec(bbox=[120, 100, 80, 100])),
    ]
    paths.parts_json.write_text(
        PartsPlan(version="1.0", parts=parts).model_dump_json(indent=2),
        encoding="utf-8",
    )
    return project_id, PartsPlan(version="1.0", parts=parts)


def test_contamination_detected_for_dirty_eye_mask():
    from app.services.quality_service import _check_color_contamination

    pid, plan = _setup_contamination_project(eye_mask_contaminated=True)
    issues = _check_color_contamination(pid, plan)
    assert any(
        i.part_id == "eye_l" and i.code.value == "COLOR_CONTAMINATION"
        for i in issues
    )
    # 下地側(顔)が目の領域を含むのは正常なので警告しない
    assert not any(i.part_id == "face_base" for i in issues)


def test_no_contamination_for_clean_masks():
    from app.services.quality_service import _check_color_contamination

    pid, plan = _setup_contamination_project(eye_mask_contaminated=False)
    issues = _check_color_contamination(pid, plan)
    assert issues == []
