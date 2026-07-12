"""左右対称パーツのマスクミラーリング。

片側(_l / _r)のマスクを仕上げたら、反対側へ左右反転コピーする。
反転軸は両パーツの bbox 中心の中点(なければ画像中心)を使う。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services import layer_service, mask_service
from app.services.project_service import load_parts, load_project, save_parts

logger = get_logger(__name__)


class MirrorResult(BaseModel):
    source_part_id: str
    twin_part_id: str
    mask_path: str
    layer_path: Optional[str] = None
    bbox_updated: bool = False


def twin_part_id(part_id: str) -> Optional[str]:
    """左右対称パーツの相方 ID を返す(なければ None)。

    トークン単位で 'l' / 'r' を入れ替える(最後に出現したもの)。
    例: eye_white_l → eye_white_r / side_hair_l_01 → side_hair_r_01
    """
    tokens = part_id.split("_")
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i] == "l":
            tokens[i] = "r"
            return "_".join(tokens)
        if tokens[i] == "r":
            tokens[i] = "l"
            return "_".join(tokens)
    return None


def mirror_axis(
    src_bbox: Optional[list[int]], twin_bbox: Optional[list[int]], width: int
) -> float:
    """反転軸の x 座標。両 bbox があれば中心の中点、なければ画像中心。"""
    if src_bbox and twin_bbox:
        src_cx = src_bbox[0] + src_bbox[2] / 2
        twin_cx = twin_bbox[0] + twin_bbox[2] / 2
        return (src_cx + twin_cx) / 2
    return width / 2


def mirror_mask_array(mask: np.ndarray, axis: float) -> np.ndarray:
    """マスクを x=axis で左右反転する(画像サイズは不変、範囲外は切り捨て)。"""
    h, w = mask.shape[:2]
    flipped = mask[:, ::-1]  # x → (w-1) - x(軸 (w-1)/2 での反転)
    # 軸 a での反転にするため、水平シフト dx = 2a - (w-1) を適用する
    dx = int(round(2 * axis - (w - 1)))
    out = np.zeros_like(mask)
    if dx >= 0:
        if dx < w:
            out[:, dx:] = flipped[:, : w - dx]
    else:
        out[:, : w + dx] = flipped[:, -dx:]
    return out


def mirror_bbox(bbox: list[int], axis: float, width: int) -> list[int]:
    x, y, w, h = bbox
    new_x = int(round(2 * axis - (x + w)))
    new_x = max(0, min(new_x, width - 1))
    w = min(w, width - new_x)
    return [new_x, y, w, h]


def mirror_to_twin(project_id: str, part_id: str) -> MirrorResult:
    twin_id = twin_part_id(part_id)
    if twin_id is None:
        raise ValueError(
            f"{part_id} は左右対称パーツではありません(_l / _r を含む必要があります)"
        )
    plan = load_parts(project_id)
    parts_by_id = {p.id: p for p in plan.parts}
    if twin_id not in parts_by_id:
        raise ValueError(f"相方パーツが存在しません: {twin_id}")

    project = load_project(project_id)
    width = project.source_image.width
    src = parts_by_id[part_id]
    twin = parts_by_id[twin_id]

    mask = mask_service.load_mask(project_id, part_id)
    axis = mirror_axis(src.segmentation.bbox, twin.segmentation.bbox, width)
    mirrored = mirror_mask_array(mask, axis)
    mask_path = mask_service.save_mask(project_id, twin_id, mirrored)

    # 相方の bbox もミラーで更新(未設定または元 bbox がある場合)
    bbox_updated = False
    if src.segmentation.bbox:
        twin.segmentation.bbox = mirror_bbox(src.segmentation.bbox, axis, width)
        save_parts(project_id, plan)
        bbox_updated = True

    layer_path = None
    try:
        layer_path = layer_service.generate_layer(project_id, twin)
    except Exception as e:  # レイヤー生成失敗はミラー自体の失敗にしない
        logger.warning("ミラー後のレイヤー生成に失敗: %s (%s)", twin_id, e)

    logger.info("ミラーコピー: %s → %s (axis=%.1f)", part_id, twin_id, axis)
    return MirrorResult(
        source_part_id=part_id,
        twin_part_id=twin_id,
        mask_path=mask_path,
        layer_path=layer_path,
        bbox_updated=bbox_updated,
    )
