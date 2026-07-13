"""全自動仕上げパイプライン API。"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.paths import ProjectPaths
from app.models.jobs import Job, JobKind
from app.services.jobs import start_job
from app.services.pipeline_service import PipelineSummary, run_auto_pipeline

router = APIRouter(prefix="/projects/{project_id}/pipeline", tags=["pipeline"])


@router.post("/auto", response_model=Job, status_code=202)
def auto(project_id: str, background: BackgroundTasks) -> Job:
    """セグメント→整合→補完→モーション修正→品質→自動修正を一括実行する。"""
    return start_job(
        background,
        project_id,
        JobKind.auto_pipeline,
        lambda cb: run_auto_pipeline(project_id, progress_cb=cb),
    )


@router.get("/summary", response_model=PipelineSummary)
def summary(project_id: str) -> PipelineSummary:
    path = ProjectPaths(project_id).json_dir / "pipeline_summary.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="パイプラインはまだ実行されていません",
        )
    return PipelineSummary.model_validate_json(path.read_text(encoding="utf-8"))
