"""エクスポート API。"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.paths import ProjectPaths
from app.models.export import ExportResult
from app.services import export_service
from app.services.rigging_plan_service import generate_rigging_plan
from app.services.segmentation_service import load_tasks  # noqa: F401 (再エクスポート用)

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


class ExportRequest(BaseModel):
    force: bool = False


@router.post("/psd", response_model=ExportResult)
def export_psd(project_id: str, req: ExportRequest | None = None) -> ExportResult:
    return export_service.export_psd(project_id, force=req.force if req else False)


@router.post("/ora", response_model=ExportResult)
def export_ora(project_id: str, req: ExportRequest | None = None) -> ExportResult:
    return export_service.export_ora(project_id, force=req.force if req else False)


@router.post("/layers-zip", response_model=ExportResult)
def export_layers_zip(project_id: str, req: ExportRequest | None = None) -> ExportResult:
    return export_service.export_layers_zip(
        project_id, force=req.force if req else False
    )


@router.post("/rigging-plan")
def export_rigging_plan(project_id: str) -> dict:
    rel = generate_rigging_plan(project_id)
    return {"rigging_plan_path": rel}


@router.get("/files/{filename}")
def download(project_id: str, filename: str) -> FileResponse:
    paths = ProjectPaths(project_id)
    p = paths.resolve(f"exports/{filename}")
    if not p.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"ファイルがありません: {filename}")
    return FileResponse(p, filename=filename)
