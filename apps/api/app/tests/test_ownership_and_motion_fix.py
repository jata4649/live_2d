"""ピクセル所有権ソルバーとモーション穴自動補完のテスト。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.models.parts import Part, PartsPlan, PartType, SegmentationSpec


def _write_project(project_id: str, rgba: np.ndarray, parts: list[Part],
                   masks: dict[str, np.ndarray] | None = None,
                   layers: dict[str, np.ndarray] | None = None):
    from app.core.paths import ProjectPaths

    paths = ProjectPaths(project_id)
    paths.ensure_dirs()
    Image.fromarray(rgba, "RGBA").save(paths.normalized_image)
    paths.parts_json.write_text(
        PartsPlan(version="1.0", parts=parts).model_dump_json(indent=2),
        encoding="utf-8",
    )
    for pid, m in (masks or {}).items():
        Image.fromarray(m, "L").save(paths.mask_png(pid))
    for pid, arr in (layers or {}).items():
        Image.fromarray(arr, "RGBA").save(paths.layer_png(pid))
    return paths


# ------------------------------------------------------------ 所有権ソルバー

def test_resolve_orphans_assigns_gap_to_color_matching_part():
    """2マスクの隙間の孤児ピクセルが、色の近いパーツへ編入される。"""
    from app.services.ownership_service import resolve_orphans

    size = 300
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[50:250, 50:150] = [120, 70, 40, 255]    # 左: 髪色
    rgba[50:250, 150:250] = [255, 220, 190, 255]  # 右: 肌色

    hair_mask = np.zeros((size, size), np.uint8)
    hair_mask[50:250, 50:140] = 255   # 髪の右端 10px は取りこぼし(孤児)
    face_mask = np.zeros((size, size), np.uint8)
    face_mask[50:250, 150:250] = 255

    parts = [
        Part(id="hair", name_jp="髪", z_order=20, part_type=PartType.hair,
             segmentation=SegmentationSpec(bbox=[50, 50, 100, 200])),
        Part(id="face", name_jp="顔", z_order=10, part_type=PartType.face,
             segmentation=SegmentationSpec(bbox=[150, 50, 100, 200])),
    ]
    _write_project("orphan_test", rgba, parts,
                   masks={"hair": hair_mask, "face": face_mask})

    report = resolve_orphans("orphan_test")
    assert report.orphan_px_before == 200 * 10
    assert report.orphan_px_after == 0
    # 髪色の隙間は(肌色の顔ではなく)髪へ編入される
    assert report.assignments[0].part_id == "hair"

    from app.services import mask_service
    hair_after = mask_service.load_mask("orphan_test", "hair")
    assert (hair_after[100, 140:150] > 127).all()


def test_resolve_orphans_island_goes_to_nearest():
    """どのマスクとも隣接しない孤島は最近傍パーツへ編入される。"""
    from app.services.ownership_service import resolve_orphans

    size = 300
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[50:250, 50:150] = [120, 70, 40, 255]
    rgba[100:120, 200:220] = [120, 70, 40, 255]  # 離れ小島(アホ毛の先など)

    hair_mask = np.zeros((size, size), np.uint8)
    hair_mask[50:250, 50:150] = 255

    parts = [
        Part(id="hair", name_jp="髪", z_order=20, part_type=PartType.hair,
             segmentation=SegmentationSpec(bbox=[50, 50, 100, 200])),
    ]
    _write_project("island_test", rgba, parts, masks={"hair": hair_mask})

    report = resolve_orphans("island_test")
    assert report.orphan_px_after == 0
    assert report.assignments[0].part_id == "hair"


def test_resolve_orphans_endpoint_e2e(client, project_id):
    """一気通貫: 解析 → セグメント → 整合 → 孤児ゼロ。"""
    from app.tests.test_e2e_flow import _wait_job

    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run")
    assert _wait_job(client, res.json()["job_id"])["status"] == "done"

    res = client.post(f"/api/v1/projects/{project_id}/masks/resolve-orphans")
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["orphan_px_after"] == 0


# ------------------------------------------------------------ モーション穴補完

def test_fix_motion_holes_fills_underlying_layer():
    """髪の下の欠けが、髪を揺らして見える範囲だけ下地へ焼き込まれる。"""
    from app.services.motion_check_service import fix_motion_holes, run_motion_check

    size = 200
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[50:150, 50:150] = [80, 100, 200, 255]

    base = np.zeros((size, size, 4), np.uint8)
    base[50:150, 50:150] = [80, 100, 200, 255]
    base[80:120, 80:120] = 0  # 髪の真下が欠けている
    hair = np.zeros((size, size, 4), np.uint8)
    hair[80:120, 80:120] = [120, 70, 40, 255]

    parts = [
        Part(id="body_base", name_jp="体", z_order=0, part_type=PartType.body),
        Part(id="hair_front", name_jp="前髪", z_order=10, part_type=PartType.hair),
    ]
    _write_project("motion_fix_test", rgba, parts,
                   layers={"body_base": base, "hair_front": hair})

    before = run_motion_check("motion_fix_test")
    assert before.entries  # 穴がある

    result = fix_motion_holes("motion_fix_test")
    assert result.fills
    assert result.fills[0].moved_part_id == "hair_front"
    assert result.fills[0].target_part_id == "body_base"
    assert result.fills[0].filled_px > 0
    # 補完後の再チェックで穴が消えている
    assert result.report_after.entries == []

    # 下地レイヤーの補完領域は周囲の色(青系)で塗られている
    from app.core.paths import ProjectPaths
    paths = ProjectPaths("motion_fix_test")
    with Image.open(paths.layer_png("body_base")) as img:
        fixed = np.asarray(img.convert("RGBA"))
    filled = fixed[:, :, 3] > 8
    assert filled[90, 82]  # 左端ストリップ(揺らすと見える範囲)
    assert fixed[90, 82, 2] > 150  # 青が支配的


def test_motion_fix_endpoint(client, project_id):
    """API 経由: レイヤー生成後に motion-fix が 200 を返す。"""
    from app.tests.test_e2e_flow import _wait_job

    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run")
    assert _wait_job(client, res.json()["job_id"])["status"] == "done"
    res = client.post(f"/api/v1/projects/{project_id}/layers/generate")
    assert _wait_job(client, res.json()["job_id"])["status"] == "done"

    res = client.post(f"/api/v1/projects/{project_id}/quality/motion-fix")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "fills" in body and "report_after" in body
