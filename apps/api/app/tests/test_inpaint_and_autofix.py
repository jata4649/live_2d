"""欠損補完(最近傍フィル)と品質自動修正のテスト。"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.inpaint.nearest_fill import fill_region_nearest, occluded_region


# ---------------------------------------------------------------- 純関数

def test_occluded_region_between_face_and_hair():
    """顔マスクの上に髪マスクが重なる場合、境界付近の隠れ領域が得られる。"""
    face = np.zeros((100, 100), np.uint8)
    face[40:90, 20:80] = 255      # 顔(下半分)
    hair = np.zeros((100, 100), np.uint8)
    hair[10:50, 10:90] = 255      # 髪(上半分、顔の上部を覆う)

    region = occluded_region(face, hair, expand_px=15)

    assert (region > 0).any()
    # 隠れ領域は顔の可視領域とは重ならない
    assert not ((region > 0) & (face > 0)).any()
    # 隠れ領域は髪の内側にある
    assert ((region > 0) <= (hair > 0)).all()
    # 顔の上端より上(額側)に広がっている
    ys = np.argwhere(region > 0)[:, 0]
    assert ys.min() < 40


def test_fill_region_nearest_extends_color():
    """補完領域は最近傍の可視ピクセルの色で塗られ、alpha=255 になる。"""
    rgba = np.zeros((60, 60, 4), np.uint8)
    src_mask = np.zeros((60, 60), np.uint8)
    # 供給元: 下半分が肌色
    rgba[30:60, :, :] = [255, 220, 190, 255]
    src_mask[30:60, :] = 255
    # 補完領域: そのすぐ上の帯
    region = np.zeros((60, 60), np.uint8)
    region[20:30, :] = 255

    out = fill_region_nearest(rgba, src_mask, region, smooth_px=0)

    assert (out[22, 30, :3] == [255, 220, 190]).all()
    assert out[22, 30, 3] == 255
    # 領域外は変化しない
    assert out[5, 5, 3] == 0


def test_fill_region_nearest_no_source_is_noop():
    rgba = np.zeros((20, 20, 4), np.uint8)
    region = np.full((20, 20), 255, np.uint8)
    out = fill_region_nearest(rgba, np.zeros((20, 20), np.uint8), region)
    assert (out == rgba).all()


# ---------------------------------------------------------------- E2E(API)

@pytest.fixture
def analyzed_project(client, project_id):
    """解析→マスク生成→レイヤー生成まで済ませたプロジェクト。"""
    client.put(
        f"/api/v1/projects/{project_id}/preferences",
        json={"quality_level": "standard", "mouth_type": "open_close"},
    )
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    import time

    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run")
    job_id = res.json()["job_id"]
    for _ in range(300):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    res = client.post(f"/api/v1/projects/{project_id}/layers/generate")
    job_id = res.json()["job_id"]
    for _ in range(300):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.2)
    return project_id


def test_inpaint_run_fills_hidden_regions(client, analyzed_project):
    pid = analyzed_project
    # 計画 → 実行
    res = client.post(f"/api/v1/projects/{pid}/inpaint/plan")
    assert res.status_code == 200
    assert len(res.json()["tasks"]) > 0

    res = client.post(f"/api/v1/projects/{pid}/inpaint/run")
    assert res.status_code == 200
    results = res.json()["results"]
    done = [r for r in results if r["status"] == "done"]
    assert len(done) > 0, results
    assert all(r["region_px"] > 0 for r in done)

    # 領域マスクが保存されている
    first = done[0]
    res = client.get(
        f"/api/v1/projects/{pid}/files/masks/"
        f"inpaint_{first['target_part_id']}_under_{first['occluder_part_id']}.png"
    )
    assert res.status_code == 200

    # 対象レイヤーの補完領域が不透明になっている
    import io

    layer = Image.open(io.BytesIO(
        client.get(f"/api/v1/projects/{pid}/layers/{first['target_part_id']}").content
    )).convert("RGBA")
    region = Image.open(io.BytesIO(res.content)).convert("L")
    layer_a = np.asarray(layer)[:, :, 3]
    region_a = np.asarray(region)
    covered = layer_a[region_a > 127]
    assert covered.size > 0 and (covered == 255).mean() > 0.9


def test_quality_autofix_applies_fixes(client, analyzed_project):
    pid = analyzed_project
    # 意図的に問題を作る: 補完必須パーツの塗り足しを 0 に、目を後ろ髪より背面に
    plan = client.get(f"/api/v1/projects/{pid}/parts").json()
    for p in plan["parts"]:
        if p["processing"]["needs_inpaint_under"]:
            p["processing"]["overlap_bleed_px"] = 0
        if p["id"] == "iris_l":
            p["z_order"] = 5  # back_hair(10) より背面
    client.put(f"/api/v1/projects/{pid}/parts", json=plan)

    report = client.post(f"/api/v1/projects/{pid}/quality/check").json()
    codes = {i["code"] for i in report["issues"]}
    assert "INSUFFICIENT_BLEED" in codes
    assert "Z_ORDER_ANOMALY" in codes

    res = client.post(f"/api/v1/projects/{pid}/quality/autofix")
    assert res.status_code == 200
    body = res.json()
    assert len(body["applied"]) > 0
    new_codes = {i["code"] for i in body["report"]["issues"]}
    assert "INSUFFICIENT_BLEED" not in new_codes
    assert "Z_ORDER_ANOMALY" not in new_codes
    # スコアが悪化していない
    assert body["report"]["overall_score"] >= report["overall_score"]
