"""マスクからレイヤーPNG(RGBA・元画像と同キャンバス)を生成する。"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PIL import Image

from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.image_processing import masks as mask_ops
from app.image_processing.alpha import extract_layer
from app.models.parts import Part
from app.services import mask_service
from app.services.image_service import load_normalized_rgba
from app.services.project_service import load_parts

logger = get_logger(__name__)


def generate_layer(project_id: str, part: Part, image: np.ndarray | None = None) -> str:
    """1パーツのレイヤーPNGを生成し、相対パスを返す。

    塗り足し(overlap_bleed_px)はマスク膨張として、
    境界ぼかし(edge_feather_px)はフェザーとして適用する。
    """
    if image is None:
        image = load_normalized_rgba(project_id)
    mask = mask_service.load_mask(project_id, part.id)

    if part.processing.overlap_bleed_px > 0:
        mask = mask_ops.dilate(mask, part.processing.overlap_bleed_px)
    if part.processing.edge_feather_px > 0:
        mask = mask_ops.feather(mask, part.processing.edge_feather_px)

    layer = extract_layer(image, mask)
    paths = ProjectPaths(project_id)
    paths.layers_dir.mkdir(parents=True, exist_ok=True)
    out = paths.layer_png(part.id)
    Image.fromarray(layer, "RGBA").save(out, format="PNG")
    return paths.rel(out)


def generate_all_layers(
    project_id: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> dict[str, str]:
    """マスクが存在する全パーツのレイヤーを生成する。part_id -> 相対パス。"""
    plan = load_parts(project_id)
    image = load_normalized_rgba(project_id)
    results: dict[str, str] = {}
    total = len(plan.parts) or 1
    for i, part in enumerate(plan.parts):
        if progress_cb:
            progress_cb(i / total, f"{part.id} のレイヤーを生成中")
        try:
            results[part.id] = generate_layer(project_id, part, image)
        except mask_service.MaskError:
            logger.info("マスク未生成のためスキップ: %s/%s", project_id, part.id)
    if progress_cb:
        progress_cb(1.0, "完了")
    return results
