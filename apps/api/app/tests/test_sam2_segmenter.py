"""Sam2Segmenter のテスト(フェイク predictor 注入。torch/sam2 不要)。"""
from __future__ import annotations

import numpy as np
import pytest

from app.models.parts import SegmentationMethod
from app.models.segmentation import SegmentationTask
from app.segmentation.sam2_segmenter import Sam2Segmenter


class FakePredictor:
    """SAM2ImagePredictor の set_image / predict を模倣する。"""

    def __init__(self, size=(80, 100)):  # (H, W)
        self.size = size
        self.set_images: list[np.ndarray] = []
        self.calls: list[dict] = []

    def set_image(self, image):
        self.set_images.append(image)

    def predict(self, box=None, point_coords=None, point_labels=None,
                multimask_output=False):
        self.calls.append({
            "box": box, "point_coords": point_coords, "point_labels": point_labels,
        })
        h, w = self.size
        mask = np.zeros((1, h, w), np.float32)
        if box is not None:
            x0, y0, x1, y1 = (int(v) for v in box)
            mask[0, y0:y1, x0:x1] = 1.0
        scores = np.array([0.93])
        return mask, scores, None


def _task(method=SegmentationMethod.sam2_box, **kw) -> SegmentationTask:
    return SegmentationTask(task_id="t1", part_id="p1", method=method, **kw)


def _image(h=80, w=100) -> np.ndarray:
    img = np.zeros((h, w, 4), np.uint8)
    img[:, :, 3] = 255
    return img


def test_box_prompt_converts_xywh_to_xyxy():
    predictor = FakePredictor()
    seg = Sam2Segmenter(predictor=predictor)
    result = seg.segment(_image(), _task(bbox=[10, 20, 30, 40]))

    call = predictor.calls[0]
    assert list(call["box"]) == [10, 20, 40, 60]  # x+w, y+h
    assert result.mask.dtype == np.uint8
    assert result.mask[30, 20] == 255   # box 内
    assert result.mask[5, 5] == 0       # box 外
    assert result.confidence == pytest.approx(0.93)


def test_bbox_clipped_to_image_bounds():
    predictor = FakePredictor()
    seg = Sam2Segmenter(predictor=predictor)
    seg.segment(_image(h=80, w=100), _task(bbox=[90, 70, 50, 50]))
    assert list(predictor.calls[0]["box"]) == [90, 70, 100, 80]


def test_point_prompts_with_labels():
    predictor = FakePredictor()
    seg = Sam2Segmenter(predictor=predictor)
    seg.segment(
        _image(),
        _task(
            method=SegmentationMethod.sam2_points,
            bbox=[0, 0, 50, 50],
            positive_points=[[10, 10], [20, 20]],
            negative_points=[[30, 30]],
        ),
    )
    call = predictor.calls[0]
    assert call["point_coords"].tolist() == [[10, 10], [20, 20], [30, 30]]
    assert call["point_labels"].tolist() == [1, 1, 0]


def test_no_prompt_returns_empty_mask_with_warning():
    seg = Sam2Segmenter(predictor=FakePredictor())
    result = seg.segment(_image(), _task())
    assert result.mask.sum() == 0
    assert any("未指定" in w for w in result.warnings)


def test_rgba_composited_on_white_before_predict():
    predictor = FakePredictor()
    seg = Sam2Segmenter(predictor=predictor)
    img = np.zeros((80, 100, 4), np.uint8)  # 全透明
    seg.segment(img, _task(bbox=[0, 0, 10, 10]))
    sent = predictor.set_images[0]
    assert sent.shape == (80, 100, 3)
    assert sent[0, 0].tolist() == [255, 255, 255]  # 透明→白


def test_registry_fallback_when_sam2_missing(monkeypatch):
    """sam2 未導入環境では manual_box にフォールバックし警告が付く。"""
    from app.segmentation import registry

    monkeypatch.setattr(registry, "sam2_importable", lambda: False)
    monkeypatch.setattr(registry, "_sam2", None)
    seg, warnings = registry.resolve(SegmentationMethod.sam2_box)
    assert seg.name == "manual_box"
    assert warnings and "代替" in warnings[0]


def test_segmenters_endpoint(client):
    res = client.get("/api/v1/segmenters")
    assert res.status_code == 200
    methods = {s["method"] for s in res.json()}
    assert {"manual_box", "mock", "sam2_box", "sam2_points"} <= methods
