"""境界帯ガイデッドフィルタによる簡易アルファマッティング。

2値マスクは髪の毛先のような半透明・入り組んだ境界でカクつくため、
マスク境界の狭い帯だけを「元画像をガイドにした guided filter」で
連続アルファ化する。画像のエッジに沿ってアルファがなだらかに変化し、
単純なガウスぼかし(feather)より輪郭への追従が良い。

opencv-contrib(ximgproc)には依存せず、box filter による
標準的な guided filter を自前実装している(He et al. 2010)。
"""
from __future__ import annotations

import cv2
import numpy as np


def guided_filter(
    guide: np.ndarray, src: np.ndarray, radius: int = 4, eps: float = 1e-3
) -> np.ndarray:
    """グレースケール guided filter。

    guide / src ともに float32 の [0, 1]。radius は box 窓の半径。
    eps が小さいほどガイドのエッジを強く保持する。
    """
    ksize = (2 * radius + 1, 2 * radius + 1)
    mean_i = cv2.blur(guide, ksize)
    mean_p = cv2.blur(src, ksize)
    corr_i = cv2.blur(guide * guide, ksize)
    corr_ip = cv2.blur(guide * src, ksize)
    var_i = corr_i - mean_i * mean_i
    cov_ip = corr_ip - mean_i * mean_p
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    mean_a = cv2.blur(a, ksize)
    mean_b = cv2.blur(b, ksize)
    return mean_a * guide + mean_b


def soft_edge_alpha(
    rgba: np.ndarray,
    mask: np.ndarray,
    band_px: int = 3,
    radius: int = 4,
    eps: float = 1e-3,
) -> np.ndarray:
    """マスク境界帯のみ連続アルファ化したマスクを返す。

    - 境界から band_px 内側より深い領域は不透明のまま(下地が痩せない)
    - 境界から band_px 外側より遠い領域は透明のまま(にじみ広がりなし)
    - その間の帯だけ guided filter の出力で置き換える
    """
    binary = (mask > 127).astype(np.uint8)
    if not binary.any() or binary.all():
        return mask

    kernel = np.ones((3, 3), np.uint8)
    inner = cv2.erode(binary, kernel, iterations=band_px)
    outer = cv2.dilate(binary, kernel, iterations=band_px)
    band = (outer == 1) & (inner == 0)
    if not band.any():
        return mask

    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    q = guided_filter(gray, binary.astype(np.float32), radius=radius, eps=eps)
    q = np.clip(q, 0.0, 1.0)

    out = mask.copy()
    out[band] = (q[band] * 255.0 + 0.5).astype(np.uint8)
    out[inner == 1] = 255
    out[outer == 0] = 0
    # 元画像自体が透明な場所は透明のまま(extract_layer でも乗算されるが明示)
    out[rgba[:, :, 3] <= 8] = 0
    return out
