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


def _load_check_layers(
    project_id: str,
) -> tuple[list[tuple[Part, np.ndarray]], tuple[int, int], float]:
    """可視パーツのレイヤーを z 昇順でロードし、チェック解像度へ縮小する。"""
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)
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
    return layers, size, scale


def run_motion_check(project_id: str) -> MotionCheckReport:
    paths = ProjectPaths(project_id)
    layers, size, _ = _load_check_layers(project_id)

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


# ---------------------------------------------------------------- 穴の自動補完

class MotionFill(BaseModel):
    moved_part_id: str
    target_part_id: str
    filled_px: int  # フル解像度での補完ピクセル数


class MotionFixReport(BaseModel):
    fills: list[MotionFill] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    report_after: MotionCheckReport


def fix_motion_holes(project_id: str) -> MotionFixReport:
    """モーションチェックで見つかった穴を、下のレイヤーへ塗って埋める。

    可動パーツごとに全シフトの穴を合算し、フル解像度へ拡大した領域を
    「そのパーツより背面で、穴に最も広く隣接するレイヤー」へ
    OpenCV inpaint(TELEA)で焼き込む。マスクは変更しない
    (欠損補完と同じ「レイヤーへの焼き込み」方針)。
    """
    import cv2

    paths = ProjectPaths(project_id)
    layers, size, scale = _load_check_layers(project_id)

    base = _composite([arr for _, arr in layers], size)
    base_opaque = base[:, :, 3] > 8
    amp = max(4, round(size[0] * AMPLITUDE_RATIO))
    shifts = [(amp, 0), (-amp, 0), (0, amp // 2)]

    # 可動パーツごとの穴(チェック解像度)
    holes_by_part: dict[str, np.ndarray] = {}
    for idx, (part, _) in enumerate(layers):
        if not _is_movable(part):
            continue
        accum = np.zeros(base_opaque.shape, bool)
        for dx, dy in shifts:
            moved = [
                _shift_layer(arr, dx, dy) if i == idx else arr
                for i, (_, arr) in enumerate(layers)
            ]
            comp = _composite(moved, size)
            accum |= base_opaque & (comp[:, :, 3] <= 8)
        if accum.any():
            holes_by_part[part.id] = accum

    fills: list[MotionFill] = []
    skipped: list[str] = []
    if holes_by_part:
        # フル解像度のレイヤーを z 昇順でロード
        full: dict[str, np.ndarray] = {}
        order: list[Part] = [p for p, _ in layers]
        full_size: tuple[int, int] | None = None
        for part in order:
            with Image.open(paths.layer_png(part.id)) as img:
                arr = np.asarray(img.convert("RGBA")).copy()
            full[part.id] = arr
            full_size = (arr.shape[1], arr.shape[0])
        assert full_size is not None
        fw, fh = full_size
        margin = max(2, round(1.0 / scale)) if scale < 1.0 else 2
        kernel = np.ones((3, 3), np.uint8)

        for idx, part in enumerate(order):
            if part.id not in holes_by_part:
                continue
            hole = holes_by_part[part.id].astype(np.uint8) * 255
            hole_full = cv2.resize(hole, (fw, fh), interpolation=cv2.INTER_NEAREST)
            hole_full = cv2.dilate(hole_full, kernel, iterations=margin) > 127

            # 補完先: このパーツより背面で、穴の周囲に最も広く接するレイヤー
            ring = (
                cv2.dilate(hole_full.astype(np.uint8), kernel, iterations=8) > 0
            ) & ~hole_full
            best_id: str | None = None
            best_contact = 0
            for lower in order[:idx]:
                contact = int(((full[lower.id][:, :, 3] > 8) & ring).sum())
                if contact > best_contact:
                    best_contact = contact
                    best_id = lower.id
            if best_id is None or best_contact < 30:
                skipped.append(
                    f"{part.id}: 補完先レイヤーが見つかりませんでした"
                )
                continue

            target = full[best_id]
            region = hole_full & ~(target[:, :, 3] > 8)
            if not region.any():
                continue
            # inpaint の「既知領域」に透明ピクセルの色ゴミが混ざらないよう、
            # 領域近傍の透明部もまとめて未知として塗り、region のみ反映する
            unknown = region | (
                (cv2.dilate(region.astype(np.uint8), kernel, iterations=8) > 0)
                & ~(target[:, :, 3] > 8)
            )
            bgr = cv2.cvtColor(target[:, :, :3], cv2.COLOR_RGB2BGR)
            painted = cv2.inpaint(
                bgr, unknown.astype(np.uint8) * 255, 5, cv2.INPAINT_TELEA
            )
            target[region, :3] = cv2.cvtColor(painted, cv2.COLOR_BGR2RGB)[region]
            target[region, 3] = 255
            Image.fromarray(target, "RGBA").save(
                paths.layer_png(best_id), format="PNG"
            )
            fills.append(MotionFill(
                moved_part_id=part.id,
                target_part_id=best_id,
                filled_px=int(region.sum()),
            ))
            logger.info(
                "モーション穴補完: %s の下(%s)へ %dpx 焼き込み",
                part.id, best_id, int(region.sum()),
            )

    return MotionFixReport(
        fills=fills, skipped=skipped, report_after=run_motion_check(project_id)
    )
