"""疑似モーションチェック。

揺れもの・可動パーツを数パターン平行移動して合成し、
「動かしたときに現れる穴(下地の欠け)」を Cubism 持ち込み前に検出する。

穴の定義: 元の合成で不透明だったピクセルが、パーツを動かした合成で
透明になった箇所(= そのパーツの下に描画が存在しない領域)。

速度のため長辺 1024px 以下に縮小して評価する。
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.models.parts import Part, PartType
from app.services.project_service import load_parts

logger = get_logger(__name__)

CHECK_LONG_EDGE = 1024
# 可動量(画像幅比)。髪・装飾の物理揺れを想定した振幅
AMPLITUDE_RATIO = 0.03

# 動かす対象: 揺れもの + 可動が想定されるパーツ
_MOVABLE_TYPES = {PartType.hair, PartType.accessory}


class MotionHole(BaseModel):
    part_id: str
    shift: list[int]  # [dx, dy](チェック解像度でのピクセル)
    hole_px: int
    hole_ratio: float  # 人物領域に対する比率


class MotionCheckReport(BaseModel):
    amplitude_px: int
    checked_parts: int
    entries: list[MotionHole] = Field(default_factory=list)
    preview_path: str = ""


def _is_movable(part: Part) -> bool:
    if part.part_type in _MOVABLE_TYPES:
        return True
    return bool(part.live2d.physics_hint)


def _shift_layer(layer: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(layer)
    h, w = layer.shape[:2]
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    if sx0 < sx1 and sy0 < sy1:
        out[sy0 + dy : sy1 + dy, sx0 + dx : sx1 + dx] = layer[sy0:sy1, sx0:sx1]
    return out


def _composite(layers: list[np.ndarray], size: tuple[int, int]) -> np.ndarray:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    for layer in layers:
        canvas = Image.alpha_composite(canvas, Image.fromarray(layer, "RGBA"))
    return np.asarray(canvas)


def run_motion_check(project_id: str) -> MotionCheckReport:
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)

    # 可視パーツのレイヤーを z 昇順(背面から)でロードし、チェック解像度へ縮小
    ordered = [p for p in sorted(plan.parts, key=lambda p: p.z_order) if p.visible]
    layers: list[tuple[Part, np.ndarray]] = []
    scale = 1.0
    size: tuple[int, int] | None = None
    for part in ordered:
        png = paths.layer_png(part.id)
        if not png.exists():
            continue
        with Image.open(png) as img:
            img = img.convert("RGBA")
            if size is None:
                long_edge = max(img.size)
                scale = min(1.0, CHECK_LONG_EDGE / long_edge)
                size = (round(img.width * scale), round(img.height * scale))
            if img.size != size:
                img = img.resize(size, Image.BILINEAR)
            layers.append((part, np.asarray(img).copy()))
    if not layers or size is None:
        raise ValueError("レイヤーが未生成です。先にレイヤー生成を実行してください")

    base = _composite([arr for _, arr in layers], size)
    base_opaque = base[:, :, 3] > 8
    figure_px = int(base_opaque.sum()) or 1

    amp = max(4, round(size[0] * AMPLITUDE_RATIO))
    shifts = [(amp, 0), (-amp, 0), (0, amp // 2)]

    entries: list[MotionHole] = []
    hole_accum = np.zeros(base_opaque.shape, bool)
    checked = 0
    for idx, (part, _) in enumerate(layers):
        if not _is_movable(part):
            continue
        checked += 1
        for dx, dy in shifts:
            moved = [
                _shift_layer(arr, dx, dy) if i == idx else arr
                for i, (_, arr) in enumerate(layers)
            ]
            comp = _composite(moved, size)
            holes = base_opaque & (comp[:, :, 3] <= 8)
            hole_px = int(holes.sum())
            if hole_px > 0:
                hole_accum |= holes
                entries.append(MotionHole(
                    part_id=part.id,
                    shift=[dx, dy],
                    hole_px=hole_px,
                    hole_ratio=hole_px / figure_px,
                ))

    # ヒートマップ: 元画像の上に穴をマゼンタで重ねる
    overlay = base.copy()
    overlay[hole_accum] = [255, 0, 200, 255]
    paths.previews_dir.mkdir(parents=True, exist_ok=True)
    preview = paths.previews_dir / "motion_check.png"
    Image.fromarray(overlay, "RGBA").save(preview, format="PNG")

    report = MotionCheckReport(
        amplitude_px=amp,
        checked_parts=checked,
        entries=sorted(entries, key=lambda e: -e.hole_px),
        preview_path=paths.rel(preview),
    )
    (paths.json_dir / "motion_check.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info(
        "モーションチェック完了: %s 可動%d件 / 穴%d件",
        project_id, checked, len(entries),
    )
    return report
