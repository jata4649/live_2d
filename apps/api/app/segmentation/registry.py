"""Segmenter レジストリ。task.method に応じた実装を返す。

SAM2 は torch / sam2 が導入済みの環境でのみ有効化される。
未導入の場合は ManualBoxSegmenter にフォールバックし、警告として記録する。
"""
from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter
from app.segmentation.manual_box_segmenter import ManualBoxSegmenter
from app.segmentation.mock_segmenter import MockSegmenter
from app.segmentation.sam2_segmenter import Sam2Segmenter, sam2_importable

logger = get_logger(__name__)

_segmenters: list[Segmenter] = [MockSegmenter(), ManualBoxSegmenter()]
_sam2: Optional[Sam2Segmenter] = None


def _get_sam2() -> Optional[Sam2Segmenter]:
    """SAM2 を遅延生成する(モデルのロードは初回 segment 時)。"""
    global _sam2
    if _sam2 is None and sam2_importable():
        _sam2 = Sam2Segmenter()
    return _sam2


def resolve(method: SegmentationMethod) -> tuple[Segmenter, list[str]]:
    """method を処理できる Segmenter を返す。無ければフォールバック。"""
    if method in (SegmentationMethod.sam2_box, SegmentationMethod.sam2_points):
        sam2 = _get_sam2()
        if sam2 is not None:
            return sam2, []
    for seg in _segmenters:
        if method in seg.supported_methods:
            return seg, []
    fallback = ManualBoxSegmenter()
    warning = (
        f"セグメンテーション手法 {method.value} は未導入のため "
        f"{fallback.name} で代替しました"
    )
    logger.warning(warning)
    return fallback, [warning]


def run_task(image, task: SegmentationTask) -> MaskResult:
    seg, warnings = resolve(task.method)
    result = seg.segment(image, task)
    result.warnings = warnings + result.warnings
    return result


def list_segmenters() -> list[dict]:
    """利用可能なセグメンテーション手法と可否(UI セレクタ用)。"""
    sam2_ok = sam2_importable()
    return [
        {"method": "manual_box", "label": "矩形 + 簡易切り抜き", "available": True,
         "reason": ""},
        {"method": "mock", "label": "モック(楕円)", "available": True, "reason": ""},
        {"method": "sam2_box", "label": "SAM2(矩形プロンプト)",
         "available": sam2_ok,
         "reason": "" if sam2_ok else "torch / sam2 が未インストールです"},
        {"method": "sam2_points", "label": "SAM2(ポイントプロンプト)",
         "available": sam2_ok,
         "reason": "" if sam2_ok else "torch / sam2 が未インストールです"},
    ]
