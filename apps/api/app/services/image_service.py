"""画像アップロードと正規化。"""
from __future__ import annotations

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.image_processing.normalize import load_image, normalize
from app.models.project import Project
from app.services.project_service import load_project, save_project

logger = get_logger(__name__)

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class InvalidImageError(Exception):
    pass


def store_and_normalize(project_id: str, data: bytes) -> Project:
    """アップロードされた画像を検証・保存し、正規化まで行う。"""
    if len(data) > settings.max_upload_bytes:
        raise InvalidImageError(
            f"ファイルサイズが上限({settings.max_upload_bytes // (1024*1024)}MB)を超えています"
        )
    try:
        img = load_image(data)
        fmt = (img.format or "").upper()
    except UnidentifiedImageError as e:
        raise InvalidImageError("画像として読み込めませんでした") from e
    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError(
            f"未対応の画像形式です: {fmt or '不明'}(対応: PNG / JPG / WEBP)"
        )

    paths = ProjectPaths(project_id)
    paths.ensure_dirs()

    # 元画像は必ず無劣化 PNG で保存(フォーマット変換のみ、色は触らない)
    img.save(paths.original_image, format="PNG")

    normalized, working, meta = normalize(data, settings.working_long_edge)

    # 背景つき画像(アルファなし)は、rembg が使えれば人物アルファを生成する。
    # アルファが付くと高精度経路(アルファ切り抜き・色分離・人物範囲フィット)が
    # そのまま有効になる。rembg 未導入・失敗時は従来動作。
    if not meta.has_alpha and settings.bg_removal:
        from app.image_processing.bg_removal import (
            bg_removal_available,
            remove_background,
        )
        from app.image_processing.normalize import make_working_copy

        if bg_removal_available()[0]:
            cut = remove_background(np.asarray(normalized.convert("RGBA")))
            if cut is not None:
                normalized = Image.fromarray(cut, "RGBA")
                working = make_working_copy(normalized, settings.working_long_edge)
                meta.has_alpha = True
                logger.info("背景除去でアルファを生成しました: %s", project_id)

    normalized.save(paths.normalized_image, format="PNG")
    working.save(paths.working_image, format="PNG")

    project = load_project(project_id)
    project.source_image.original_path = paths.rel(paths.original_image)
    project.source_image.normalized_path = paths.rel(paths.normalized_image)
    project.source_image.width = meta.width
    project.source_image.height = meta.height
    project.source_image.has_alpha = meta.has_alpha
    project.source_image.color_profile = meta.color_profile
    save_project(project)
    logger.info(
        "画像正規化完了: %s %dx%d alpha=%s",
        project_id, meta.width, meta.height, meta.has_alpha,
    )
    return project


def load_normalized_rgba(project_id: str) -> np.ndarray:
    paths = ProjectPaths(project_id)
    if not paths.normalized_image.exists():
        raise InvalidImageError("正規化済み画像がありません。先に画像をアップロードしてください")
    with Image.open(paths.normalized_image) as img:
        return np.asarray(img.convert("RGBA")).copy()
