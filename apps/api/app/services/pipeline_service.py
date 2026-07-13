"""全自動仕上げパイプライン。

「アップロード済みの画像から、品質処理を全部通した状態」までを
ワンボタン(1ジョブ)で実行する:

1. 解析(未解析の場合のみ。既存のパーツ設計・ユーザー編集は壊さない)
2. セグメンテーション一括実行
3. レイヤー一括生成
4. 未割当ピクセル整合(resolve_orphans)
5. 欠損補完(needs_inpaint_under パーツ)
6. モーション穴の自動補完(検出 → 焼き込み → 再チェック)
7. 品質チェック → 自動修正 → 最終チェック

実行サマリは json/pipeline_summary.json に保存する。
"""
from __future__ import annotations

from typing import Callable, Optional

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.paths import ProjectPaths

logger = get_logger(__name__)

ProgressCb = Optional[Callable[[float, str], None]]


class PipelineStep(BaseModel):
    step: str
    detail: str


class PipelineSummary(BaseModel):
    steps: list[PipelineStep] = Field(default_factory=list)
    final_score: int = 0
    motion_holes_after: int = 0
    orphan_px_after: int = 0


def run_auto_pipeline(project_id: str, progress_cb: ProgressCb = None) -> PipelineSummary:
    from app.services import (
        analysis_service,
        inpaint_service,
        layer_service,
        ownership_service,
        quality_service,
        segmentation_service,
    )
    from app.services.motion_check_service import fix_motion_holes

    paths = ProjectPaths(project_id)
    summary = PipelineSummary()

    def prog(ratio: float, message: str) -> None:
        if progress_cb:
            progress_cb(ratio, message)

    def add(step: str, detail: str) -> None:
        summary.steps.append(PipelineStep(step=step, detail=detail))
        logger.info("パイプライン[%s] %s: %s", project_id, step, detail)

    # 1. 解析(既存のパーツ設計があれば尊重する)
    prog(0.0, "解析")
    if not paths.parts_json.exists():
        from app.ai.mock_analyzer import get_analyzer

        analyzer_name = get_analyzer("auto").name  # Claude が使えれば Claude
        plan = analysis_service.analyze(project_id, analyzer_name)
        add("解析", f"{analyzer_name} アナライザーで {len(plan.parts)} パーツを設計しました")
    else:
        add("解析", "既存のパーツ設計を使用します(再解析なし)")

    # 2. セグメンテーション
    results = segmentation_service.run_all(
        project_id, progress_cb=lambda r, m: prog(0.02 + 0.38 * r, f"セグメンテーション: {m}")
    )
    failed = [pid for pid, warns in results.items() if any("失敗" in w for w in warns)]
    add("セグメンテーション", f"{len(results)} パーツ実行"
        + (f"(失敗 {len(failed)} 件)" if failed else ""))

    # 3. レイヤー生成
    layers = layer_service.generate_all_layers(
        project_id, progress_cb=lambda r, m: prog(0.40 + 0.20 * r, f"レイヤー生成: {m}")
    )
    add("レイヤー生成", f"{len(layers)} 枚生成しました")

    # 4. 未割当ピクセル整合
    prog(0.62, "未割当ピクセル整合")
    orphan = ownership_service.resolve_orphans(project_id)
    summary.orphan_px_after = orphan.orphan_px_after
    add("未割当ピクセル整合",
        f"{orphan.orphan_px_before}px → {orphan.orphan_px_after}px"
        f"({len(orphan.assignments)} パーツへ編入)")

    # 5. 欠損補完
    prog(0.70, "欠損補完")
    inpaint = inpaint_service.run_inpaint(project_id)
    done = [r for r in inpaint if r.status == "done"]
    add("欠損補完", f"{len(done)} 件実行 / {len(inpaint) - len(done)} 件スキップ")

    # 6. モーション穴の自動補完
    prog(0.78, "モーション穴の補完")
    motion = fix_motion_holes(project_id)
    summary.motion_holes_after = len(motion.report_after.entries)
    add("モーション穴補完",
        f"{len(motion.fills)} 件焼き込み / 残り穴 {summary.motion_holes_after} 件")

    # 7. 品質チェック → 自動修正 → 最終チェック
    prog(0.88, "品質チェック")
    first = quality_service.run_quality_check(project_id)
    fixable = [i for i in first.issues if i.auto_fix_available]
    if fixable:
        prog(0.93, "自動修正")
        applied, final = quality_service.apply_autofix(project_id)
        add("自動修正", f"{len(applied)} 件適用(スコア {first.overall_score}"
                        f" → {final.overall_score})")
    else:
        final = first
        add("品質チェック", f"自動修正の対象なし(スコア {final.overall_score})")
    summary.final_score = final.overall_score

    (paths.json_dir / "pipeline_summary.json").write_text(
        summary.model_dump_json(indent=2), encoding="utf-8"
    )
    prog(1.0, f"完了(最終スコア {summary.final_score} 点)")
    return summary
