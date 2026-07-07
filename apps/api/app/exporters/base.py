"""PsdExporter 抽象基底クラス。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.export import ExporterCapabilities, ExportResult
from app.models.parts import PartsPlan
from app.models.project import Project


class PsdExporter(ABC):
    name: str = "base"

    @abstractmethod
    def export(
        self,
        project: Project,
        parts: PartsPlan,
        layers_dir: Path,
        out_path: Path,
    ) -> ExportResult:
        """レイヤーPNG群から出力ファイルを生成する。"""

    @abstractmethod
    def validate_capabilities(self) -> ExporterCapabilities:
        ...
