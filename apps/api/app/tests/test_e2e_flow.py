"""API 一気通貫テスト: アップロード → 解析 → セグメンテーション →
レイヤー生成 → プレビュー → 品質チェック → PSD/ZIP/リギング設計書出力。
"""
from __future__ import annotations

import io
import time

from PIL import Image


def test_full_pipeline(client, project_id):
    # 1. プロジェクトが正規化済みで作成されている
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 200
    project = res.json()
    assert project["source_image"]["width"] == 512
    assert project["source_image"]["has_alpha"] is True

    # 2. ヒアリング回答の保存
    res = client.put(
        f"/api/v1/projects/{project_id}/preferences",
        json={"quality_level": "standard", "mouth_type": "open_close",
              "arm_movement": False},
    )
    assert res.status_code == 200
    assert res.json()["status"]["interview_done"] is True

    # 3. 質問生成
    res = client.post(f"/api/v1/projects/{project_id}/generate-questions")
    assert res.status_code == 200
    assert len(res.json()["questions"]) >= 5

    # 4. AI解析(Mock)
    res = client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    assert res.status_code == 200, res.text
    parts = res.json()["parts"]
    assert len(parts) >= 15
    ids = {p["id"] for p in parts}
    # 標準テンプレートの必須パーツ
    assert {"face_base", "front_hair_01", "back_hair", "mouth_line"} <= ids
    # open_close 指定なので歯・舌は含まれない
    assert "teeth" not in ids and "tongue" not in ids
    # 腕は動かさないので腕パーツなし
    assert "hand_l" not in ids

    # 5. パーツ編集(PUT)
    res = client.get(f"/api/v1/projects/{project_id}/parts")
    plan = res.json()
    plan["parts"][0]["name_jp"] = "編集済み"
    res = client.put(f"/api/v1/projects/{project_id}/parts", json=plan)
    assert res.status_code == 200
    assert res.json()["parts"][0]["name_jp"] == "編集済み"

    # 6. セグメンテーション一括実行(ジョブ)
    res = client.post(f"/api/v1/projects/{project_id}/segmentation/run")
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    job = _wait_job(client, job_id)
    assert job["status"] == "done", job

    # 7. マスク取得と書き戻し
    res = client.get(f"/api/v1/projects/{project_id}/masks/face_base")
    assert res.status_code == 200
    mask_img = Image.open(io.BytesIO(res.content))
    assert mask_img.size == (512, 768)
    buf = io.BytesIO()
    mask_img.save(buf, format="PNG")
    res = client.put(
        f"/api/v1/projects/{project_id}/masks/face_base", content=buf.getvalue()
    )
    assert res.status_code == 200

    # 8. マスク refine
    res = client.post(
        f"/api/v1/projects/{project_id}/masks/face_base/refine",
        json={"dilate_px": 2, "fill_holes": True},
    )
    assert res.status_code == 200

    # 9. レイヤー生成(ジョブ)
    res = client.post(f"/api/v1/projects/{project_id}/layers/generate")
    assert res.status_code == 202
    job = _wait_job(client, res.json()["job_id"])
    assert job["status"] == "done", job
    res = client.get(f"/api/v1/projects/{project_id}/layers/face_base")
    assert res.status_code == 200
    layer_img = Image.open(io.BytesIO(res.content))
    assert layer_img.size == (512, 768)  # 元画像と同キャンバス
    assert layer_img.mode == "RGBA"

    # 10. 合成プレビュー
    res = client.post(f"/api/v1/projects/{project_id}/preview/composite")
    assert res.status_code == 200
    preview = res.json()
    assert preview["layers_used"] > 0

    # 11. 補完タスク計画
    res = client.post(f"/api/v1/projects/{project_id}/inpaint/plan")
    assert res.status_code == 200
    assert len(res.json()["tasks"]) > 0  # needs_inpaint_under のパーツがあるため

    # 12. 品質チェック
    res = client.post(f"/api/v1/projects/{project_id}/quality/check")
    assert res.status_code == 200
    report = res.json()
    assert 0 <= report["overall_score"] <= 100

    # 13. PSD 出力(品質スコアに関わらず force で出す)
    res = client.post(
        f"/api/v1/projects/{project_id}/export/psd", json={"force": True}
    )
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["ok"] is True
    # PSD 直接生成が成功していること(フォールバックでないこと)
    assert result["exporter"] == "psd_tools", result

    # 14. layers.zip 出力
    res = client.post(
        f"/api/v1/projects/{project_id}/export/layers-zip", json={"force": True}
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # 15. リギング設計書
    res = client.post(f"/api/v1/projects/{project_id}/export/rigging-plan")
    assert res.status_code == 200
    res = client.get(
        f"/api/v1/projects/{project_id}/files/docs/rigging_plan.md"
    )
    assert res.status_code == 200
    assert "リギング設計書" in res.text

    # 16. PSD を psd-tools で再検証
    res = client.get(f"/api/v1/projects/{project_id}/export/files/live2d_import.psd")
    assert res.status_code == 200
    from psd_tools import PSDImage

    psd = PSDImage.open(io.BytesIO(res.content))
    assert (psd.width, psd.height) == (512, 768)
    layer_names = [l.name for l in psd.descendants() if not l.is_group()]
    assert len(layer_names) == len(set(layer_names))  # 重複なし


def test_project_list_and_delete(client, project_id):
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert any(p["project_id"] == project_id for p in res.json())

    res = client.delete(f"/api/v1/projects/{project_id}")
    assert res.status_code == 204
    res = client.get(f"/api/v1/projects/{project_id}")
    assert res.status_code == 404
    assert res.json()["code"] == "PROJECT_NOT_FOUND"


def test_invalid_image_rejected(client):
    res = client.post(
        "/api/v1/projects",
        data={"name": "bad"},
        files={"image": ("bad.txt", b"not an image", "text/plain")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_IMAGE"


def test_mask_size_mismatch_rejected(client, project_id):
    import io as _io

    from PIL import Image as _Image

    bad = _Image.new("L", (10, 10))
    buf = _io.BytesIO()
    bad.save(buf, format="PNG")
    res = client.put(
        f"/api/v1/projects/{project_id}/masks/face_base", content=buf.getvalue()
    )
    assert res.status_code == 422
    assert res.json()["code"] == "MASK_ERROR"


def test_path_traversal_blocked(client, project_id):
    res = client.get(f"/api/v1/projects/{project_id}/files/../../etc/passwd")
    assert res.status_code in (400, 404)


def _wait_job(client, job_id: str, timeout: float = 60.0) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/api/v1/jobs/{job_id}")
        assert res.status_code == 200
        job = res.json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise TimeoutError(f"ジョブがタイムアウトしました: {job_id}")
