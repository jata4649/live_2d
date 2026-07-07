"""画像アップロード・正規化 API。"""
from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.models.project import Project
from app.services import image_service, project_service

router = APIRouter(prefix="/projects/{project_id}", tags=["image"])


@router.post("/upload-image", response_model=Project)
async def upload_image(project_id: str, image: UploadFile = File(...)) -> Project:
    project_service.load_project(project_id)  # 存在確認
    data = await image.read()
    return image_service.store_and_normalize(project_id, data)


@router.post("/normalize-image", response_model=Project)
def normalize_image(project_id: str) -> Project:
    """保存済み original から正規化をやり直す。"""
    from app.core.paths import ProjectPaths

    project_service.load_project(project_id)
    paths = ProjectPaths(project_id)
    if not paths.original_image.exists():
        raise image_service.InvalidImageError("元画像がありません")
    return image_service.store_and_normalize(
        project_id, paths.original_image.read_bytes()
    )
