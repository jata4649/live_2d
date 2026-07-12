"""2段階処理(縮小版でセグメンテーション → マスクをフル解像度化)のテスト。"""
from __future__ import annotations

import numpy as np

from app.models.segmentation import SegmentationTask
from app.services.segmentation_service import scale_task, upscale_mask


def _task(**kw) -> SegmentationTask:
    return SegmentationTask(task_id="t", part_id="p", **kw)


def test_scale_task_converts_bbox_and_points():
    task = _task(
        bbox=[100, 200, 300, 400],
        positive_points=[[10, 20]],
        negative_points=[[30, 40]],
    )
    scaled = scale_task(task, 0.5)
    assert scaled.bbox == [50, 100, 150, 200]
    assert scaled.positive_points == [[5, 10]]
    assert scaled.negative_points == [[15, 20]]
    # 元タスクは変更されない
    assert task.bbox == [100, 200, 300, 400]


def test_scale_task_identity_when_scale_1():
    task = _task(bbox=[1, 2, 3, 4])
    assert scale_task(task, 1.0) is task


def test_scale_task_keeps_min_size():
    scaled = scale_task(_task(bbox=[0, 0, 1, 1]), 0.25)
    assert scaled.bbox[2] >= 1 and scaled.bbox[3] >= 1


def test_upscale_mask_to_full_resolution():
    mask = np.zeros((50, 40), np.uint8)  # H=50, W=40
    mask[10:30, 5:25] = 255
    full = upscale_mask(mask, (160, 200))  # (w, h) = 4倍
    assert full.shape == (200, 160)
    assert set(np.unique(full)) <= {0, 255}  # 二値
    assert full[80, 60] == 255   # 元の (20, 15) に対応
    assert full[10, 10] == 0


def test_upscale_mask_noop_when_same_size():
    mask = np.zeros((30, 20), np.uint8)
    assert upscale_mask(mask, (20, 30)) is mask


def test_segmentation_runs_on_working_and_saves_full_mask(client, monkeypatch):
    """working が縮小版になるよう設定し、保存マスクがフル解像度であることを検証。"""
    from app.core.config import settings
    from app.tests.conftest import make_test_character

    monkeypatch.setattr(settings, "working_long_edge", 192)  # 768 → 192 (1/4)

    res = client.post(
        "/api/v1/projects",
        data={"name": "two_stage"},
        files={"image": ("c.png", make_test_character(), "image/png")},
    )
    pid = res.json()["project_id"]

    # working.png が縮小されていることを確認
    res = client.get(f"/api/v1/projects/{pid}/files/source/working.png")
    import io

    from PIL import Image

    working = Image.open(io.BytesIO(res.content))
    assert max(working.size) == 192

    client.post(f"/api/v1/projects/{pid}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{pid}/segmentation/run/face_base")
    assert res.status_code == 200, res.text

    mask = Image.open(io.BytesIO(
        client.get(f"/api/v1/projects/{pid}/masks/face_base").content
    ))
    assert mask.size == (512, 768)  # フル解像度で保存されている

    # マスクが顔の bbox 付近を覆っている(頭部の楕円中心)
    arr = np.asarray(mask.convert("L"))
    assert arr[160, 256] > 127
