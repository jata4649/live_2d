"""projects / jobs テーブルへのアクセス。"""
from __future__ import annotations

import json
from typing import Optional

from app.db.database import connect
from app.models.jobs import Job, JobStatus
from app.models.project import ProjectStatus, ProjectSummary, utcnow_iso


class ProjectRepository:
    def upsert(self, project_id: str, name: str, created_at: str, status: ProjectStatus) -> None:
        with connect() as conn:
            conn.execute(
                """INSERT INTO projects(project_id, name, created_at, updated_at, status_json)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(project_id) DO UPDATE SET
                     name=excluded.name, updated_at=excluded.updated_at,
                     status_json=excluded.status_json""",
                (project_id, name, created_at, utcnow_iso(), status.model_dump_json()),
            )

    def list_summaries(self) -> list[ProjectSummary]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [
            ProjectSummary(
                project_id=r["project_id"],
                name=r["name"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                status=ProjectStatus(**json.loads(r["status_json"])),
            )
            for r in rows
        ]

    def delete(self, project_id: str) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM jobs WHERE project_id=?", (project_id,))


class JobRepository:
    def create(self, job: Job) -> None:
        with connect() as conn:
            conn.execute(
                """INSERT INTO jobs(job_id, project_id, kind, status, progress,
                                    message, error, created_at, finished_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    job.job_id, job.project_id, job.kind.value, job.status.value,
                    job.progress, job.message, job.error, job.created_at, job.finished_at,
                ),
            )

    def update(
        self,
        job_id: str,
        *,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> None:
        sets, vals = [], []
        if status is not None:
            sets.append("status=?"); vals.append(status.value)
        if progress is not None:
            sets.append("progress=?"); vals.append(progress)
        if message is not None:
            sets.append("message=?"); vals.append(message)
        if error is not None:
            sets.append("error=?"); vals.append(error)
        if finished_at is not None:
            sets.append("finished_at=?"); vals.append(finished_at)
        if not sets:
            return
        vals.append(job_id)
        with connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", vals)

    def get(self, job_id: str) -> Optional[Job]:
        with connect() as conn:
            r = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if r is None:
            return None
        return Job(
            job_id=r["job_id"], project_id=r["project_id"], kind=r["kind"],
            status=r["status"], progress=r["progress"], message=r["message"] or "",
            error=r["error"], created_at=r["created_at"], finished_at=r["finished_at"],
        )


project_repo = ProjectRepository()
job_repo = JobRepository()
