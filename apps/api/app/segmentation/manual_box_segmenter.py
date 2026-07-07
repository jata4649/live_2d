"""ManualBoxSegmenter: 矩形内をアルファ・色ベースで簡易切り抜きする MVP 実装。

手法:
1. 元画像にアルファがあれば、bbox 内のアルファ > 0 領域を前景候補とする
2. アルファがない(全面不透明)場合は GrabCut を bbox 初期化で実行
3. GrabCut が使えない/失敗した場合は bbox 矩形をそのままマスクにする

いずれの場合も結果は bbox 内にクリップされる。
"""
from __future__ import annotations

import cv2
import numpy as np

from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter


class ManualBoxSegmenter(Segmenter):
    name = "manual_box"

    @property
    def supported_methods(self) -> set[SegmentationMethod]:
        return {SegmentationMethod.manual_box, SegmentationMethod.alpha_color}

    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult:
        h, w = image.shape[:2]
        warnings: list[str] = []
        if not task.bbox:
            return MaskResult(
                mask=np.zeros((h, w), np.uint8),
                confidence=0.0,
                method_used=self.name,
                warnings=["bbox が未指定です。パーツ編集画面で矩形を指定してください"],
            )

        x, y, bw, bh = task.bbox
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        bw = max(1, min(bw, w - x))
        bh = max(1, min(bh, h - y))

        alpha = image[:, :, 3]
        box_alpha = alpha[y : y + bh, x : x + bw]

        mask = np.zeros((h, w), np.uint8)
        if (box_alpha < 250).any():
            # 透過情報あり: アルファをそのまま前景とみなす(最も信頼できる)
            mask[y : y + bh, x : x + bw] = np.where(box_alpha > 8, 255, 0).astype(np.uint8)
            confidence = 0.6
            method = "alpha"
        else:
            confidence, method = self._grabcut(image, mask, (x, y, bw, bh), warnings)

        if mask[y : y + bh, x : x + bw].sum() == 0:
            # 全滅した場合は矩形フォールバック
            mask[y : y + bh, x : x + bw] = 255
            confidence = 0.2
            warnings.append("切り抜きに失敗したため矩形マスクにフォールバックしました")

        return MaskResult(mask=mask, confidence=confidence,
                          method_used=f"{self.name}:{method}", warnings=warnings)

    def _grabcut(
        self,
        image: np.ndarray,
        mask_out: np.ndarray,
        rect: tuple[int, int, int, int],
        warnings: list[str],
    ) -> tuple[float, str]:
        x, y, bw, bh = rect
        try:
            bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            gc_mask = np.zeros(image.shape[:2], np.uint8)
            bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
            cv2.grabCut(bgr, gc_mask, (x, y, bw, bh), bgd, fgd, 4,
                        cv2.GC_INIT_WITH_RECT)
            fg = ((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)).astype(np.uint8) * 255
            # bbox 外は常に背景
            clipped = np.zeros_like(fg)
            clipped[y : y + bh, x : x + bw] = fg[y : y + bh, x : x + bw]
            mask_out[:] = clipped
            return 0.4, "grabcut"
        except Exception as e:  # GrabCut は入力により失敗しうる
            warnings.append(f"GrabCut が失敗しました: {e}")
            return 0.2, "rect"
