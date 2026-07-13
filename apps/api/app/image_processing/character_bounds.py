"""キャラクター(人物)の実寸バウンディングボックス検出。

テンプレートのbboxはキャンバス全体比率で置かれるため、余白の多い画像や
キャラクターが中央からずれた画像では大きく外れる。実際の人物範囲を検出し、
テンプレートを人物範囲へ再マッピングするために使う。

検出方法:
1. アルファに変化があれば alpha > 8 を人物とみなす
2. 全面不透明なら四隅の色を背景色と推定し、色差の大きい領域を人物とみなす
最大連結成分のバウンディングボックスを返す(見つからなければ None)。
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


def character_bbox(rgba: np.ndarray) -> Optional[list[int]]:
    """人物のバウンディングボックス [x, y, w, h] を返す。"""
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3]

    if alpha.min() < 250:
        fg = (alpha > 8).astype(np.uint8)
    else:
        fg = _foreground_by_bg_color(rgba)
        if fg is None:
            return None

    # 小ノイズ除去 → 最大連結成分
    kernel = np.ones((3, 3), np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if n <= 1:
        return None
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    area = stats[largest, cv2.CC_STAT_AREA]
    if area < 0.02 * w * h:  # 小さすぎる検出は信用しない
        return None
    x = int(stats[largest, cv2.CC_STAT_LEFT])
    y = int(stats[largest, cv2.CC_STAT_TOP])
    bw = int(stats[largest, cv2.CC_STAT_WIDTH])
    bh = int(stats[largest, cv2.CC_STAT_HEIGHT])
    return [x, y, bw, bh]


def _foreground_by_bg_color(rgba: np.ndarray) -> Optional[np.ndarray]:
    """四隅パッチの中央値を背景色とみなし、色差の大きい画素を前景とする。"""
    h, w = rgba.shape[:2]
    p = max(4, min(h, w) // 50)
    corners = np.concatenate([
        rgba[:p, :p, :3].reshape(-1, 3),
        rgba[:p, -p:, :3].reshape(-1, 3),
        rgba[-p:, :p, :3].reshape(-1, 3),
        rgba[-p:, -p:, :3].reshape(-1, 3),
    ])
    bg = np.median(corners, axis=0)
    # 四隅の色がバラバラなら背景推定は不可能(写真背景など)
    if corners.std(axis=0).max() > 24:
        return None
    diff = np.abs(rgba[:, :, :3].astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    return (diff > 24).astype(np.uint8)


def fit_bbox(
    bbox: list[int],
    template_extent: list[int],
    target_extent: list[int],
) -> list[int]:
    """template_extent 座標系の bbox を target_extent 座標系へアフィン写像する。"""
    tx, ty, tw, th = template_extent
    cx, cy, cw, ch = target_extent
    sx = cw / tw if tw else 1.0
    sy = ch / th if th else 1.0
    x, y, w, h = bbox
    return [
        round(cx + (x - tx) * sx),
        round(cy + (y - ty) * sy),
        max(1, round(w * sx)),
        max(1, round(h * sy)),
    ]
