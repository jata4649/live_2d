"""セグメンテーション実行(単体・一括)。

大画像対策の2段階処理(docs/08 リスクR3):
- セグメンテーション自体は内部処理用の縮小版(working.png)で実行し、
  プロンプト(bbox / points)を縮小座標へ換算、結果マスクをフル解像度へ拡大する
- レイヤー生成・マスク編集・PSD出力は従来どおりフル解像度
- 元画像が作業サイズ以下の場合や ALS_SEGMENT_ON_WORKING=0 の場合は従来どおり
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.image_processing import masks as mask_ops
from app.models.segmentation import (
    SegmentationTask,
    SegmentationTaskList,
    TaskStatus,
)
from app.segmentation.registry import run_task
from app.services import mask_service
from app.services.analysis_service import generate_segmentation_tasks
from app.services.image_service import load_normalized_rgba
from app.services.project_service import load_parts, load_project, save_project

logger = get_logger(__name__)


@dataclass
class SegmentationContext:
    """1回の実行で共有する画像コンテキスト。"""
    image: np.ndarray          # セグメンテーションに使う画像(RGBA)
    scale: float               # image / フル解像度 の比率(<= 1.0)
    full_size: tuple[int, int]  # (width, height) フル解像度


def load_context(project_id: str) -> SegmentationContext:
    paths = ProjectPaths(project_id)
    project = load_project(project_id)
    full_w = project.source_image.width
    full_h = project.source_image.height

    if settings.segment_on_working and paths.working_image.exists():
        with Image.open(paths.working_image) as img:
            arr = np.asarray(img.convert("RGBA")).copy()
        if arr.shape[1] < full_w:
            return SegmentationContext(
                image=arr, scale=arr.shape[1] / full_w, full_size=(full_w, full_h)
            )
    return SegmentationContext(
        image=load_normalized_rgba(project_id), scale=1.0,
        full_size=(full_w, full_h),
    )


def scale_task(task: SegmentationTask, scale: float) -> SegmentationTask:
    """プロンプト座標を縮小画像の座標系へ換算したコピーを返す。"""
    if scale == 1.0:
        return task
    scaled = task.model_copy(deep=True)
    if scaled.bbox:
        x, y, w, h = scaled.bbox
        scaled.bbox = [
            round(x * scale), round(y * scale),
            max(1, round(w * scale)), max(1, round(h * scale)),
        ]
    scaled.positive_points = [
        [round(px * scale), round(py * scale)] for px, py in scaled.positive_points
    ]
    scaled.negative_points = [
        [round(px * scale), round(py * scale)] for px, py in scaled.negative_points
    ]
    return scaled


def upscale_mask(mask: np.ndarray, full_size: tuple[int, int]) -> np.ndarray:
    """マスクをフル解像度へ拡大する(線形補間 → 二値化で境界を滑らかに)。"""
    w, h = full_size
    if mask.shape[:2] == (h, w):
        return mask
    resized = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    return np.where(resized > 127, 255, 0).astype(np.uint8)


def load_tasks(project_id: str) -> SegmentationTaskList:
    paths = ProjectPaths(project_id)
    if not paths.segmentation_tasks_json.exists():
        # parts.json から自動生成
        plan = load_parts(project_id)
        return generate_segmentation_tasks(project_id, plan)
    return SegmentationTaskList.model_validate_json(
        paths.segmentation_tasks_json.read_text(encoding="utf-8")
    )


def save_tasks(project_id: str, tasks: SegmentationTaskList) -> None:
    paths = ProjectPaths(project_id)
    paths.segmentation_tasks_json.write_text(
        tasks.model_dump_json(indent=2), encoding="utf-8"
    )


def run_single(
    project_id: str,
    task: SegmentationTask,
    ctx: Optional[SegmentationContext] = None,
) -> list[str]:
    """1タスク実行。マスクをフル解像度で保存し警告リストを返す。"""
    if ctx is None:
        ctx = load_context(project_id)

    result = run_task(ctx.image, scale_task(task, ctx.scale))
    mask = upscale_mask(result.mask, ctx.full_size)
    mask = mask_ops.apply_refinement(
        mask,
        remove_noise=task.refinement.remove_small_noise,
        holes=task.refinement.fill_holes,
        smooth=task.refinement.smooth_edges,
        dilate_px=task.refinement.dilate_px,
        erode_px=task.refinement.erode_px,
        feather_px=task.refinement.feather_px,
    )
    mask_service.save_mask(project_id, task.part_id, mask)
    logger.info(
        "セグメンテーション完了: %s/%s method=%s conf=%s scale=%.2f",
        project_id, task.part_id, result.method_used, result.confidence, ctx.scale,
    )
    return result.warnings


def run_part(project_id: str, part_id: str) -> list[str]:
    tasks = load_tasks(project_id)
    task = next((t for t in tasks.tasks if t.part_id == part_id), None)
    if task is None:
        raise ValueError(f"セグメンテーションタスクが見つかりません: {part_id}")
    warnings = run_single(project_id, task)
    task.status = TaskStatus.done
    save_tasks(project_id, tasks)
    return warnings


def run_all(
    project_id: str,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> dict[str, list[str]]:
    """全タスク実行。part_id -> warnings の辞書を返す。"""
    tasks = load_tasks(project_id)
    ctx = load_context(project_id)  # 画像は一度だけロードして共有する
    results: dict[str, list[str]] = {}
    total = len(tasks.tasks) or 1
    for i, task in enumerate(tasks.tasks):
        if progress_cb:
            progress_cb(i / total, f"{task.part_id} を処理中")
        task.status = TaskStatus.running
        try:
            results[task.part_id] = run_single(project_id, task, ctx=ctx)
            task.status = TaskStatus.done
        except Exception as e:
            task.status = TaskStatus.failed
            task.error = str(e)
            results[task.part_id] = [f"失敗: {e}"]
            logger.exception("セグメンテーション失敗: %s/%s", project_id, task.part_id)
    save_tasks(project_id, tasks)

    project = load_project(project_id)
    project.status.segmentation_done = True
    save_project(project)
    if progress_cb:
        progress_cb(1.0, "完了")
    return results
