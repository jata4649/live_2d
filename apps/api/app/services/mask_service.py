"""マスクの読み書きと後処理(refine)。"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from app.core.paths import ProjectPaths
from app.image_processing import masks as mask_ops
from app.models.segmentation import RefinementParams
from app.services.project_service import load_project


class MaskError(Exception):
    pass


def save_mask(project_id: str, part_id: str, mask: np.ndarray) -> str:
    paths = ProjectPaths(project_id)
    paths.masks_dir.mkdir(parents=True, exist_ok=True)
    out = paths.mask_png(part_id)
    Image.fromarray(mask, "L").save(out, format="PNG")
    return paths.rel(out)


def load_mask(project_id: str, part_id: str) -> np.ndarray:
    paths = ProjectPaths(project_id)
    p = paths.mask_png(part_id)
    if not p.exists():
        raise MaskError(f"マスクが未生成です: {part_id}")
    with Image.open(p) as img:
        return np.asarray(img.convert("L")).copy()


def save_mask_from_png_bytes(project_id: str, part_id: str, data: bytes) -> str:
    """フロントで編集されたマスクPNGの書き戻し。サイズ・形式を検証する。"""
    project = load_project(project_id)
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        raise MaskError("マスクPNGとして読み込めませんでした") from e
    mask = np.asarray(img.convert("L"))
    expected = (project.source_image.height, project.source_image.width)
    if mask.shape != expected:
        raise MaskError(
            f"マスクサイズ {mask.shape[::-1]} が正規化画像 {expected[::-1]} と一致しません"
        )
    return save_mask(project_id, part_id, mask.copy())


def refine_mask(project_id: str, part_id: str, params: RefinementParams) -> str:
    mask = load_mask(project_id, part_id)
    refined = mask_ops.apply_refinement(
        mask,
        remove_noise=params.remove_small_noise,
        holes=params.fill_holes,
        smooth=params.smooth_edges,
        dilate_px=params.dilate_px,
        erode_px=params.erode_px,
        feather_px=params.feather_px,
    )
    return save_mask(project_id, part_id, refined)
