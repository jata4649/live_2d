"""プロジェクト管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.models.project import Project, ProjectSummary, UserPreferences
from app.services import image_service, project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project)
async def create_project(
    name: str = Form(...),
    image: UploadFile = File(...),
) -> Project:
    project, _ = project_service.create_project(name)
    data = await image.read()
    return image_service.store_and_normalize(project.project_id, data)


@router.get("", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    return project_service.list_projects()


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    return project_service.load_project(project_id)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    project_service.load_project(project_id)  # 存在確認
    project_service.delete_project(project_id)


@router.put("/{project_id}/preferences", response_model=Project)
def update_preferences(project_id: str, preferences: UserPreferences) -> Project:
    return project_service.update_preferences(project_id, preferences)
