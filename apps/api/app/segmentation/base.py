"""Segmenter 抽象基底クラス。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask


@dataclass
class MaskResult:
    """segment() の返り値。mask は uint8 (H, W)、0=背景 255=前景。"""
    mask: np.ndarray
    confidence: Optional[float] = None
    method_used: str = ""
    warnings: list[str] = field(default_factory=list)


class Segmenter(ABC):
    name: str = "base"

    @abstractmethod
    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult:
        """image は RGBA uint8 (H, W, 4)。"""

    @property
    @abstractmethod
    def supported_methods(self) -> set[SegmentationMethod]:
        ...
