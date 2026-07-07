"""画像処理純関数のテスト。"""
from __future__ import annotations

import numpy as np

from app.image_processing import masks as mask_ops
from app.image_processing.alpha import extract_layer
from app.image_processing.composite import composite_layers
from app.image_processing.difference import difference


def _square_mask(size=100, x0=30, x1=70) -> np.ndarray:
    m = np.zeros((size, size), np.uint8)
    m[x0:x1, x0:x1] = 255
    return m


def test_dilate_grows_mask():
    m = _square_mask()
    grown = mask_ops.dilate(m, 5)
    assert grown.sum() > m.sum()
    # 元領域は保持される
    assert (grown[m > 0] == 255).all()


def test_erode_shrinks_mask():
    m = _square_mask()
    shrunk = mask_ops.erode(m, 5)
    assert 0 < shrunk.sum() < m.sum()


def test_fill_holes():
    m = _square_mask()
    m[45:55, 45:55] = 0  # 穴
    filled = mask_ops.fill_holes(m)
    assert (filled[45:55, 45:55] == 255).all()


def test_remove_small_noise():
    m = _square_mask()
    m[5, 5] = 255  # 1px ノイズ
    cleaned = mask_ops.remove_small_noise(m)
    assert cleaned[5, 5] == 0
    assert (cleaned[40:60, 40:60] == 255).all()


def test_extract_layer_preserves_canvas_and_position():
    rgba = np.zeros((100, 100, 4), np.uint8)
    rgba[:, :, 0] = 200
    rgba[:, :, 3] = 255
    mask = _square_mask()
    layer = extract_layer(rgba, mask)
    assert layer.shape == rgba.shape  # キャンバスサイズ不変
    assert layer[50, 50, 3] == 255    # マスク内は不透明
    assert layer[10, 10, 3] == 0      # マスク外は透明
    assert layer[50, 50, 0] == 200    # 色は保持


def test_extract_layer_rejects_size_mismatch():
    rgba = np.zeros((100, 100, 4), np.uint8)
    mask = np.zeros((50, 50), np.uint8)
    try:
        extract_layer(rgba, mask)
        assert False, "サイズ不一致で例外が出るべき"
    except ValueError:
        pass


def test_composite_and_difference_roundtrip():
    """マスクが全域をカバーすれば合成結果は元画像と一致する。"""
    rgba = np.zeros((80, 80, 4), np.uint8)
    rgba[:, :, 1] = 150
    rgba[:40, :, 3] = 255
    rgba[40:, :, 3] = 255

    top_mask = np.zeros((80, 80), np.uint8)
    top_mask[:40, :] = 255
    bottom_mask = np.zeros((80, 80), np.uint8)
    bottom_mask[40:, :] = 255

    layers = [extract_layer(rgba, bottom_mask), extract_layer(rgba, top_mask)]
    comp = composite_layers(layers, (80, 80))
    _, stats = difference(rgba, comp)
    assert stats.diff_pixel_ratio == 0.0
