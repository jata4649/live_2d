"""疑似モーションチェックと自動ポイントプロンプトのテスト。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.models.parts import (
    Part,
    PartsPlan,
    PartType,
    SegmentationMethod,
    SegmentationSpec,
)


# ---------------------------------------------------------------- _shift_layer

def test_shift_layer():
    from app.services.motion_check_service import _shift_layer

    layer = np.zeros((10, 10, 4), np.uint8)
    layer[2:5, 3:6] = [255, 0, 0, 255]
    out = _shift_layer(layer, 2, 1)
    assert out[3:6, 5:8, 3].min() == 255  # 移動先
    assert out[2:5, 3:5, 3].max() == 0    # 移動元は空
    # 画像外へはみ出す移動でも例外にならない
    out = _shift_layer(layer, 9, 0)
    assert out[:, :9, 3].max() == 0


# ---------------------------------------------------------------- 穴検出

def _make_layer_project(tmp_layers: dict[str, np.ndarray], parts: list[Part]) -> str:
    """parts.json とレイヤーPNGを直接書き込んだ合成テスト用プロジェクトを作る。"""
    from app.core.paths import ProjectPaths

    project_id = "motion_test"
    paths = ProjectPaths(project_id)
    paths.ensure_dirs()
    paths.parts_json.write_text(
        PartsPlan(version="1.0", parts=parts).model_dump_json(indent=2),
        encoding="utf-8",
    )
    for part_id, arr in tmp_layers.items():
        Image.fromarray(arr, "RGBA").save(paths.layer_png(part_id))
    return project_id


def test_motion_check_detects_hole_under_hair():
    """髪の下に下地がない場合、髪を揺らすと穴として検出される。"""
    from app.services.motion_check_service import run_motion_check

    size = 200
    # 下地: 中央の矩形だが、髪の真下 [80:120, 80:120] だけ透明(欠損)
    base = np.zeros((size, size, 4), np.uint8)
    base[50:150, 50:150] = [80, 100, 200, 255]
    base[80:120, 80:120] = 0
    # 髪: 欠損部分をちょうど覆う
    hair = np.zeros((size, size, 4), np.uint8)
    hair[80:120, 80:120] = [120, 70, 40, 255]

    parts = [
        Part(id="body_base", name_jp="体", z_order=0, part_type=PartType.body),
        Part(id="hair_front", name_jp="前髪", z_order=10, part_type=PartType.hair),
    ]
    pid = _make_layer_project({"body_base": base, "hair_front": hair}, parts)
    report = run_motion_check(pid)

    assert report.checked_parts == 1
    holes = [e for e in report.entries if e.part_id == "hair_front"]
    assert holes and holes[0].hole_px > 0

    from app.core.paths import ProjectPaths
    paths = ProjectPaths(pid)
    assert (paths.previews_dir / "motion_check.png").exists()
    assert (paths.json_dir / "motion_check.json").exists()


def test_motion_check_no_hole_when_base_is_solid():
    """下地が完全に塗られていれば、髪を揺らしても穴は出ない。"""
    from app.services.motion_check_service import run_motion_check

    size = 200
    base = np.zeros((size, size, 4), np.uint8)
    base[50:150, 50:150] = [80, 100, 200, 255]  # 欠損なし
    hair = np.zeros((size, size, 4), np.uint8)
    hair[80:120, 80:120] = [120, 70, 40, 255]

    parts = [
        Part(id="body_base", name_jp="体", z_order=0, part_type=PartType.body),
        Part(id="hair_front", name_jp="前髪", z_order=10, part_type=PartType.hair),
    ]
    pid = _make_layer_project({"body_base": base, "hair_front": hair}, parts)
    report = run_motion_check(pid)

    assert report.checked_parts == 1
    assert report.entries == []


def test_motion_check_api(client, project_id):
    """一気通貫: 解析 → セグメント → レイヤー生成 → モーションチェック。"""
    from app.tests.test_e2e_flow import _wait_job

    res = client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    assert res.status_code == 200, res.text
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run")
    assert res.status_code == 202, res.text
    assert _wait_job(client, res.json()["job_id"])["status"] == "done"
    res = client.post(f"/api/v1/projects/{project_id}/layers/generate")
    assert res.status_code == 202, res.text
    assert _wait_job(client, res.json()["job_id"])["status"] == "done"

    res = client.post(f"/api/v1/projects/{project_id}/quality/motion-check")
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["checked_parts"] >= 1
    assert report["amplitude_px"] >= 4
    assert report["preview_path"].endswith("motion_check.png")


# ---------------------------------------------------------------- auto_prompts

def _part(pid: str, bbox: list[int], ptype: PartType = PartType.other,
          group: str = "") -> Part:
    return Part(
        id=pid, name_jp=pid, part_type=ptype, group=group,
        segmentation=SegmentationSpec(
            method=SegmentationMethod.manual_box, bbox=bbox
        ),
    )


def test_auto_prompts_positive_center_and_inner_negatives():
    """顔 bbox の切り抜きでは、内包する目・口の中心が負例になる。"""
    from app.ai.mock_analyzer import auto_prompts

    face = _part("face_base", [100, 100, 200, 200], PartType.face, group="Face")
    eye = _part("eye_l", [130, 150, 40, 20], PartType.eye, group="Eye_L")
    mouth = _part("mouth", [180, 240, 40, 20], PartType.mouth, group="Mouth")
    outside = _part("body", [100, 320, 200, 300], PartType.body, group="Body")
    plan = PartsPlan(parts=[face, eye, mouth, outside])

    positives, negatives = auto_prompts(face, plan)
    assert positives == [[200, 200]]  # bbox 中心
    assert [150, 160] in negatives    # 目の中心
    assert [200, 250] in negatives    # 口の中心
    assert len(negatives) == 2        # 体(顔の外)は含まれない


def test_auto_prompts_skips_same_group_parts():
    """同グループの内包パーツ(白目の中の虹彩など)は負例にしない。"""
    from app.ai.mock_analyzer import auto_prompts

    eye = _part("eye_white_l", [100, 100, 40, 30], PartType.eye, group="Eye_L")
    iris = _part("iris_l", [110, 105, 15, 15], PartType.eye, group="Eye_L")
    plan = PartsPlan(parts=[eye, iris])

    _, negatives = auto_prompts(eye, plan)
    assert negatives == []


def test_auto_prompts_skips_similar_size_siblings():
    """別グループでも、ほぼ同サイズの重なりパーツは負例にしない。"""
    from app.ai.mock_analyzer import auto_prompts

    eye = _part("eye_white_l", [100, 100, 40, 20], PartType.eye, group="Eye_L")
    lid = _part("eyelid_l", [98, 98, 42, 22], PartType.eye, group="Eyelid_L")
    plan = PartsPlan(parts=[eye, lid])

    _, negatives = auto_prompts(eye, plan)
    assert negatives == []


def test_generate_tasks_adds_auto_points_and_sam2_upgrade(monkeypatch):
    """タスク生成で自動ポイントが付与され、SAM2 導入時は経路が昇格する。"""
    import app.segmentation.sam2_segmenter as sam2_mod
    from app.ai.mock_analyzer import MockAnalyzer

    monkeypatch.setattr(sam2_mod, "sam2_importable", lambda: True)

    face = _part("face_base", [100, 100, 200, 200], PartType.face, group="Face")
    eye = _part("eye_l", [130, 150, 40, 20], PartType.eye, group="Eye_L")
    plan = PartsPlan(parts=[face, eye])

    tasks = MockAnalyzer().generate_segmentation_tasks(plan).tasks
    by_id = {t.part_id: t for t in tasks}

    face_task = by_id["face_base"]
    assert face_task.method == SegmentationMethod.sam2_box
    assert face_task.positive_points == [[200, 200]]
    assert [150, 160] in face_task.negative_points

    # ユーザーが手動で打った点は上書きされない
    face.segmentation.positive_points = [[111, 111]]
    tasks2 = MockAnalyzer().generate_segmentation_tasks(plan).tasks
    face_task2 = {t.part_id: t for t in tasks2}["face_base"]
    assert face_task2.positive_points == [[111, 111]]


def test_generate_tasks_keeps_manual_box_without_sam2(monkeypatch):
    import app.segmentation.sam2_segmenter as sam2_mod
    from app.ai.mock_analyzer import MockAnalyzer

    monkeypatch.setattr(sam2_mod, "sam2_importable", lambda: False)
    face = _part("face_base", [100, 100, 200, 200], PartType.face)
    plan = PartsPlan(parts=[face])
    tasks = MockAnalyzer().generate_segmentation_tasks(plan).tasks
    assert tasks[0].method == SegmentationMethod.manual_box
