"""Inpainter 抽象基底クラス(MVP では NoopInpainter のみ)。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from app.models.segmentation import InpaintTask


class Inpainter(ABC):
    name: str = "base"

    @abstractmethod
    def inpaint(self, image: np.ndarray, mask: np.ndarray, task: InpaintTask) -> np.ndarray:
        """mask 領域を補完した画像を返す。"""


class NoopInpainter(Inpainter):
    """MVP 用: 何もしない。タスク計画の生成のみが目的のため。"""

    name = "noop"

    def inpaint(self, image: np.ndarray, mask: np.ndarray, task: InpaintTask) -> np.ndarray:
        return image
