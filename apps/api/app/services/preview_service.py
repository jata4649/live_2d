"""合成プレビューと差分プレビューの生成。"""
from __future__ import annotations

import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.core.paths import ProjectPaths
from app.image_processing.composite import composite_layers
from app.image_processing.difference import difference
from app.services.image_service import load_normalized_rgba
from app.services.project_service import load_parts


class PreviewResult(BaseModel):
    composite_path: str
    difference_path: str
    diff_pixel_count: int
    diff_pixel_ratio: float
    max_channel_diff: int
    layers_used: int


def generate_previews(project_id: str) -> PreviewResult:
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)
    original = load_normalized_rgba(project_id)
    h, w = original.shape[:2]

    # z_order 昇順(背面から)で、レイヤーPNGが存在する可視パーツを合成
    layers: list[np.ndarray] = []
    used = 0
    for part in sorted(plan.parts, key=lambda p: p.z_order):
        if not part.visible:
            continue
        layer_path = paths.layer_png(part.id)
        if not layer_path.exists():
            continue
        with Image.open(layer_path) as img:
            layers.append(np.asarray(img.convert("RGBA")))
        used += 1

    composite = composite_layers(layers, (w, h))
    paths.previews_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(composite, "RGBA").save(paths.composite_preview, format="PNG")

    heat, stats = difference(original, composite)
    Image.fromarray(heat, "RGBA").save(paths.difference_preview, format="PNG")

    return PreviewResult(
        composite_path=paths.rel(paths.composite_preview),
        difference_path=paths.rel(paths.difference_preview),
        diff_pixel_count=stats.diff_pixel_count,
        diff_pixel_ratio=stats.diff_pixel_ratio,
        max_channel_diff=stats.max_channel_diff,
        layers_used=used,
    )
