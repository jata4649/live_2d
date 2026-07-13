"""quality_report.json のスキーマ。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.project import utcnow_iso


class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class IssueCode(str, Enum):
    DUPLICATE_LAYER_NAME = "DUPLICATE_LAYER_NAME"
    EMPTY_LAYER = "EMPTY_LAYER"
    MISSING_MASK = "MISSING_MASK"
    COMPOSITE_DIFF = "COMPOSITE_DIFF"
    Z_ORDER_ANOMALY = "Z_ORDER_ANOMALY"
    LR_NAMING_MISMATCH = "LR_NAMING_MISMATCH"
    MISSING_REQUIRED_PART = "MISSING_REQUIRED_PART"
    INSUFFICIENT_BLEED = "INSUFFICIENT_BLEED"
    EDGE_ARTIFACT = "EDGE_ARTIFACT"
    PSD_CONSTRAINT_VIOLATION = "PSD_CONSTRAINT_VIOLATION"
    FILE_MISSING = "FILE_MISSING"
    COLOR_CONTAMINATION = "COLOR_CONTAMINATION"


class QualityIssue(BaseModel):
    severity: Severity
    part_id: Optional[str] = None
    code: IssueCode
    message: str
    suggested_fix: str = ""
    auto_fix_available: bool = False


class QualityReport(BaseModel):
    overall_score: int = 0
    approved: bool = False
    checked_at: str = Field(default_factory=utcnow_iso)
    issues: list[QualityIssue] = Field(default_factory=list)
