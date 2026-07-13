"""ルールベース品質チェック。

チェックコードは docs/04_data_models.md の11種に対応する。
スコアは 100 点から severity 重み付きで減点する方式。
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.core.paths import ProjectPaths
from app.image_processing.alpha import detect_edge_artifact
from app.models.parts import PartsPlan, PartType
from app.models.quality import IssueCode, QualityIssue, QualityReport, Severity
from app.services.preview_service import generate_previews
from app.services.project_service import load_parts, load_project, save_project

_PENALTY = {
    Severity.high: 15,
    Severity.medium: 7,
    Severity.low: 3,
    Severity.info: 0,
}

# 差分比率の許容値(これを超えると COMPOSITE_DIFF)
_DIFF_RATIO_WARN = 0.005
_DIFF_RATIO_HIGH = 0.05
# 半透明境界の異常色比率の許容値
_EDGE_ARTIFACT_RATIO = 0.30
# 混入検出: マスク内で「背面パーツの色」に近いピクセルがこの比率を超えると警告
_CONTAMINATION_RATIO = 0.20
# 混入検出: 2パーツの代表色(Lab)がこの距離未満なら色で判別できないため判定しない
_MIN_COLOR_SEPARATION = 25.0
# 混入判定のマージン(自分の代表色よりこの距離以上「相手寄り」なら混入とみなす)
_CONTAMINATION_MARGIN = 10.0


def run_quality_check(project_id: str) -> QualityReport:
    paths = ProjectPaths(project_id)
    plan = load_parts(project_id)
    issues: list[QualityIssue] = []

    issues += _check_duplicate_names(plan)
    issues += _check_lr_naming(plan)
    issues += _check_required_parts(plan)
    issues += _check_z_order(plan)
    issues += _check_files_and_layers(paths, plan)
    issues += _check_color_contamination(project_id, plan)
    issues += _check_composite_diff(project_id, plan)

    score = max(0, 100 - sum(_PENALTY[i.severity] for i in issues))
    report = QualityReport(
        overall_score=score,
        approved=score >= 70,
        issues=sorted(issues, key=lambda i: list(_PENALTY).index(i.severity)),
    )
    paths.quality_report_json.write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    project = load_project(project_id)
    project.status.quality_checked = True
    save_project(project)
    return report


def apply_autofix(project_id: str) -> tuple[list[dict], QualityReport]:
    """auto_fix_available な issue に自動修正を適用し、再チェック結果を返す。

    対応する修正:
    - EDGE_ARTIFACT: マスクを1px膨張 + 1pxぼかし → レイヤー再生成
    - INSUFFICIENT_BLEED: overlap_bleed_px を 4 に引き上げ → レイヤー再生成
    - Z_ORDER_ANOMALY: 後ろ髪より手前の z_order に引き上げ
    - COMPOSITE_DIFF: 孤児ピクセル整合(resolve_orphans)→ レイヤー再生成
    """
    from app.models.segmentation import RefinementParams
    from app.services import layer_service, mask_service
    from app.services.project_service import save_parts

    report = load_report(project_id) or run_quality_check(project_id)
    plan = load_parts(project_id)
    parts_by_id = {p.id: p for p in plan.parts}
    back_hair_max = max(
        (p.z_order for p in plan.parts
         if p.part_type == PartType.hair and "back" in p.id),
        default=0,
    )

    applied: list[dict] = []
    plan_dirty = False
    for issue in report.issues:
        if issue.code == IssueCode.COMPOSITE_DIFF and issue.auto_fix_available:
            from app.services.ownership_service import resolve_orphans

            try:
                r = resolve_orphans(project_id)
                applied.append({
                    "part_id": "", "code": issue.code.value,
                    "action": f"孤児ピクセル {r.orphan_px_before}px を "
                              f"{len(r.assignments)} パーツへ編入しました",
                })
            except Exception as e:
                applied.append({
                    "part_id": "", "code": issue.code.value,
                    "action": f"修正に失敗しました: {e}",
                })
            continue
        if not issue.auto_fix_available or not issue.part_id:
            continue
        part = parts_by_id.get(issue.part_id)
        if part is None:
            continue
        try:
            if issue.code == IssueCode.EDGE_ARTIFACT:
                mask_service.refine_mask(
                    project_id, part.id,
                    RefinementParams(
                        remove_small_noise=False, fill_holes=False,
                        smooth_edges=False, dilate_px=1, feather_px=1,
                    ),
                )
                layer_service.generate_layer(project_id, part)
                action = "マスクを1px膨張し境界をぼかしてレイヤーを再生成しました"
            elif issue.code == IssueCode.INSUFFICIENT_BLEED:
                part.processing.overlap_bleed_px = max(
                    4, part.processing.overlap_bleed_px
                )
                plan_dirty = True
                layer_service.generate_layer(project_id, part)
                action = "塗り足しを4pxに引き上げてレイヤーを再生成しました"
            elif issue.code == IssueCode.Z_ORDER_ANOMALY:
                part.z_order = back_hair_max + 10
                plan_dirty = True
                action = f"z_order を {part.z_order} に引き上げました"
            else:
                continue
            applied.append({
                "part_id": part.id, "code": issue.code.value, "action": action,
            })
        except Exception as e:  # 1件の失敗で全体を止めない
            applied.append({
                "part_id": part.id, "code": issue.code.value,
                "action": f"修正に失敗しました: {e}",
            })

    if plan_dirty:
        save_parts(project_id, plan)
    return applied, run_quality_check(project_id)


def load_report(project_id: str) -> QualityReport | None:
    paths = ProjectPaths(project_id)
    if not paths.quality_report_json.exists():
        return None
    return QualityReport.model_validate_json(
        paths.quality_report_json.read_text(encoding="utf-8")
    )


def _check_duplicate_names(plan: PartsPlan) -> list[QualityIssue]:
    issues = []
    seen: dict[str, str] = {}
    for p in plan.parts:
        layer_name = p.name_en or p.name_jp or p.id
        if layer_name in seen:
            issues.append(QualityIssue(
                severity=Severity.high,
                part_id=p.id,
                code=IssueCode.DUPLICATE_LAYER_NAME,
                message=f"レイヤー名「{layer_name}」が {seen[layer_name]} と重複しています",
                suggested_fix="表示名を一意になるよう変更してください",
            ))
        else:
            seen[layer_name] = p.id
    return issues


def _check_lr_naming(plan: PartsPlan) -> list[QualityIssue]:
    ids = {p.id for p in plan.parts}
    issues = []
    for pid in sorted(ids):
        if pid.endswith("_l"):
            twin = pid[:-2] + "_r"
            if twin not in ids:
                issues.append(QualityIssue(
                    severity=Severity.low,
                    part_id=pid,
                    code=IssueCode.LR_NAMING_MISMATCH,
                    message=f"{pid} に対応する右側パーツ({twin})がありません",
                    suggested_fix="左右非対称のキャラクターであれば問題ありません",
                ))
    return issues


def _check_required_parts(plan: PartsPlan) -> list[QualityIssue]:
    issues = []
    types_present = {p.part_type for p in plan.parts}
    for t, label in [(PartType.eye, "目"), (PartType.mouth, "口"), (PartType.hair, "髪")]:
        if t not in types_present:
            issues.append(QualityIssue(
                severity=Severity.high,
                part_id=None,
                code=IssueCode.MISSING_REQUIRED_PART,
                message=f"必須パーツ({label})が1つもありません",
                suggested_fix=f"{label}のパーツを追加してください",
            ))
    return issues


def _check_z_order(plan: PartsPlan) -> list[QualityIssue]:
    """ヒューリスティック: 後ろ髪より背面の目・口、前髪より前面の胴体などを検出。"""
    issues = []
    back_hair = [p for p in plan.parts if p.part_type == PartType.hair and "back" in p.id]
    face_parts = [p for p in plan.parts if p.part_type in (PartType.eye, PartType.mouth)]
    if back_hair and face_parts:
        max_back = max(p.z_order for p in back_hair)
        for fp in face_parts:
            if fp.z_order <= max_back:
                issues.append(QualityIssue(
                    severity=Severity.medium,
                    part_id=fp.id,
                    code=IssueCode.Z_ORDER_ANOMALY,
                    message=f"{fp.name_jp} が後ろ髪より背面にあります(z_order={fp.z_order})",
                    suggested_fix="z_order を後ろ髪より大きい値にしてください",
                    auto_fix_available=True,
                ))
    return issues


def _check_files_and_layers(paths: ProjectPaths, plan: PartsPlan) -> list[QualityIssue]:
    issues = []
    for p in plan.parts:
        mask_path = paths.mask_png(p.id)
        layer_path = paths.layer_png(p.id)
        if not mask_path.exists():
            issues.append(QualityIssue(
                severity=Severity.medium if p.required else Severity.low,
                part_id=p.id,
                code=IssueCode.MISSING_MASK,
                message=f"{p.name_jp} のマスクが未生成です",
                suggested_fix="セグメンテーションを実行してください",
            ))
            continue
        if not layer_path.exists():
            issues.append(QualityIssue(
                severity=Severity.low,
                part_id=p.id,
                code=IssueCode.FILE_MISSING,
                message=f"{p.name_jp} のレイヤーPNGが未生成です",
                suggested_fix="レイヤー生成を実行してください",
            ))
            continue
        with Image.open(layer_path) as img:
            rgba = np.asarray(img.convert("RGBA"))
        if rgba[:, :, 3].max() == 0:
            issues.append(QualityIssue(
                severity=Severity.medium,
                part_id=p.id,
                code=IssueCode.EMPTY_LAYER,
                message=f"{p.name_jp} のレイヤーが透明ピクセルのみです",
                suggested_fix="マスクを確認し、パーツ領域を塗ってください",
            ))
            continue
        artifact_ratio = detect_edge_artifact(rgba)
        if artifact_ratio > _EDGE_ARTIFACT_RATIO:
            issues.append(QualityIssue(
                severity=Severity.medium,
                part_id=p.id,
                code=IssueCode.EDGE_ARTIFACT,
                message=f"{p.name_jp} の境界に白/黒フチの可能性があります"
                        f"(異常色比率 {artifact_ratio:.0%})",
                suggested_fix="マスクを1px膨張し、境界を軽くぼかしてください",
                auto_fix_available=True,
            ))
        if p.processing.needs_inpaint_under and p.processing.overlap_bleed_px < 4:
            issues.append(QualityIssue(
                severity=Severity.low,
                part_id=p.id,
                code=IssueCode.INSUFFICIENT_BLEED,
                message=f"{p.name_jp} は補完が必要ですが塗り足しが {p.processing.overlap_bleed_px}px しかありません",
                suggested_fix="overlap_bleed_px を 4 以上にしてください",
                auto_fix_available=True,
            ))
    return issues


def _check_color_contamination(project_id: str, plan: PartsPlan) -> list[QualityIssue]:
    """色統計ベースの混入検出。

    「目のマスクに肌色が2割混ざっている」のような切り抜きミスを、
    パーツごとの代表色(マスク中心部の Lab 平均)との距離で検出する。

    判定対象は「A の bbox 中心を含む、より大きく背面にある B」との組のみ
    (目 vs 顔、口 vs 顔など)。下地パーツが上のパーツ領域を広めに含むのは
    Live2D 的に正しいため、背面側パーツ(B)は判定しない。
    """
    import cv2

    from app.services.image_service import load_normalized_rgba

    paths = ProjectPaths(project_id)
    candidates = [
        p for p in plan.parts
        if p.visible and p.segmentation.bbox and paths.mask_png(p.id).exists()
    ]
    if len(candidates) < 2:
        return []

    rgba = load_normalized_rgba(project_id)
    lab = cv2.cvtColor(
        (rgba[:, :, :3].astype(np.float32) / 255.0), cv2.COLOR_RGB2Lab
    )
    valid = rgba[:, :, 3] > 8

    # 各パーツのマスクと代表色(境界の影響を避けるため中心部を侵食で取る)
    kernel = np.ones((3, 3), np.uint8)
    stats: dict[str, tuple[np.ndarray, np.ndarray]] = {}  # id -> (mask, mean_lab)
    for p in candidates:
        with Image.open(paths.mask_png(p.id)) as img:
            mask = (np.asarray(img.convert("L")) > 127) & valid
        core = cv2.erode(mask.astype(np.uint8), kernel, iterations=3).astype(bool)
        if core.sum() < 100:
            core = mask
        if core.sum() < 100:
            continue
        stats[p.id] = (mask, lab[core].mean(axis=0))

    issues: list[QualityIssue] = []
    parts_by_id = {p.id: p for p in plan.parts}
    for a in candidates:
        if a.id not in stats:
            continue
        ax, ay, aw, ah = a.segmentation.bbox
        cx, cy = ax + aw // 2, ay + ah // 2
        mask_a, mean_a = stats[a.id]
        px: np.ndarray | None = None
        dist_own: np.ndarray | None = None
        worst: tuple[float, str] | None = None
        for b in candidates:
            if b.id == a.id or b.id not in stats:
                continue
            bx, by, bw, bh = b.segmentation.bbox
            # B は「A を含む・十分大きい・背面」のパーツのみ(目 vs 顔 等)
            if not (bx <= cx <= bx + bw and by <= cy <= by + bh):
                continue
            if bw * bh < 2 * aw * ah or b.z_order >= a.z_order:
                continue
            _, mean_b = stats[b.id]
            if float(np.linalg.norm(mean_a - mean_b)) < _MIN_COLOR_SEPARATION:
                continue  # 色が近すぎて判別できない
            if dist_own is None or px is None:
                px = lab[mask_a]
                dist_own = np.linalg.norm(px - mean_a, axis=1)
            dist_b = np.linalg.norm(px - mean_b, axis=1)
            ratio = float(
                (dist_b + _CONTAMINATION_MARGIN < dist_own).mean()
            )
            if ratio > _CONTAMINATION_RATIO and (worst is None or ratio > worst[0]):
                worst = (ratio, b.id)
        if worst is not None:
            b_part = parts_by_id[worst[1]]
            issues.append(QualityIssue(
                severity=Severity.medium,
                part_id=a.id,
                code=IssueCode.COLOR_CONTAMINATION,
                message=f"{a.name_jp} のマスクに {b_part.name_jp} の色が "
                        f"{worst[0]:.0%} 混入している疑いがあります",
                suggested_fix="背景ポイント(Alt+クリック)を混入箇所に追加して"
                              "再セグメント、またはマスク編集で除去してください",
            ))
    return issues


def _check_composite_diff(project_id: str, plan: PartsPlan) -> list[QualityIssue]:
    paths = ProjectPaths(project_id)
    has_layers = any(paths.layer_png(p.id).exists() for p in plan.parts)
    if not has_layers:
        return []  # レイヤー未生成は MISSING 系で報告済み
    result = generate_previews(project_id)
    if result.diff_pixel_ratio <= _DIFF_RATIO_WARN:
        return []
    severity = Severity.high if result.diff_pixel_ratio > _DIFF_RATIO_HIGH else Severity.medium
    return [QualityIssue(
        severity=severity,
        part_id=None,
        code=IssueCode.COMPOSITE_DIFF,
        message=f"合成プレビューが元画像と {result.diff_pixel_ratio:.1%} 異なります"
                f"({result.diff_pixel_count}px)",
        suggested_fix="自動修正(孤児ピクセル整合)を実行するか、"
                      "差分プレビューで欠けている箇所を確認して修正してください",
        auto_fix_available=True,
    )]
