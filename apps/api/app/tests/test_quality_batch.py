"""品質向上バッチ(パイプライン / ツインミラー修正 / 形状チェック / bbox同期 / GIF)のテスト。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.models.parts import Part, PartType, SegmentationSpec


# ---------------------------------------------------------------- パイプライン

def test_auto_pipeline_e2e(client, project_id):
    """ワンボタンで最終スコアまで到達し、成果物が揃う。"""
    from app.tests.test_e2e_flow import _wait_job

    res = client.post(f"/api/v1/projects/{project_id}/pipeline/auto")
    assert res.status_code == 202, res.text
    job = _wait_job(client, res.json()["job_id"], timeout=180.0)
    assert job["status"] == "done", job

    res = client.get(f"/api/v1/projects/{project_id}/pipeline/summary")
    assert res.status_code == 200
    summary = res.json()
    assert 0 <= summary["final_score"] <= 100
    assert summary["orphan_px_after"] == 0
    step_names = [s["step"] for s in summary["steps"]]
    assert "セグメンテーション" in step_names
    assert "モーション穴補完" in step_names

    # 成果物: レイヤー・品質レポート・モーションGIF
    from app.core.paths import ProjectPaths
    paths = ProjectPaths(project_id)
    assert paths.layer_png("face_base").exists()
    assert paths.quality_report_json.exists()
    gif = paths.previews_dir / "motion_preview.gif"
    assert gif.exists()
    with Image.open(gif) as img:
        assert getattr(img, "n_frames", 1) > 1


# ---------------------------------------------------------- ツイン自動ミラー

def test_autofix_mirrors_missing_twin_mask(client, project_id):
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run/eye_white_l")
    assert res.status_code == 200, res.text

    res = client.post(f"/api/v1/projects/{project_id}/quality/check")
    issues = res.json()["issues"]
    target = [
        i for i in issues
        if i["part_id"] == "eye_white_r" and i["code"] == "MISSING_MASK"
    ]
    assert target and target[0]["auto_fix_available"] is True

    res = client.post(f"/api/v1/projects/{project_id}/quality/autofix")
    assert res.status_code == 200
    applied = res.json()["applied"]
    assert any(
        a["part_id"] == "eye_white_r" and a["code"] == "MISSING_MASK"
        for a in applied
    )
    from app.core.paths import ProjectPaths
    assert ProjectPaths(project_id).mask_png("eye_white_r").exists()


# ------------------------------------------------------------ マスク形状チェック

def _shape_part(pid: str, bbox: list[int]) -> Part:
    return Part(id=pid, name_jp=pid, part_type=PartType.other,
                segmentation=SegmentationSpec(bbox=bbox))


def test_mask_fragmented_detected(tmp_path):
    from app.core.paths import ProjectPaths
    from app.services.quality_service import _check_mask_shape

    paths = ProjectPaths("frag_test")
    paths.ensure_dirs()
    mask = np.zeros((200, 200), np.uint8)
    mask[50:100, 50:100] = 255  # 本体
    for i in range(6):          # 飛び地ノイズ
        y = 120 + 10 * i
        mask[y : y + 4, 150 : 154 + 20 * (i % 2)] = 255
    Image.fromarray(mask, "L").save(paths.mask_png("hair"))

    issues = _check_mask_shape(paths, _shape_part("hair", [40, 40, 140, 140]))
    codes = [i.code.value for i in issues]
    assert "MASK_FRAGMENTED" in codes


def test_mask_too_small_detected():
    from app.core.paths import ProjectPaths
    from app.services.quality_service import _check_mask_shape

    paths = ProjectPaths("small_test")
    paths.ensure_dirs()
    mask = np.zeros((200, 200), np.uint8)
    mask[100:104, 100:104] = 255  # bbox に対して極小
    Image.fromarray(mask, "L").save(paths.mask_png("eye"))

    issues = _check_mask_shape(paths, _shape_part("eye", [50, 50, 100, 100]))
    codes = [i.code.value for i in issues]
    assert "MASK_TOO_SMALL" in codes


def test_healthy_mask_no_issues():
    from app.core.paths import ProjectPaths
    from app.services.quality_service import _check_mask_shape

    paths = ProjectPaths("healthy_test")
    paths.ensure_dirs()
    mask = np.zeros((200, 200), np.uint8)
    mask[50:150, 50:150] = 255
    Image.fromarray(mask, "L").save(paths.mask_png("face"))

    assert _check_mask_shape(paths, _shape_part("face", [45, 45, 110, 110])) == []


# ---------------------------------------------------------------- bbox 同期

def test_sync_bbox_to_mask(client, project_id):
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run/face_base")
    assert res.status_code == 200, res.text

    res = client.post(f"/api/v1/projects/{project_id}/masks/face_base/sync-bbox")
    assert res.status_code == 200, res.text
    bbox = res.json()["bbox"]

    # bbox がマスクの実範囲(+余白4px)に一致する
    from app.services import mask_service
    mask = mask_service.load_mask(project_id, "face_base")
    ys, xs = np.nonzero(mask > 127)
    assert bbox[0] == max(0, xs.min() - 4)
    assert bbox[1] == max(0, ys.min() - 4)

    # parts.json にも反映されている
    res = client.get(f"/api/v1/projects/{project_id}/parts")
    part = next(p for p in res.json()["parts"] if p["id"] == "face_base")
    assert part["segmentation"]["bbox"] == bbox
