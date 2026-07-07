"""非同期ジョブ実行ヘルパー。

FastAPI BackgroundTasks 上で処理を実行し、進捗を jobs テーブルへ書き込む。
フロントは GET /jobs/{job_id} でポーリングする。
"""
from __future__ import annotations

import uuid
from typing import Callable

from fastapi import BackgroundTasks

from app.core.logging import get_logger
from app.db.repository import job_repo
from app.models.jobs import Job, JobKind, JobStatus
from app.models.project import utcnow_iso

logger = get_logger(__name__)

# work(progress_cb) -> Any。progress_cb(ratio, message) で進捗報告。
WorkFn = Callable[[Callable[[float, str], None]], object]


def start_job(
    background: BackgroundTasks,
    project_id: str,
    kind: JobKind,
    work: WorkFn,
) -> Job:
    job = Job(job_id=str(uuid.uuid4()), project_id=project_id, kind=kind)
    job_repo.create(job)

    def _run() -> None:
        job_repo.update(job.job_id, status=JobStatus.running)

        def progress_cb(ratio: float, message: str) -> None:
            job_repo.update(job.job_id, progress=ratio, message=message)

        try:
            work(progress_cb)
            job_repo.update(
                job.job_id,
                status=JobStatus.done,
                progress=1.0,
                finished_at=utcnow_iso(),
            )
        except Exception as e:
            logger.exception("ジョブ失敗: %s (%s)", job.job_id, kind.value)
            job_repo.update(
                job.job_id,
                status=JobStatus.failed,
                error=str(e),
                finished_at=utcnow_iso(),
            )

    background.add_task(_run)
    return job
