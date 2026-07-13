"""ピクセル所有権ソルバー。

元画像の不透明ピクセルのうち「どのパーツのマスクにも入らなかった
孤児ピクセル」を、隣接関係と色の近さで最も自然なパーツへ自動編入する。

COMPOSITE_DIFF(合成と元画像の差分)の主因はこの孤児ピクセルと
マスク間の隙間なので、この整合パスで合成差分を原理的にほぼ0にできる。

割り当て単位は連結成分ごと(マスク境界の細い隙間・取りこぼした房など)。
候補パーツのスコア = 隣接ピクセル数 × 色の近さ(Lab 距離の指数減衰)。
どのパーツとも隣接しない孤島は、最近傍のマスクピクセルの所有者へ渡す。
"""
from __future__ import annotations

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.paths import ProjectPaths
from app.services import mask_service
from app.services.image_service import load_normalized_rgba
from app.services.project_service import load_parts

logger = get_logger(__name__)

# これ以下の面積(px)の成分はノイズとして最寄りへ黙って編入する
_TINY_COMPONENT_PX = 4
# 色の近さの減衰スケール(Lab 距離)
_COLOR_SCALE = 40.0


class OrphanAssignment(BaseModel):
    part_id: str
    components: int
    pixels: int


class OrphanReport(BaseModel):
    orphan_px_before: int
    orphan_px_after: int
    components: int
    assignments: list[OrphanAssignment] = Field(default_factory=list)
    layers_regenerated: list[str] = Field(default_factory=list)


def resolve_orphans(project_id: str) -> OrphanReport:
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)
    rgba = load_normalized_rgba(project_id)
    h, w = rgba.shape[:2]
    opaque = rgba[:, :, 3] > 8

    # 所有者マップ: z 昇順に塗り重ね、最前面のパーツが所有者になる
    ordered = [
        p for p in sorted(plan.parts, key=lambda p: p.z_order)
        if p.visible and paths.mask_png(p.id).exists()
    ]
    if not ordered:
        raise ValueError("マスクが未生成です。先にセグメンテーションを実行してください")

    owner = np.full((h, w), -1, np.int32)
    masks: dict[str, np.ndarray] = {}
    for idx, part in enumerate(ordered):
        m = mask_service.load_mask(project_id, part.id) > 127
        masks[part.id] = m
        owner[m] = idx

    orphans = opaque & (owner < 0)
    before = int(orphans.sum())
    report = OrphanReport(
        orphan_px_before=before, orphan_px_after=0, components=0
    )
    if before == 0:
        return report

    # 各パーツの代表色(Lab)。境界の影響を避けるため中心部を侵食で取る
    lab = cv2.cvtColor(
        rgba[:, :, :3].astype(np.float32) / 255.0, cv2.COLOR_RGB2Lab
    )
    kernel = np.ones((3, 3), np.uint8)
    mean_lab: dict[int, np.ndarray] = {}
    for idx, part in enumerate(ordered):
        core = cv2.erode(masks[part.id].astype(np.uint8), kernel, 3).astype(bool)
        if core.sum() < 50:
            core = masks[part.id]
        if core.any():
            mean_lab[idx] = lab[core].mean(axis=0)

    # 孤島用: 最近傍の所有済みピクセル(距離変換ラベル)
    inv = np.where(owner >= 0, 0, 255).astype(np.uint8)
    _, nearest_labels = cv2.distanceTransformWithLabels(
        inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    owned_coords = np.argwhere(inv == 0)

    n_comp, comp_map = cv2.connectedComponents(orphans.astype(np.uint8))
    report.components = n_comp - 1
    added: dict[str, int] = {}
    added_components: dict[str, int] = {}
    for ci in range(1, n_comp):
        comp = comp_map == ci
        comp_px = int(comp.sum())
        ring = cv2.dilate(comp.astype(np.uint8), kernel).astype(bool) & ~comp
        neighbor_owners = owner[ring]
        neighbor_owners = neighbor_owners[neighbor_owners >= 0]

        target_idx: int
        if neighbor_owners.size > 0 and comp_px > _TINY_COMPONENT_PX:
            comp_mean = lab[comp].mean(axis=0)
            candidates = np.unique(neighbor_owners)
            best_score = -1.0
            target_idx = int(candidates[0])
            for cand in candidates:
                contact = float((neighbor_owners == cand).sum())
                dist = (
                    float(np.linalg.norm(comp_mean - mean_lab[int(cand)]))
                    if int(cand) in mean_lab else _COLOR_SCALE
                )
                score = contact * float(np.exp(-dist / _COLOR_SCALE))
                if score > best_score:
                    best_score = score
                    target_idx = int(cand)
        elif neighbor_owners.size > 0:
            # 極小成分は接触数のみで決める
            vals, counts = np.unique(neighbor_owners, return_counts=True)
            target_idx = int(vals[counts.argmax()])
        else:
            # 孤島: 最近傍の所有済みピクセルの所有者へ
            ys, xs = np.nonzero(comp)
            ny, nx = owned_coords[nearest_labels[ys[0], xs[0]] - 1]
            target_idx = int(owner[ny, nx])

        part_id = ordered[target_idx].id
        masks[part_id] |= comp
        owner[comp] = target_idx
        added[part_id] = added.get(part_id, 0) + comp_px
        added_components[part_id] = added_components.get(part_id, 0) + 1

    # 変更されたマスクを保存し、レイヤーを再生成
    from app.services import layer_service

    parts_by_id = {p.id: p for p in ordered}
    for part_id, px in sorted(added.items(), key=lambda kv: -kv[1]):
        mask_service.save_mask(
            project_id, part_id, masks[part_id].astype(np.uint8) * 255
        )
        report.assignments.append(OrphanAssignment(
            part_id=part_id, components=added_components[part_id], pixels=px,
        ))
        if paths.layer_png(part_id).exists():
            layer_service.generate_layer(project_id, parts_by_id[part_id], rgba)
            report.layers_regenerated.append(part_id)

    report.orphan_px_after = int((opaque & (owner < 0)).sum())
    logger.info(
        "孤児ピクセル整合: %s %dpx → %dpx(%d成分 / %dパーツへ編入)",
        project_id, before, report.orphan_px_after,
        report.components, len(added),
    )
    return report
