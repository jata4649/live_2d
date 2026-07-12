"""エクスポート実行(PSD / layers.zip / rigging_plan)とフォールバック制御。"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.exporters.layer_zip_exporter import LayerZipExporter
from app.exporters.photoshop_script_exporter import PhotoshopScriptExporter
from app.exporters.psd_tools_exporter import PsdToolsExporter
from app.models.export import ExportResult
from app.services.project_service import load_parts, load_project, save_project
from app.services.quality_service import run_quality_check

logger = get_logger(__name__)


class ExportBlockedError(Exception):
    """品質スコア不足によるエクスポート拒否。"""

    def __init__(self, score: int):
        self.score = score
        super().__init__(
            f"品質スコアが {score} 点のため出力を中断しました"
            f"(基準: {settings.export_min_score} 点以上)。"
            "品質レポートを確認するか、force=true で強制出力してください"
        )


def _check_quality_gate(project_id: str, force: bool) -> None:
    report = run_quality_check(project_id)
    if not force and report.overall_score < settings.export_min_score:
        raise ExportBlockedError(report.overall_score)


def export_psd(project_id: str, force: bool = False) -> ExportResult:
    """PSD 出力。失敗時は JSX スクリプト生成へ自動フォールバック。"""
    _check_quality_gate(project_id, force)
    project = load_project(project_id)
    parts = load_parts(project_id)
    paths = ProjectPaths(project_id)

    result = PsdToolsExporter().export(
        project, parts, paths.layers_dir, paths.psd_export
    )
    if not result.ok:
        logger.warning("PSD 生成失敗、フォールバックへ: %s", result.error)
        fallback = PhotoshopScriptExporter().export(
            project, parts, paths.layers_dir, paths.photoshop_script
        )
        fallback.fallback_used = True
        fallback.warnings.insert(
            0,
            f"PSD 直接生成に失敗したため Photoshop スクリプトを生成しました: {result.error}",
        )
        # スクリプトと同じ場所に layers.zip も用意する
        LayerZipExporter().export(project, parts, paths.layers_dir, paths.layers_zip)
        return fallback

    project.status.export_done = True
    save_project(project)
    return result


def export_ora(project_id: str, force: bool = False) -> ExportResult:
    """OpenRaster (.ora) 出力(Krita / GIMP 向け)。"""
    from app.exporters.openraster_exporter import OpenRasterExporter

    _check_quality_gate(project_id, force)
    project = load_project(project_id)
    parts = load_parts(project_id)
    paths = ProjectPaths(project_id)
    return OpenRasterExporter().export(
        project, parts, paths.layers_dir, paths.ora_export
    )


def export_layers_zip(project_id: str, force: bool = False) -> ExportResult:
    _check_quality_gate(project_id, force)
    project = load_project(project_id)
    parts = load_parts(project_id)
    paths = ProjectPaths(project_id)
    return LayerZipExporter().export(project, parts, paths.layers_dir, paths.layers_zip)
