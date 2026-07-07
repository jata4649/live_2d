"""セグメンテーション実行(単体・一括)。"""
from __future__ import annotations

from typing import Callable, Optional

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


def run_single(project_id: str, task: SegmentationTask) -> list[str]:
    """1タスク実行。マスクを保存し警告リストを返す。"""
    image = load_normalized_rgba(project_id)
    result = run_task(image, task)
    mask = mask_ops.apply_refinement(
        result.mask,
        remove_noise=task.refinement.remove_small_noise,
        holes=task.refinement.fill_holes,
        smooth=task.refinement.smooth_edges,
        dilate_px=task.refinement.dilate_px,
        erode_px=task.refinement.erode_px,
        feather_px=task.refinement.feather_px,
    )
    mask_service.save_mask(project_id, task.part_id, mask)
    logger.info(
        "セグメンテーション完了: %s/%s method=%s conf=%s",
        project_id, task.part_id, result.method_used, result.confidence,
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
    results: dict[str, list[str]] = {}
    total = len(tasks.tasks) or 1
    for i, task in enumerate(tasks.tasks):
        if progress_cb:
            progress_cb(i / total, f"{task.part_id} を処理中")
        task.status = TaskStatus.running
        try:
            results[task.part_id] = run_single(project_id, task)
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
