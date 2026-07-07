"""セグメンテーション・マスク API。"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from pydantic import BaseModel

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import Response

from app.models.jobs import Job, JobKind
from app.models.segmentation import RefinementParams, SegmentationTaskList
from app.services import mask_service, project_service, segmentation_service
from app.services.jobs import start_job

router = APIRouter(prefix="/projects/{project_id}", tags=["segmentation"])


@router.post("/segmentation/tasks", response_model=SegmentationTaskList)
def generate_tasks(project_id: str) -> SegmentationTaskList:
    plan = project_service.load_parts(project_id)
    from app.services.analysis_service import generate_segmentation_tasks

    return generate_segmentation_tasks(project_id, plan)


@router.post("/segmentation/run", response_model=Job, status_code=202)
def run_all(project_id: str, background: BackgroundTasks) -> Job:
    project_service.load_parts(project_id)  # 存在確認(未解析なら404相当)
    return start_job(
        background,
        project_id,
        JobKind.segmentation_run,
        lambda cb: segmentation_service.run_all(project_id, progress_cb=cb),
    )


class RunPartResponse(BaseModel):
    part_id: str
    mask_path: str
    warnings: list[str]


@router.post("/segmentation/run/{part_id}", response_model=RunPartResponse)
def run_part(project_id: str, part_id: str) -> RunPartResponse:
    warnings = segmentation_service.run_part(project_id, part_id)
    return RunPartResponse(
        part_id=part_id,
        mask_path=f"masks/{part_id}_mask.png",
        warnings=warnings,
    )


@router.get("/masks/{part_id}")
def get_mask(project_id: str, part_id: str) -> Response:
    mask = mask_service.load_mask(project_id, part_id)
    buf = io.BytesIO()
    Image.fromarray(mask, "L").save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.put("/masks/{part_id}")
async def put_mask(project_id: str, part_id: str, request: Request) -> dict:
    data = await request.body()
    rel = mask_service.save_mask_from_png_bytes(project_id, part_id, data)
    return {"mask_path": rel}


@router.post("/masks/{part_id}/refine")
def refine_mask(project_id: str, part_id: str, params: RefinementParams) -> dict:
    rel = mask_service.refine_mask(project_id, part_id, params)
    return {"mask_path": rel}
