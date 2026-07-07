"""segmentation_tasks.json / inpaint_tasks.json / ヒアリングのスキーマ。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.parts import SegmentationMethod


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class RefinementParams(BaseModel):
    remove_small_noise: bool = True
    fill_holes: bool = True
    smooth_edges: bool = True
    dilate_px: int = 0
    erode_px: int = 0
    feather_px: int = 0


class SegmentationTask(BaseModel):
    task_id: str
    part_id: str
    image_path: str = "source/normalized.png"
    method: SegmentationMethod = SegmentationMethod.manual_box
    bbox: Optional[list[int]] = None
    positive_points: list[list[int]] = Field(default_factory=list)
    negative_points: list[list[int]] = Field(default_factory=list)
    text_prompt: str = ""
    expected_output: str = ""
    refinement: RefinementParams = Field(default_factory=RefinementParams)
    status: TaskStatus = TaskStatus.pending
    error: Optional[str] = None


class SegmentationTaskList(BaseModel):
    tasks: list[SegmentationTask] = Field(default_factory=list)


class InpaintTask(BaseModel):
    task_id: str
    target_part_id: str
    occluder_part_ids: list[str] = Field(default_factory=list)
    region_mask_path: str = ""
    reason: str = ""
    method: str = "none"  # MVP: "none" / 将来: "api" | "local_model"
    priority: str = "normal"
    status: str = "planned"


class InpaintTaskList(BaseModel):
    tasks: list[InpaintTask] = Field(default_factory=list)


class Question(BaseModel):
    id: str
    category: str
    question: str
    type: str = "single_choice"  # single_choice | multi_choice | boolean | text
    choices: list[str] = Field(default_factory=list)
    maps_to: str = ""


class QuestionList(BaseModel):
    questions: list[Question] = Field(default_factory=list)
