"""アルファチャンネル操作。"""
from __future__ import annotations

import cv2
import numpy as np


def extract_layer(rgba: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """元画像(RGBA)とマスク(grayscale)からレイヤーRGBAを生成する。

    - キャンバスサイズは元画像と同一(位置ずれなし)
    - パーツ以外は完全透明
    - マスクのグレー値と元画像のアルファを乗算合成
    """
    if rgba.shape[:2] != mask.shape[:2]:
        raise ValueError(
            f"マスクサイズ {mask.shape[:2]} が画像サイズ {rgba.shape[:2]} と一致しません"
        )
    layer = rgba.copy()
    src_alpha = rgba[:, :, 3].astype(np.uint16)
    m = mask.astype(np.uint16)
    layer[:, :, 3] = (src_alpha * m // 255).astype(np.uint8)
    # 完全透明ピクセルの RGB を膨張で埋め、透明フチ(白/黒フチ)を防ぐ
    layer = bleed_rgb_into_transparent(layer)
    return layer


def bleed_rgb_into_transparent(rgba: np.ndarray, iterations: int = 2) -> np.ndarray:
    """透明領域の境界へ隣接する不透明ピクセルの色をにじませる(エッジ対策)。"""
    out = rgba.copy()
    alpha = out[:, :, 3]
    opaque = (alpha > 0).astype(np.uint8)
    if opaque.all() or not opaque.any():
        return out
    rgb = out[:, :, :3]
    for _ in range(iterations):
        kernel = np.ones((3, 3), np.uint8)
        grown = cv2.dilate(opaque, kernel)
        ring = (grown == 1) & (opaque == 0)
        if not ring.any():
            break
        blurred = cv2.blur(rgb * opaque[:, :, None], (3, 3))
        weight = cv2.blur(opaque.astype(np.float32), (3, 3))
        weight[weight == 0] = 1
        filled = (blurred / weight[:, :, None]).astype(np.uint8)
        rgb[ring] = filled[ring]
        opaque = grown
    out[:, :, :3] = rgb
    return out


def detect_edge_artifact(rgba: np.ndarray) -> float:
    """半透明境界ピクセルのうち、極端に明るい/暗い色の比率を返す(フチ検出の簡易指標)。"""
    alpha = rgba[:, :, 3]
    edge = (alpha > 0) & (alpha < 255)
    n_edge = int(edge.sum())
    if n_edge == 0:
        return 0.0
    rgb = rgba[:, :, :3][edge].astype(np.int32)
    lum = rgb.mean(axis=1)
    artifact = ((lum > 250) | (lum < 5)).sum()
    return float(artifact) / n_edge
