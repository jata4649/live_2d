"""エクスポート関連のスキーマ。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExportResult(BaseModel):
    ok: bool
    exporter: str
    output_path: str = ""
    fallback_used: bool = False
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class ExporterCapabilities(BaseModel):
    name: str
    supports_groups: bool = True
    supports_hidden_layers: bool = True
    max_recommended_layers: int = 500
