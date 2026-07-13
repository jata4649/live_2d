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


# 色ベース分離(GrabCut mask init)を適用する bbox 面積の上限(画像比)。
# 目・口・虹彩など小さな内部パーツのみが対象。顔・胴体などの大きな
# ベースパーツは中央シードの色に引きずられて縮むため、従来のアルファ
# 切り抜きを維持する(下地パーツは広めに取るのが Live2D 的にも正解)。
COLOR_SEPARATION_MAX_AREA_RATIO = 0.05


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
        opaque_ratio = float((box_alpha > 8).mean())

        image_has_alpha = bool((alpha < 250).any())
        is_small = bw * bh <= COLOR_SEPARATION_MAX_AREA_RATIO * w * h

        mask = np.zeros((h, w), np.uint8)
        if image_has_alpha and opaque_ratio < 0.85:
            # 透過境界が bbox 内にある(髪の房・アホ毛など輪郭系パーツ):
            # アルファ切り抜きが最も信頼できる
            mask[y : y + bh, x : x + bw] = np.where(box_alpha > 8, 255, 0).astype(np.uint8)
            confidence = 0.6
            method = "alpha"
        elif image_has_alpha and is_small:
            # bbox 内がほぼ不透明な小パーツ(顔の上の目・口・虹彩など):
            # アルファでは周囲と分離できないため、色ベース(GrabCut)で分離する
            confidence, method = self._grabcut_color_separation(
                image, mask, (x, y, bw, bh), task, warnings
            )
        elif image_has_alpha:
            # bbox 内がほぼ不透明な大パーツ(顔・胴体などのベースパーツ):
            # 下地は広めに取るのが正解のため bbox 全体(∩ アルファ)を採用する
            mask[y : y + bh, x : x + bw] = np.where(box_alpha > 8, 255, 0).astype(np.uint8)
            confidence = 0.5
            method = "alpha_rect"
        else:
            # 完全不透明画像(アルファ情報なし): 従来どおり矩形初期化 GrabCut
            confidence, method = self._grabcut(image, mask, (x, y, bw, bh), warnings)

        if mask[y : y + bh, x : x + bw].sum() == 0:
            # 全滅した場合は矩形フォールバック
            mask[y : y + bh, x : x + bw] = 255
            confidence = 0.2
            warnings.append("切り抜きに失敗したため矩形マスクにフォールバックしました")

        return MaskResult(mask=mask, confidence=confidence,
                          method_used=f"{self.name}:{method}", warnings=warnings)

    def _grabcut_color_separation(
        self,
        image: np.ndarray,
        mask_out: np.ndarray,
        rect: tuple[int, int, int, int],
        task: SegmentationTask,
        warnings: list[str],
    ) -> tuple[float, str]:
        """マスク初期化つき GrabCut。

        bbox 中央部を前景候補、bbox 内周辺を背景候補、bbox 外と透明部を
        確定背景として色分布で分離する。目・口・虹彩など「不透明領域の
        内部にあるパーツ」を周囲の肌・髪から切り分けるための経路。
        """
        x, y, bw, bh = rect
        try:
            bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            gc_mask = np.full(image.shape[:2], cv2.GC_BGD, np.uint8)
            gc_mask[y : y + bh, x : x + bw] = cv2.GC_PR_BGD
            # 中央 50% を前景候補にする
            cx0 = x + bw // 4
            cy0 = y + bh // 4
            gc_mask[cy0 : cy0 + bh // 2, cx0 : cx0 + bw // 2] = cv2.GC_PR_FGD
            gc_mask[image[:, :, 3] <= 8] = cv2.GC_BGD
            # ポイントプロンプトを前景/背景候補として反映する。
            # 確定(GC_FGD/GC_BGD)ではなく候補(PR)にとどめることで、
            # 自動生成ポイントが実パーツから外れていても致命傷にならない
            h_img, w_img = image.shape[:2]
            r = max(2, min(bw, bh) // 20)
            for px, py in task.positive_points:
                if 0 <= px < w_img and 0 <= py < h_img:
                    cv2.circle(gc_mask, (int(px), int(py)), r,
                               int(cv2.GC_PR_FGD), -1)
            for px, py in task.negative_points:
                if 0 <= px < w_img and 0 <= py < h_img:
                    cv2.circle(gc_mask, (int(px), int(py)), r,
                               int(cv2.GC_PR_BGD), -1)
            # 透明部は常に確定背景
            gc_mask[image[:, :, 3] <= 8] = cv2.GC_BGD

            bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
            cv2.grabCut(bgr, gc_mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
            fg = (
                (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)
            ).astype(np.uint8) * 255
            clipped = np.zeros_like(fg)
            clipped[y : y + bh, x : x + bw] = fg[y : y + bh, x : x + bw]
            mask_out[:] = clipped
            return 0.5, "grabcut_color"
        except Exception as e:
            warnings.append(f"色分離 GrabCut が失敗しました: {e}")
            return 0.2, "rect"

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
