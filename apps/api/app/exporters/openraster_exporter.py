"""OpenRaster (.ora) エクスポータ。

Krita / GIMP がネイティブで開けるオープン規格。PSD が使えない
ワークフロー(Krita ユーザー等)向けの出力形式。

仕様: https://www.openraster.org/
- ZIP コンテナ。先頭エントリは無圧縮の `mimetype`(image/openraster)
- `stack.xml`: レイヤー構造(最初の子が最前面)
- `data/*.png`: 各レイヤー
- `mergedimage.png` / `Thumbnails/thumbnail.png`(仕様で必須)
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from app.core.logging import get_logger
from app.exporters.base import PsdExporter
from app.exporters.layer_tree import GroupNode, build_tree
from app.models.export import ExporterCapabilities, ExportResult
from app.models.parts import PartsPlan
from app.models.project import Project

logger = get_logger(__name__)

THUMBNAIL_MAX = 256


class OpenRasterExporter(PsdExporter):
    name = "openraster"

    def validate_capabilities(self) -> ExporterCapabilities:
        return ExporterCapabilities(
            name=self.name, supports_groups=True,
            supports_hidden_layers=True, max_recommended_layers=1000,
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

        # 上(手前)から順に、レイヤーPNGが存在するパーツを収集
        entries: list[dict] = []
        for part in sorted(parts.parts, key=lambda p: -p.z_order):
            png = layers_dir / f"{part.id}.png"
            if not png.exists():
                warnings.append(f"レイヤーPNG未生成のためスキップ: {part.id}")
                continue
            entries.append({
                "name": part.name_en or part.id,
                "group": part.group,
                "visible": part.visible,
                "png_path": png,
            })
        if not entries:
            return ExportResult(
                ok=False, exporter=self.name,
                error="出力可能なレイヤーがありません。先にレイヤー生成を実行してください",
            )

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_ora(out_path, width, height, entries)
        except Exception as e:
            logger.exception("ORA 書き込み失敗")
            return ExportResult(ok=False, exporter=self.name, error=str(e))

        return ExportResult(
            ok=True, exporter=self.name,
            output_path=str(out_path), warnings=warnings,
        )

    def _write_ora(
        self, out_path: Path, width: int, height: int, entries: list[dict]
    ) -> None:
        # レイヤーファイル名を確定(top-down 順に data/layer000.png ...)
        for i, entry in enumerate(entries):
            entry["src"] = f"data/layer{i:03d}.png"

        image = ET.Element(
            "image",
            {"version": "0.0.3", "w": str(width), "h": str(height),
             "xres": "72", "yres": "72"},
        )
        root_stack = ET.SubElement(image, "stack")
        self._emit(build_tree(entries), root_stack)
        stack_xml = ET.tostring(image, encoding="UTF-8", xml_declaration=True)

        merged = self._merged_image(width, height, entries)
        thumb = merged.copy()
        thumb.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX))

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype は仕様により先頭・無圧縮
            zf.writestr(
                zipfile.ZipInfo("mimetype"), b"image/openraster",
                compress_type=zipfile.ZIP_STORED,
            )
            zf.writestr("stack.xml", stack_xml)
            for entry in entries:
                zf.write(entry["png_path"], entry["src"])
            zf.writestr("mergedimage.png", self._png_bytes(merged))
            zf.writestr("Thumbnails/thumbnail.png", self._png_bytes(thumb))

    def _emit(self, node: GroupNode, parent_el: ET.Element) -> None:
        """ツリーを stack.xml 要素へ変換する(最初の子 = 最前面)。"""
        for child in node.children:
            if isinstance(child, GroupNode):
                stack_el = ET.SubElement(
                    parent_el, "stack",
                    {"name": child.name, "visibility": "visible",
                     "isolation": "isolate"},
                )
                self._emit(child, stack_el)
            else:
                ET.SubElement(
                    parent_el, "layer",
                    {
                        "name": child["name"],
                        "src": child["src"],
                        "x": "0",
                        "y": "0",
                        "opacity": "1.0",
                        "visibility": "visible" if child["visible"] else "hidden",
                        "composite-op": "svg:src-over",
                    },
                )

    @staticmethod
    def _merged_image(width: int, height: int, entries: list[dict]) -> Image.Image:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for entry in reversed(entries):  # 背面から合成
            if not entry["visible"]:
                continue
            with Image.open(entry["png_path"]) as img:
                canvas = Image.alpha_composite(canvas, img.convert("RGBA"))
        return canvas

    @staticmethod
    def _png_bytes(img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
