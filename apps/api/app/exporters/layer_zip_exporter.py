"""レイヤーPNG + manifest.json の ZIP エクスポート(常時提供の保険)。"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.exporters.base import PsdExporter
from app.models.export import ExporterCapabilities, ExportResult
from app.models.parts import PartsPlan
from app.models.project import Project


class LayerZipExporter(PsdExporter):
    name = "layer_zip"

    def validate_capabilities(self) -> ExporterCapabilities:
        return ExporterCapabilities(name=self.name, max_recommended_layers=2000)

    def export(
        self,
        project: Project,
        parts: PartsPlan,
        layers_dir: Path,
        out_path: Path,
    ) -> ExportResult:
        warnings: list[str] = []
        manifest = {
            "project": project.name,
            "canvas": {
                "width": project.source_image.width,
                "height": project.source_image.height,
            },
            "note": "z_order 降順が最前面。全レイヤーはキャンバス左上原点に配置してください。",
            "layers": [],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for part in sorted(parts.parts, key=lambda p: -p.z_order):
                png = layers_dir / f"{part.id}.png"
                if not png.exists():
                    warnings.append(f"レイヤーPNG未生成のためスキップ: {part.id}")
                    continue
                arcname = f"layers/{part.id}.png"
                zf.write(png, arcname)
                manifest["layers"].append({
                    "id": part.id,
                    "name": part.name_en or part.name_jp,
                    "group": part.group,
                    "z_order": part.z_order,
                    "visible": part.visible,
                    "file": arcname,
                })
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
        return ExportResult(
            ok=True, exporter=self.name,
            output_path=str(out_path), warnings=warnings,
        )
