"""品質チェック API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.quality import QualityReport
from app.services import quality_service

router = APIRouter(prefix="/projects/{project_id}/quality", tags=["quality"])


@router.post("/check", response_model=QualityReport)
def check(project_id: str) -> QualityReport:
    return quality_service.run_quality_check(project_id)


@router.get("/report", response_model=QualityReport)
def report(project_id: str) -> QualityReport:
    result = quality_service.load_report(project_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="品質レポートがまだありません。品質チェックを実行してください",
        )
    return result
