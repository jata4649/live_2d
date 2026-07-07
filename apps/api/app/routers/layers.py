"""レイヤー生成・プレビュー API。"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from app.core.paths import ProjectPaths
from app.models.jobs import Job, JobKind
from app.services import layer_service, preview_service, project_service
from app.services.jobs import start_job
from app.services.mask_service import MaskError
from app.services.preview_service import PreviewResult

router = APIRouter(prefix="/projects/{project_id}", tags=["layers"])


@router.post("/layers/generate", response_model=Job, status_code=202)
def generate_all(project_id: str, background: BackgroundTasks) -> Job:
    project_service.load_parts(project_id)
    return start_job(
        background,
        project_id,
        JobKind.layer_generate,
        lambda cb: layer_service.generate_all_layers(project_id, progress_cb=cb),
    )


@router.post("/layers/generate/{part_id}")
def generate_one(project_id: str, part_id: str) -> dict:
    plan = project_service.load_parts(project_id)
    part = next((p for p in plan.parts if p.id == part_id), None)
    if part is None:
        raise MaskError(f"パーツが見つかりません: {part_id}")
    rel = layer_service.generate_layer(project_id, part)
    return {"layer_path": rel}


@router.get("/layers/{part_id}")
def get_layer(project_id: str, part_id: str) -> FileResponse:
    paths = ProjectPaths(project_id)
    p = paths.layer_png(part_id)
    if not p.exists():
        raise MaskError(f"レイヤーが未生成です: {part_id}")
    return FileResponse(p, media_type="image/png")


@router.post("/preview/composite", response_model=PreviewResult)
def composite(project_id: str) -> PreviewResult:
    return preview_service.generate_previews(project_id)
