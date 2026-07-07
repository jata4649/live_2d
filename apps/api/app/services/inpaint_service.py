"""欠損補完の実行(簡易・最近傍フィル)。

inpaint_tasks.json のタスクごとに:
1. 遮蔽パーツと対象パーツのマスクから隠れ領域マスクを生成・保存
2. 対象レイヤーの隠れ領域を最近傍フィルで補完
3. 対象マスクを補完領域ぶん拡張して保存(レイヤーは再生成せず直接更新)
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.inpaint.nearest_fill import fill_region_nearest, occluded_region
from app.inpaint.task_planner import plan_inpaint_tasks
from app.models.segmentation import InpaintTaskList
from app.services import mask_service
from app.services.project_service import load_parts

logger = get_logger(__name__)

# 対象マスクを何px先まで「隠れている」とみなして補完するか
DEFAULT_EXPAND_PX = 24


class InpaintResult(BaseModel):
    task_id: str
    target_part_id: str
    occluder_part_id: str
    region_px: int
    status: str  # "done" | "skipped"
    reason: str = ""


def run_inpaint(project_id: str, expand_px: int = DEFAULT_EXPAND_PX) -> list[InpaintResult]:
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)

    if paths.inpaint_tasks_json.exists():
        tasks = InpaintTaskList.model_validate_json(
            paths.inpaint_tasks_json.read_text(encoding="utf-8")
        )
    else:
        tasks = plan_inpaint_tasks(plan)

    part_ids = {p.id for p in plan.parts}
    results: list[InpaintResult] = []

    for task in tasks.tasks:
        occluder = task.occluder_part_ids[0] if task.occluder_part_ids else ""
        base = InpaintResult(
            task_id=task.task_id,
            target_part_id=task.target_part_id,
            occluder_part_id=occluder,
            region_px=0,
            status="skipped",
        )
        if task.target_part_id not in part_ids or occluder not in part_ids:
            base.reason = "対象または遮蔽パーツが存在しません"
            results.append(base)
            continue
        try:
            target_mask = mask_service.load_mask(project_id, task.target_part_id)
            occluder_mask = mask_service.load_mask(project_id, occluder)
        except mask_service.MaskError as e:
            base.reason = f"マスク未生成: {e}"
            results.append(base)
            continue
        layer_path = paths.layer_png(task.target_part_id)
        if not layer_path.exists():
            base.reason = "対象レイヤーが未生成です"
            results.append(base)
            continue

        region = occluded_region(target_mask, occluder_mask, expand_px)
        region_px = int((region > 127).sum())
        if region_px == 0:
            base.reason = "隠れ領域がありません(パーツが重なっていません)"
            results.append(base)
            continue

        # 領域マスクを保存(レビュー・再編集用)
        region_path = paths.resolve(
            task.region_mask_path
            or f"masks/inpaint_{task.target_part_id}_under_{occluder}.png"
        )
        region_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(region, "L").save(region_path, format="PNG")

        # レイヤーを補完して上書き
        with Image.open(layer_path) as img:
            layer = np.asarray(img.convert("RGBA")).copy()
        filled = fill_region_nearest(layer, target_mask, region)
        Image.fromarray(filled, "RGBA").save(layer_path, format="PNG")

        # 対象マスクを補完領域ぶん拡張
        new_mask = np.maximum(target_mask, region)
        mask_service.save_mask(project_id, task.target_part_id, new_mask)

        task.status = "done"
        task.method = "nearest_fill"
        base.region_px = region_px
        base.status = "done"
        results.append(base)
        logger.info(
            "補完完了: %s ← %s の下 %dpx", task.target_part_id, occluder, region_px
        )

    paths.inpaint_tasks_json.write_text(
        tasks.model_dump_json(indent=2), encoding="utf-8"
    )
    return results
