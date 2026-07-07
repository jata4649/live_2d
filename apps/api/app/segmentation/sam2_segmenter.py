"""Sam2Segmenter: Phase 2 で実装するスタブ。

SAM2 導入時にこのクラスを完成させ、registry._segmenters に登録する。
インターフェースは確定済みのため、他のコードの変更は不要。
"""
from __future__ import annotations

import numpy as np

from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter


class Sam2Segmenter(Segmenter):
    name = "sam2"

    def __init__(self, checkpoint_path: str | None = None):
        raise NotImplementedError(
            "Sam2Segmenter は Phase 2 で実装予定です。"
            "現在は manual_box / mock を使用してください。"
        )

    @property
    def supported_methods(self) -> set[SegmentationMethod]:
        return {SegmentationMethod.sam2_box, SegmentationMethod.sam2_points}

    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult:
        raise NotImplementedError
