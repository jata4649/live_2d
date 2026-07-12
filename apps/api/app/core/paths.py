"""プロジェクト内ファイルパスの一元管理。

パス組み立てはこのモジュール以外で行わないこと。
parts.json 等に保存するパスはすべてプロジェクトルートからの相対パス文字列とし、
実ファイルアクセス時に ProjectPaths で絶対パスへ解決する。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings


class ProjectPaths:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.root: Path = settings.projects_root / project_id

    # --- ディレクトリ ---
    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def masks_dir(self) -> Path:
        return self.root / "masks"

    @property
    def layers_dir(self) -> Path:
        return self.root / "layers"

    @property
    def previews_dir(self) -> Path:
        return self.root / "previews"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    @property
    def json_dir(self) -> Path:
        return self.root / "json"

    @property
    def docs_dir(self) -> Path:
        return self.root / "docs"

    def ensure_dirs(self) -> None:
        for d in (
            self.source_dir,
            self.masks_dir,
            self.layers_dir,
            self.previews_dir,
            self.exports_dir,
            self.json_dir,
            self.docs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    # --- 個別ファイル(絶対パス)---
    @property
    def original_image(self) -> Path:
        return self.source_dir / "original.png"

    @property
    def normalized_image(self) -> Path:
        return self.source_dir / "normalized.png"

    @property
    def working_image(self) -> Path:
        return self.source_dir / "working.png"

    def mask_png(self, part_id: str) -> Path:
        return self.masks_dir / f"{part_id}_mask.png"

    def layer_png(self, part_id: str) -> Path:
        return self.layers_dir / f"{part_id}.png"

    @property
    def composite_preview(self) -> Path:
        return self.previews_dir / "composite_preview.png"

    @property
    def difference_preview(self) -> Path:
        return self.previews_dir / "difference_preview.png"

    @property
    def project_json(self) -> Path:
        return self.json_dir / "project.json"

    @property
    def parts_json(self) -> Path:
        return self.json_dir / "parts.json"

    @property
    def segmentation_tasks_json(self) -> Path:
        return self.json_dir / "segmentation_tasks.json"

    @property
    def inpaint_tasks_json(self) -> Path:
        return self.json_dir / "inpaint_tasks.json"

    @property
    def quality_report_json(self) -> Path:
        return self.json_dir / "quality_report.json"

    @property
    def psd_export(self) -> Path:
        return self.exports_dir / "live2d_import.psd"

    @property
    def layers_zip(self) -> Path:
        return self.exports_dir / "layers.zip"

    @property
    def ora_export(self) -> Path:
        return self.exports_dir / "live2d_import.ora"

    @property
    def photoshop_script(self) -> Path:
        return self.exports_dir / "import_script.jsx"

    @property
    def rigging_plan_md(self) -> Path:
        return self.docs_dir / "rigging_plan.md"

    # --- 相対パス(JSONに保存する形式)---
    def rel(self, abs_path: Path) -> str:
        return abs_path.relative_to(self.root).as_posix()

    def resolve(self, rel_path: str) -> Path:
        """相対パスを絶対パスへ解決。プロジェクト外への脱出を拒否する。"""
        p = (self.root / rel_path).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"プロジェクト外のパスは参照できません: {rel_path}")
        return p
