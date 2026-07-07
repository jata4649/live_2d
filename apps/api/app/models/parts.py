"""parts.json のスキーマ。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PartType(str, Enum):
    face = "face"
    eye = "eye"
    eyebrow = "eyebrow"
    mouth = "mouth"
    hair = "hair"
    body = "body"
    clothes = "clothes"
    accessory = "accessory"
    other = "other"


class SegmentationMethod(str, Enum):
    mock = "mock"
    manual_box = "manual_box"
    alpha_color = "alpha_color"
    sam2_box = "sam2_box"
    sam2_points = "sam2_points"
    external_api = "external_api"


class Priority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class SegmentationSpec(BaseModel):
    method: SegmentationMethod = SegmentationMethod.manual_box
    # [x, y, w, h] 正規化画像ピクセル座標。未指定は None。
    bbox: Optional[list[int]] = None
    positive_points: list[list[int]] = Field(default_factory=list)
    negative_points: list[list[int]] = Field(default_factory=list)
    text_prompt: str = ""

    @field_validator("bbox")
    @classmethod
    def _bbox_shape(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is not None:
            if len(v) != 4:
                raise ValueError("bbox は [x, y, w, h] の4要素で指定してください")
            if v[2] <= 0 or v[3] <= 0:
                raise ValueError("bbox の幅・高さは正の値にしてください")
        return v


class PartFiles(BaseModel):
    mask_path: str = ""
    layer_path: str = ""


class Live2DInfo(BaseModel):
    usage: list[str] = Field(default_factory=list)
    parent_deformer_hint: str = ""
    physics_hint: str = ""


class ProcessingSpec(BaseModel):
    overlap_bleed_px: int = 4
    edge_feather_px: int = 1
    needs_inpaint_under: bool = False
    inpaint_reason: str = ""


class QualitySpec(BaseModel):
    priority: Priority = Priority.normal
    manual_review_required: bool = False
    score: Optional[int] = None


class Part(BaseModel):
    id: str
    name_jp: str
    name_en: str = ""
    group: str = ""
    z_order: int = 0
    visible: bool = True
    locked: bool = False
    required: bool = False
    part_type: PartType = PartType.other
    visual_description: str = ""
    segmentation: SegmentationSpec = Field(default_factory=SegmentationSpec)
    files: PartFiles = Field(default_factory=PartFiles)
    live2d: Live2DInfo = Field(default_factory=Live2DInfo)
    processing: ProcessingSpec = Field(default_factory=ProcessingSpec)
    quality: QualitySpec = Field(default_factory=QualitySpec)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError(
                "part id は英小文字・数字・アンダースコアのみ使用できます"
            )
        return v


class PartsPlan(BaseModel):
    version: str = "1.0"
    parts: list[Part] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "PartsPlan":
        seen: set[str] = set()
        for p in self.parts:
            if p.id in seen:
                raise ValueError(f"part id が重複しています: {p.id}")
            seen.add(p.id)
        return self
