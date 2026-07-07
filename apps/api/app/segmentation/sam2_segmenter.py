"""Sam2Segmenter: SAM2 (Segment Anything Model 2) による高精度セグメンテーション。

- box prompt(sam2_box)と point prompt(sam2_points: positive/negative)に対応
- モデルは Hugging Face Hub からロード(既定: facebook/sam2-hiera-tiny)
- torch / sam2 が未導入の環境では is_available() が False を返し、
  registry が ManualBoxSegmenter へフォールバックする(MVP 動作は不変)
- 予測器は遅延ロード + プロセス内キャッシュ(初回のみ数十秒かかるため)
- テストでは predictor を注入してネットワーク・GPU なしで検証する
"""
from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np

from app.core.logging import get_logger
from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.base import MaskResult, Segmenter

logger = get_logger(__name__)

DEFAULT_MODEL = "facebook/sam2-hiera-tiny"


def sam2_importable() -> bool:
    try:
        import sam2  # noqa: F401
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


_predictor_cache: dict[str, Any] = {}


def _load_predictor(model_id: str, device: str) -> Any:
    """予測器をロードする。

    - 既定: Hugging Face Hub から from_pretrained(model_id)
    - ALS_SAM2_CHECKPOINT が設定されていればローカルの .pt を使用
      (HF に到達できないネットワーク制限環境向け。config は ALS_SAM2_CONFIG)
    """
    checkpoint = os.environ.get("ALS_SAM2_CHECKPOINT", "")
    key = f"{checkpoint or model_id}@{device}"
    if key not in _predictor_cache:
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        if checkpoint:
            from sam2.build_sam import build_sam2

            config = os.environ.get(
                "ALS_SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_t.yaml"
            )
            logger.info("SAM2 をローカル checkpoint からロード中: %s", checkpoint)
            model = build_sam2(config, checkpoint, device=device)
            _predictor_cache[key] = SAM2ImagePredictor(model)
        else:
            logger.info("SAM2 モデルをロード中: %s (device=%s)", model_id, device)
            _predictor_cache[key] = SAM2ImagePredictor.from_pretrained(
                model_id, device=device
            )
    return _predictor_cache[key]


class Sam2Segmenter(Segmenter):
    name = "sam2"

    def __init__(
        self,
        model_id: Optional[str] = None,
        device: Optional[str] = None,
        predictor: Any = None,
    ):
        self.model_id = model_id or os.environ.get("ALS_SAM2_MODEL", DEFAULT_MODEL)
        self.device = device or os.environ.get("ALS_SAM2_DEVICE", "cpu")
        self._predictor = predictor  # テスト注入用。None なら遅延ロード

    @property
    def supported_methods(self) -> set[SegmentationMethod]:
        return {SegmentationMethod.sam2_box, SegmentationMethod.sam2_points}

    def _get_predictor(self) -> Any:
        if self._predictor is None:
            self._predictor = _load_predictor(self.model_id, self.device)
        return self._predictor

    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult:
        h, w = image.shape[:2]
        warnings: list[str] = []

        box, points, labels = self._build_prompts(task, w, h, warnings)
        if box is None and points is None:
            return MaskResult(
                mask=np.zeros((h, w), np.uint8),
                confidence=0.0,
                method_used=self.name,
                warnings=warnings
                + ["bbox もポイントも未指定です。パーツ編集画面で指定してください"],
            )

        predictor = self._get_predictor()
        # SAM2 は RGB 3ch を想定。透明部分は白背景に合成する
        rgb = self._to_rgb(image)
        predictor.set_image(rgb)
        masks, scores, _ = predictor.predict(
            box=box,
            point_coords=points,
            point_labels=labels,
            multimask_output=False,
        )

        mask = np.asarray(masks[0])
        if mask.ndim == 3:  # (1, H, W) で返る実装への対応
            mask = mask[0]
        binary = (mask > 0.5).astype(np.uint8) * 255
        confidence = float(np.asarray(scores).reshape(-1)[0])
        return MaskResult(
            mask=binary,
            confidence=confidence,
            method_used=f"{self.name}:{task.method.value}",
            warnings=warnings,
        )

    @staticmethod
    def _build_prompts(
        task: SegmentationTask, w: int, h: int, warnings: list[str]
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """タスクから SAM2 のプロンプト(box xyxy / points / labels)を組み立てる。"""
        box = None
        if task.bbox:
            x, y, bw, bh = task.bbox
            x0 = max(0, min(x, w - 1))
            y0 = max(0, min(y, h - 1))
            x1 = max(x0 + 1, min(x + bw, w))
            y1 = max(y0 + 1, min(y + bh, h))
            box = np.array([x0, y0, x1, y1], dtype=np.float32)

        coords: list[list[int]] = []
        labels: list[int] = []
        for p in task.positive_points:
            coords.append([int(p[0]), int(p[1])])
            labels.append(1)
        for p in task.negative_points:
            coords.append([int(p[0]), int(p[1])])
            labels.append(0)

        if task.method == SegmentationMethod.sam2_points and not coords:
            if box is not None:
                warnings.append(
                    "ポイント未指定のため box プロンプトのみで実行しました"
                )
            return box, None, None

        if not coords:
            return box, None, None
        return (
            box,
            np.array(coords, dtype=np.float32),
            np.array(labels, dtype=np.int32),
        )

    @staticmethod
    def _to_rgb(rgba: np.ndarray) -> np.ndarray:
        if rgba.shape[2] == 3:
            return rgba
        alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
        rgb = rgba[:, :, :3].astype(np.float32)
        white = 255.0 * (1.0 - alpha)
        return (rgb * alpha + white).astype(np.uint8)
