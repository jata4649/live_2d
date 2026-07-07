"""元画像と合成プレビューの差分。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DiffStats:
    diff_pixel_count: int
    diff_pixel_ratio: float
    max_channel_diff: int


def difference(original: np.ndarray, composite: np.ndarray, threshold: int = 8) -> tuple[np.ndarray, DiffStats]:
    """差分ヒートマップ(RGBA)と統計を返す。

    アルファを含む4chの絶対差の最大値が threshold を超えるピクセルを差分とみなす。
    """
    if original.shape != composite.shape:
        raise ValueError("元画像と合成画像のサイズが一致しません")
    diff = np.abs(original.astype(np.int16) - composite.astype(np.int16)).max(axis=2)
    hot = diff > threshold
    heat = np.zeros_like(original)
    heat[:, :, 0] = 255  # 赤
    heat[:, :, 3] = np.where(hot, np.clip(diff * 2, 60, 255), 0).astype(np.uint8)
    stats = DiffStats(
        diff_pixel_count=int(hot.sum()),
        diff_pixel_ratio=float(hot.mean()),
        max_channel_diff=int(diff.max()),
    )
    return heat, stats
