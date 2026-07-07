"""隠れ領域の簡易補完(最近傍フィル)。

対象パーツの可視ピクセルから最も近い色を隠れ領域へ引き伸ばす方式。
アニメ塗りの平坦な領域(額・白目・首元など)では実用的な品質になり、
外部モデル不要・決定的でテスト可能。将来の Inpainting API 実装は
同じインターフェース(Inpainter)で差し替える。
"""
from __future__ import annotations

import cv2
import numpy as np


def fill_region_nearest(
    rgba: np.ndarray,
    source_mask: np.ndarray,
    region: np.ndarray,
    smooth_px: int = 2,
) -> np.ndarray:
    """region の各ピクセルを、source_mask 内の最近傍ピクセルの色で埋める。

    - rgba: 対象パーツのレイヤー (H, W, 4)
    - source_mask: 色の供給元(対象パーツの可視領域、0/255)
    - region: 補完する領域(0/255)。source_mask と重なる部分は無視される
    - 戻り値: region が塗られ alpha=255 になった新しいレイヤー
    """
    out = rgba.copy()
    src = source_mask > 127
    fill = (region > 127) & ~src
    if not fill.any():
        return out
    if not src.any():
        return out  # 供給元が無ければ何もしない

    # distanceTransformWithLabels: 値0のピクセル(=供給元)への最近傍ラベル
    inv = np.where(src, 0, 255).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    # ラベルは供給元ピクセルの行優先順に 1..N が振られる
    src_coords = np.argwhere(inv == 0)
    nearest = src_coords[labels[fill] - 1]  # (M, 2) = 最近傍の (y, x)

    out[fill, :3] = rgba[nearest[:, 0], nearest[:, 1], :3]
    out[fill, 3] = 255

    if smooth_px > 0:
        # 補完領域のみ軽くぼかして継ぎ目を目立たなくする
        ksize = 2 * smooth_px + 1
        blurred = cv2.GaussianBlur(out[:, :, :3], (ksize, ksize), 0)
        edge = cv2.dilate(fill.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        blend = edge & ((src) | fill)
        out[blend, :3] = blurred[blend]
    return out


def occluded_region(
    target_mask: np.ndarray,
    occluder_mask: np.ndarray,
    expand_px: int,
) -> np.ndarray:
    """対象パーツが遮蔽パーツに隠されていると推定される領域を返す。

    対象マスクを expand_px 膨張した範囲のうち、遮蔽マスクに覆われ、
    かつ対象の可視領域ではない部分。
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * expand_px + 1, 2 * expand_px + 1)
    )
    expanded = cv2.dilate(target_mask, kernel)
    region = cv2.bitwise_and(expanded, occluder_mask)
    region = cv2.bitwise_and(region, cv2.bitwise_not(target_mask))
    return region
