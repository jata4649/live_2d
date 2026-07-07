"""AI解析・パーツ編集 API。"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter

from app.models.parts import PartsPlan
from app.models.segmentation import QuestionList
from app.services import analysis_service, project_service

router = APIRouter(prefix="/projects/{project_id}", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    analyzer: str = "mock"


@router.post("/analyze", response_model=PartsPlan)
def analyze(project_id: str, req: AnalyzeRequest | None = None) -> PartsPlan:
    name = req.analyzer if req else "mock"
    return analysis_service.analyze(project_id, name)


@router.get("/parts", response_model=PartsPlan)
def get_parts(project_id: str) -> PartsPlan:
    return project_service.load_parts(project_id)


@router.put("/parts", response_model=PartsPlan)
def put_parts(project_id: str, plan: PartsPlan) -> PartsPlan:
    project_service.load_project(project_id)  # 存在確認
    project_service.save_parts(project_id, plan)
    return plan


@router.post("/generate-questions", response_model=QuestionList)
def generate_questions(project_id: str) -> QuestionList:
    return analysis_service.generate_questions(project_id)
