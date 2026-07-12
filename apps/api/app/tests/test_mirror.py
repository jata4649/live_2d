"""左右ミラーリングのテスト。"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.mirror_service import (
    mirror_axis,
    mirror_bbox,
    mirror_mask_array,
    twin_part_id,
)


def test_twin_part_id():
    assert twin_part_id("eye_white_l") == "eye_white_r"
    assert twin_part_id("eye_white_r") == "eye_white_l"
    assert twin_part_id("side_hair_l_01") == "side_hair_r_01"
    assert twin_part_id("earring_r") == "earring_l"
    assert twin_part_id("front_hair_01") is None
    assert twin_part_id("hair_l_and_r") == "hair_l_and_l"  # 最後のトークン優先


def test_mirror_axis():
    # bbox 中心: 100+20=120 と 260+20=280 → 軸は 200
    assert mirror_axis([100, 0, 40, 10], [260, 0, 40, 10], 500) == 200
    assert mirror_axis(None, None, 500) == 250


def test_mirror_mask_array_around_custom_axis():
    mask = np.zeros((10, 100), np.uint8)
    mask[:, 20:30] = 255  # x=20..29
    # 軸 x=40 → ミラーは x=50..60 付近
    out = mirror_mask_array(mask, 40.0)
    assert out[5, 55] == 255
    assert out[5, 25] == 0
    assert out.sum() == mask.sum()  # 画像内に収まっていれば面積保存


def test_mirror_mask_array_clips_out_of_bounds():
    mask = np.zeros((5, 50), np.uint8)
    mask[:, 0:10] = 255
    out = mirror_mask_array(mask, 45.0)  # ミラー先は x=80..90 → 範囲外
    assert out.sum() == 0


def test_mirror_bbox():
    # 軸 200、bbox x=100..140 → ミラーは x=260..300
    assert mirror_bbox([100, 10, 40, 20], 200.0, 500) == [260, 10, 40, 20]


def test_mirror_endpoint_e2e(client, project_id):
    """左目のマスクをミラーして右目のマスク・bbox・レイヤーが生成される。"""
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(
        f"/api/v1/projects/{project_id}/segmentation/run/eye_white_l"
    )
    assert res.status_code == 200, res.text

    res = client.post(f"/api/v1/projects/{project_id}/masks/eye_white_l/mirror")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["twin_part_id"] == "eye_white_r"
    assert body["bbox_updated"] is True
    assert body["layer_path"] == "layers/eye_white_r.png"

    # 相方マスクが取得でき、左右がほぼ対称
    import io

    from PIL import Image

    left = np.asarray(Image.open(io.BytesIO(
        client.get(f"/api/v1/projects/{project_id}/masks/eye_white_l").content
    )).convert("L"))
    right = np.asarray(Image.open(io.BytesIO(
        client.get(f"/api/v1/projects/{project_id}/masks/eye_white_r").content
    )).convert("L"))
    assert right.sum() == pytest.approx(left.sum(), rel=0.05)
    # 左右はキャラクター基準: 左目(_l)は画面向かって右側にあるため、
    # 右目(_r)の重心は左目より小さい x になる
    ys_l, xs_l = np.nonzero(left)
    ys_r, xs_r = np.nonzero(right)
    assert xs_r.mean() < xs_l.mean()


def test_mirror_rejects_non_symmetric_part(client, project_id):
    client.post(f"/api/v1/projects/{project_id}/analyze", json={"analyzer": "mock"})
    res = client.post(f"/api/v1/projects/{project_id}/masks/front_hair_01/mirror")
    assert res.status_code == 400
