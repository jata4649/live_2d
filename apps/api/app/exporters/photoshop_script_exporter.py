"""Photoshop 用 ExtendScript(JSX)生成エクスポータ。

PSD 直接生成が失敗した場合のフォールバック。
生成された JSX を Photoshop で実行すると、レイヤーPNG群から
グループ階層付き PSD が組み立てられる。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.exporters.base import PsdExporter
from app.models.export import ExporterCapabilities, ExportResult
from app.models.parts import PartsPlan
from app.models.project import Project

_JSX_TEMPLATE = """// AutoLive2D Layer Studio 自動生成スクリプト
// Photoshop: ファイル > スクリプト > 参照... からこのファイルを実行してください。
// layers/ フォルダをこの JSX と同じ場所に置いてください。
var manifest = {manifest_json};

var scriptFile = new File($.fileName);
var baseFolder = scriptFile.parent;
var doc = app.documents.add(
  new UnitValue(manifest.canvas.width, "px"),
  new UnitValue(manifest.canvas.height, "px"),
  72, manifest.project, NewDocumentMode.RGB,
  DocumentFill.TRANSPARENT, 1, BitsPerChannelType.EIGHT
);

function findOrCreateGroup(path) {
  var parent = doc;
  if (!path) return null;
  var segs = path.split("/");
  var set = null;
  for (var i = 0; i < segs.length; i++) {
    var found = null;
    var sets = (set ? set.layerSets : doc.layerSets);
    for (var j = 0; j < sets.length; j++) {
      if (sets[j].name === segs[i]) { found = sets[j]; break; }
    }
    set = found || (set ? set.layerSets.add() : doc.layerSets.add());
    if (!found) set.name = segs[i];
  }
  return set;
}

// manifest.layers は z_order 降順(最前面が先頭)
for (var i = manifest.layers.length - 1; i >= 0; i--) {
  var info = manifest.layers[i];
  var pngFile = new File(baseFolder + "/" + info.file);
  if (!pngFile.exists) continue;
  var placed = app.open(pngFile);
  placed.selection.selectAll();
  placed.selection.copy();
  placed.close(SaveOptions.DONOTSAVECHANGES);
  doc.paste();
  var layer = doc.activeLayer;
  layer.name = info.name;
  layer.visible = info.visible;
  // 貼り付けは中央基準になるため左上原点に移動
  var b = layer.bounds;
  layer.translate(-b[0], -b[1]);
  var grp = findOrCreateGroup(info.group);
  if (grp) layer.move(grp, ElementPlacement.PLACEATBEGINNING);
}
alert("AutoLive2D Layer Studio: レイヤー構築が完了しました。PSD として保存してください。");
"""


class PhotoshopScriptExporter(PsdExporter):
    name = "photoshop_script"

    def validate_capabilities(self) -> ExporterCapabilities:
        return ExporterCapabilities(name=self.name, max_recommended_layers=1000)

    def export(
        self,
        project: Project,
        parts: PartsPlan,
        layers_dir: Path,
        out_path: Path,
    ) -> ExportResult:
        layers = []
        warnings: list[str] = []
        for part in sorted(parts.parts, key=lambda p: -p.z_order):
            if not (layers_dir / f"{part.id}.png").exists():
                warnings.append(f"レイヤーPNG未生成のためスキップ: {part.id}")
                continue
            layers.append({
                "id": part.id,
                "name": part.name_en or part.name_jp,
                "group": part.group,
                "z_order": part.z_order,
                "visible": part.visible,
                "file": f"layers/{part.id}.png",
            })
        manifest = {
            "project": project.name,
            "canvas": {
                "width": project.source_image.width,
                "height": project.source_image.height,
            },
            "layers": layers,
        }
        jsx = _JSX_TEMPLATE.replace(
            "{manifest_json}", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(jsx, encoding="utf-8")
        return ExportResult(
            ok=True, exporter=self.name,
            output_path=str(out_path), warnings=warnings,
        )
