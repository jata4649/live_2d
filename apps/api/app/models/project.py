"""project.json のスキーマ。"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QualityLevel(str, Enum):
    draft = "draft"
    standard = "standard"
    high = "high"
    commercial = "commercial"


class FaceRange(str, Enum):
    small = "small"
    medium = "medium"
    large = "large"


class MouthType(str, Enum):
    open_close = "open_close"
    aiueo = "aiueo"
    singing = "singing"
    auto = "auto"


class EyeType(str, Enum):
    blink = "blink"
    gaze = "gaze"
    full = "full"


class SourceImage(BaseModel):
    original_path: str = "source/original.png"
    normalized_path: str = "source/normalized.png"
    width: int = 0
    height: int = 0
    has_alpha: bool = False
    color_profile: str = "sRGB"


class UserPreferences(BaseModel):
    quality_level: QualityLevel = QualityLevel.standard
    target: str = "VTube Studio"
    face_range: FaceRange = FaceRange.medium
    mouth_type: MouthType = MouthType.auto
    eye_type: EyeType = EyeType.full
    hair_physics: bool = True
    accessory_physics: bool = True
    arm_movement: bool = False
    expression_variants: bool = False
    accessories: list[str] = Field(default_factory=list)


class ProjectStatus(BaseModel):
    analysis_done: bool = False
    interview_done: bool = False
    segmentation_done: bool = False
    quality_checked: bool = False
    export_done: bool = False


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Project(BaseModel):
    project_id: str
    name: str
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    source_image: SourceImage = Field(default_factory=SourceImage)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    status: ProjectStatus = Field(default_factory=ProjectStatus)


class ProjectSummary(BaseModel):
    """一覧表示用の軽量ビュー。"""
    project_id: str
    name: str
    created_at: str
    updated_at: str
    status: ProjectStatus
    thumbnail_path: Optional[str] = None
