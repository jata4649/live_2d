"""プロジェクトの作成・読込・保存・削除。"""
from __future__ import annotations

import shutil
import uuid

from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.db.repository import project_repo
from app.models.parts import PartsPlan
from app.models.project import Project, ProjectSummary, UserPreferences, utcnow_iso

logger = get_logger(__name__)


class ProjectNotFoundError(Exception):
    pass


def create_project(name: str) -> tuple[Project, ProjectPaths]:
    project_id = str(uuid.uuid4())
    paths = ProjectPaths(project_id)
    paths.ensure_dirs()
    project = Project(project_id=project_id, name=name)
    save_project(project)
    logger.info("プロジェクト作成: %s (%s)", name, project_id)
    return project, paths


def save_project(project: Project) -> None:
    project.updated_at = utcnow_iso()
    paths = ProjectPaths(project.project_id)
    paths.ensure_dirs()
    paths.project_json.write_text(
        project.model_dump_json(indent=2), encoding="utf-8"
    )
    project_repo.upsert(
        project.project_id, project.name, project.created_at, project.status
    )


def load_project(project_id: str) -> Project:
    paths = ProjectPaths(project_id)
    if not paths.project_json.exists():
        raise ProjectNotFoundError(f"プロジェクトが見つかりません: {project_id}")
    return Project.model_validate_json(paths.project_json.read_text(encoding="utf-8"))


def list_projects() -> list[ProjectSummary]:
    return project_repo.list_summaries()


def delete_project(project_id: str) -> None:
    paths = ProjectPaths(project_id)
    if paths.root.exists():
        shutil.rmtree(paths.root)
    project_repo.delete(project_id)
    logger.info("プロジェクト削除: %s", project_id)


def update_preferences(project_id: str, preferences: UserPreferences) -> Project:
    project = load_project(project_id)
    project.preferences = preferences
    project.status.interview_done = True
    save_project(project)
    return project


def load_parts(project_id: str) -> PartsPlan:
    paths = ProjectPaths(project_id)
    if not paths.parts_json.exists():
        raise ProjectNotFoundError(
            "parts.json がまだ生成されていません。先に解析を実行してください"
        )
    return PartsPlan.model_validate_json(paths.parts_json.read_text(encoding="utf-8"))


def save_parts(project_id: str, plan: PartsPlan) -> None:
    paths = ProjectPaths(project_id)
    paths.ensure_dirs()
    paths.parts_json.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    # updated_at 更新のため project も保存
    project = load_project(project_id)
    save_project(project)
