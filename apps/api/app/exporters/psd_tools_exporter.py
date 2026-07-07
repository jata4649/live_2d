"""psd-tools + pytoshop 互換の自前バイナリ生成による PSD 出力。

psd-tools は PSD の「読み込み・検証」に使い、書き込みは
Photoshop 互換の最小構成(RGBA レイヤー + グループ)を直接組み立てる。

Live2D Cubism 向け制約:
- RGB / 8bit / レイヤーマスクなし / クリッピングなし
- 1パーツ1レイヤー、z_order 降順が PSD の上
- group("Hair/Front" 形式)をグループ階層に変換

生成後に psd-tools で再読込して検証する(ラウンドトリップ)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.core.logging import get_logger
from app.exporters.base import PsdExporter
from app.models.export import ExporterCapabilities, ExportResult
from app.models.parts import Part, PartsPlan
from app.models.project import Project

logger = get_logger(__name__)


class PsdToolsExporter(PsdExporter):
    name = "psd_tools"

    def validate_capabilities(self) -> ExporterCapabilities:
        return ExporterCapabilities(
            name=self.name,
            supports_groups=True,
            supports_hidden_layers=True,
            max_recommended_layers=500,
        )

    def export(
        self,
        project: Project,
        parts: PartsPlan,
        layers_dir: Path,
        out_path: Path,
    ) -> ExportResult:
        warnings: list[str] = []
        width = project.source_image.width
        height = project.source_image.height

        # z_order 降順 = PSD の上から下(psd_writer は上から順に受け取る)
        ordered = sorted(parts.parts, key=lambda p: -p.z_order)
        layer_entries: list[dict] = []
        for part in ordered:
            png = layers_dir / f"{part.id}.png"
            if not png.exists():
                warnings.append(f"レイヤーPNG未生成のためスキップ: {part.id}")
                continue
            with Image.open(png) as img:
                rgba = np.asarray(img.convert("RGBA"))
            if rgba.shape[:2] != (height, width):
                return ExportResult(
                    ok=False, exporter=self.name,
                    error=f"{part.id} のキャンバスサイズが元画像と一致しません",
                )
            layer_entries.append({
                "name": _layer_name(part),
                "group": part.group,
                "visible": part.visible,
                "rgba": rgba,
            })

        if not layer_entries:
            return ExportResult(
                ok=False, exporter=self.name,
                error="出力可能なレイヤーがありません。先にレイヤー生成を実行してください",
            )

        try:
            from app.exporters.psd_writer import write_psd

            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_psd(out_path, width, height, layer_entries)
        except Exception as e:
            logger.exception("PSD 書き込み失敗")
            return ExportResult(ok=False, exporter=self.name, error=str(e))

        # ラウンドトリップ検証
        try:
            verify_warnings = self._verify(out_path, layer_entries, width, height)
            warnings += verify_warnings
        except Exception as e:
            return ExportResult(
                ok=False, exporter=self.name,
                error=f"生成した PSD の再読込検証に失敗しました: {e}",
            )

        return ExportResult(
            ok=True, exporter=self.name,
            output_path=str(out_path), warnings=warnings,
        )

    def _verify(
        self, path: Path, entries: list[dict], width: int, height: int
    ) -> list[str]:
        from psd_tools import PSDImage

        warnings = []
        psd = PSDImage.open(path)
        if (psd.width, psd.height) != (width, height):
            raise ValueError("PSD キャンバスサイズが一致しません")
        names = [layer.name for layer in psd.descendants() if not layer.is_group()]
        expected = [e["name"] for e in entries]
        if sorted(names) != sorted(expected):
            missing = set(expected) - set(names)
            raise ValueError(f"PSD 内のレイヤーが欠落しています: {missing}")
        if len(names) != len(set(names)):
            warnings.append("PSD 内にレイヤー名の重複があります")
        return warnings


def _layer_name(part: Part) -> str:
    # Cubism で識別しやすいよう英名を優先し、id をフォールバックに
    return part.name_en or part.id
