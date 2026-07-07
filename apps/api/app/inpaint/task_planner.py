"""needs_inpaint_under フラグから inpaint_tasks.json を生成する。

MVP では実補完は行わず、Phase 3 の Inpainter 実装に渡せる形の
タスクリストを作ることが目的。
"""
from __future__ import annotations

import uuid

from app.models.parts import PartsPlan
from app.models.segmentation import InpaintTask, InpaintTaskList


def plan_inpaint_tasks(parts_plan: PartsPlan) -> InpaintTaskList:
    tasks: list[InpaintTask] = []
    # z_order 昇順 = 背面から。あるパーツの下(背面)にあり bbox が重なるパーツが補完対象。
    ordered = sorted(parts_plan.parts, key=lambda p: p.z_order)
    for i, part in enumerate(ordered):
        if not part.processing.needs_inpaint_under:
            continue
        occluded = [
            p.id
            for p in ordered[:i]
            if _bbox_overlaps(part.segmentation.bbox, p.segmentation.bbox)
        ]
        for target_id in occluded or ["(背面パーツ未特定)"]:
            tasks.append(
                InpaintTask(
                    task_id=str(uuid.uuid4()),
                    target_part_id=target_id,
                    occluder_part_ids=[part.id],
                    region_mask_path=f"masks/inpaint_{target_id}_under_{part.id}.png",
                    reason=part.processing.inpaint_reason
                    or f"{part.name_jp} が動いた際に下のパーツが見えるため",
                    priority=part.quality.priority.value,
                )
            )
    return InpaintTaskList(tasks=tasks)


def _bbox_overlaps(a: list[int] | None, b: list[int] | None) -> bool:
    if not a or not b:
        return False
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
