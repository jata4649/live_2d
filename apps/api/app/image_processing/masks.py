"""マスク操作の純関数群。

マスクは uint8 の 2 次元 ndarray(0=背景, 255=前景)で統一する。
"""
from __future__ import annotations

import cv2
import numpy as np


def _kernel(px: int) -> np.ndarray:
    size = max(1, 2 * px + 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    return cv2.dilate(mask, _kernel(px))


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    if px <= 0:
        return mask
    return cv2.erode(mask, _kernel(px))


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """外周からの flood fill で到達できない領域(=穴)を前景化する。"""
    h, w = mask.shape
    binary = (mask > 127).astype(np.uint8) * 255
    flood = binary.copy()
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, ff_mask, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    return cv2.bitwise_or(binary, holes)


def remove_small_noise(mask: np.ndarray, min_area_ratio: float = 0.0005) -> np.ndarray:
    """面積が画像比 min_area_ratio 未満の連結成分を除去する。"""
    binary = (mask > 127).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    min_area = max(4, int(mask.shape[0] * mask.shape[1] * min_area_ratio))
    out = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            out[labels == i] = 255
    return out


def smooth_edges(mask: np.ndarray, px: int = 2) -> np.ndarray:
    """開閉モルフォロジーで境界の凹凸をならす。二値のまま返す。"""
    if px <= 0:
        return mask
    k = _kernel(px)
    out = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, k)
    return out


def feather(mask: np.ndarray, px: int) -> np.ndarray:
    """境界をぼかす。戻り値はグレースケール(0-255 の連続値)。"""
    if px <= 0:
        return mask
    ksize = 2 * px + 1
    return cv2.GaussianBlur(mask, (ksize, ksize), 0)


def apply_refinement(
    mask: np.ndarray,
    *,
    remove_noise: bool = True,
    holes: bool = True,
    smooth: bool = True,
    dilate_px: int = 0,
    erode_px: int = 0,
    feather_px: int = 0,
) -> np.ndarray:
    out = mask
    if remove_noise:
        out = remove_small_noise(out)
    if holes:
        out = fill_holes(out)
    if smooth:
        out = smooth_edges(out)
    if erode_px > 0:
        out = erode(out, erode_px)
    if dilate_px > 0:
        out = dilate(out, dilate_px)
    if feather_px > 0:
        out = feather(out, feather_px)
    return out
