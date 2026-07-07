"""プロジェクト内ファイルの静的配信とジョブ・補完タスク API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import ProjectPaths
from app.db.repository import job_repo
from app.models.jobs import Job
from app.models.segmentation import InpaintTaskList

router = APIRouter(tags=["files"])


@router.api_route(
    "/projects/{project_id}/files/{path:path}", methods=["GET", "HEAD"]
)
def serve_file(project_id: str, path: str) -> FileResponse:
    paths = ProjectPaths(project_id)
    try:
        p = paths.resolve(path)  # パストラバーサルは resolve() が拒否する
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"ファイルがありません: {path}")
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"ジョブがありません: {job_id}")
    return job


@router.post("/projects/{project_id}/inpaint/plan", response_model=InpaintTaskList)
def plan_inpaint(project_id: str) -> InpaintTaskList:
    from app.inpaint.task_planner import plan_inpaint_tasks
    from app.services.project_service import load_parts

    plan = load_parts(project_id)
    tasks = plan_inpaint_tasks(plan)
    paths = ProjectPaths(project_id)
    paths.inpaint_tasks_json.write_text(
        tasks.model_dump_json(indent=2), encoding="utf-8"
    )
    return tasks


@router.get("/projects/{project_id}/inpaint/tasks", response_model=InpaintTaskList)
def get_inpaint_tasks(project_id: str) -> InpaintTaskList:
    paths = ProjectPaths(project_id)
    if not paths.inpaint_tasks_json.exists():
        return InpaintTaskList()
    return InpaintTaskList.model_validate_json(
        paths.inpaint_tasks_json.read_text(encoding="utf-8")
    )
