"""非同期ジョブのスキーマ。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.project import utcnow_iso


class JobKind(str, Enum):
    segmentation_run = "segmentation_run"
    layer_generate = "layer_generate"
    quality_check = "quality_check"
    export_psd = "export_psd"
    export_layers_zip = "export_layers_zip"
    auto_pipeline = "auto_pipeline"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(BaseModel):
    job_id: str
    project_id: str
    kind: JobKind
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    created_at: str = Field(default_factory=utcnow_iso)
    finished_at: Optional[str] = None
