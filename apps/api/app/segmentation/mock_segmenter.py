"""MockSegmenter: bbox 内を楕円形の仮マスクにする最も単純な実装。"""
from __future__ import annotations

import cv2
import numpy as np

from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter


class MockSegmenter(Segmenter):
    name = "mock"

    @property
    def supported_methods(self) -> set[SegmentationMethod]:
        return {SegmentationMethod.mock}

    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult:
        h, w = image.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        warnings = []
        if task.bbox:
            x, y, bw, bh = task.bbox
            cx, cy = x + bw // 2, y + bh // 2
            cv2.ellipse(mask, (cx, cy), (max(1, bw // 2), max(1, bh // 2)),
                        0, 0, 360, 255, -1)
        else:
            warnings.append("bbox 未指定のため空マスクを生成しました")
        return MaskResult(mask=mask, confidence=0.1, method_used=self.name,
                          warnings=warnings)
