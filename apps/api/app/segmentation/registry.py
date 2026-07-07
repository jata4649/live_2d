"""Segmenter レジストリ。task.method に応じた実装を返す。

SAM2 等の高度な手法が未導入の場合は ManualBoxSegmenter に
フォールバックし、警告として記録する。
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter
from app.segmentation.manual_box_segmenter import ManualBoxSegmenter
from app.segmentation.mock_segmenter import MockSegmenter

logger = get_logger(__name__)

_segmenters: list[Segmenter] = [MockSegmenter(), ManualBoxSegmenter()]
# Sam2Segmenter は Phase 2 でここに登録する(sam2 がインストール済みの場合のみ)


def resolve(method: SegmentationMethod) -> tuple[Segmenter, list[str]]:
    """method を処理できる Segmenter を返す。無ければフォールバック。"""
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
