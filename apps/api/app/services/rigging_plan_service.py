"""parts.json からリギング設計書(Markdown)をテンプレート生成する。"""
from __future__ import annotations

from collections import defaultdict

from app.core.paths import ProjectPaths
from app.models.parts import PartsPlan
from app.models.project import UserPreferences
from app.services.project_service import load_parts, load_project

_STANDARD_PARAMS = [
    ("ParamAngleX", "顔の左右回転", "-30〜30"),
    ("ParamAngleY", "顔の上下回転", "-30〜30"),
    ("ParamAngleZ", "顔の傾き", "-30〜30"),
    ("ParamEyeLOpen", "左目 開閉", "0〜1"),
    ("ParamEyeROpen", "右目 開閉", "0〜1"),
    ("ParamEyeBallX", "目線 左右", "-1〜1"),
    ("ParamEyeBallY", "目線 上下", "-1〜1"),
    ("ParamBrowLY", "左眉 上下", "-1〜1"),
    ("ParamBrowRY", "右眉 上下", "-1〜1"),
    ("ParamMouthOpenY", "口 開閉", "0〜1"),
    ("ParamMouthForm", "口 変形", "-1〜1"),
    ("ParamBodyAngleX", "体の左右回転", "-10〜10"),
    ("ParamBodyAngleY", "体の上下", "-10〜10"),
    ("ParamBodyAngleZ", "体の傾き", "-10〜10"),
    ("ParamBreath", "呼吸", "0〜1"),
]


def render_rigging_plan(plan: PartsPlan, preferences: UserPreferences) -> str:
    by_deformer: dict[str, list] = defaultdict(list)
    for p in plan.parts:
        by_deformer[p.live2d.parent_deformer_hint or "(未割当)"].append(p)

    physics_parts = [p for p in plan.parts if p.live2d.physics_hint]

    lines: list[str] = []
    a = lines.append
    a("# リギング設計書(自動生成)")
    a("")
    a(f"- 品質レベル: {preferences.quality_level.value}")
    a(f"- 使用目的: {preferences.target}")
    a(f"- パーツ数: {len(plan.parts)}")
    a("")
    a("> 本書は AutoLive2D Layer Studio によるテンプレート生成です。")
    a("> Live2D Cubism Editor での作業指針としてご利用ください。")
    a("")
    a("## 1. 推奨パラメータ一覧")
    a("")
    a("| パラメータID | 用途 | 推奨範囲 |")
    a("|---|---|---|")
    for pid, desc, rng in _STANDARD_PARAMS:
        a(f"| {pid} | {desc} | {rng} |")
    a("")
    a("## 2. デフォーマ構成(親子構造)")
    a("")
    a("推奨ルート構造:")
    a("```")
    a("Root")
    a("├── D_Body(体全体の回転)")
    a("│   ├── D_Arm_L / D_Arm_R")
    a("│   └── D_Head(顔XYZ角度)")
    a("│       ├── D_Hair_Front / D_Hair_Side_L / D_Hair_Side_R / D_Hair_Back")
    a("│       ├── D_Eye_L / D_Eye_R / D_Brow_L / D_Brow_R")
    a("│       └── D_Mouth")
    a("```")
    a("")
    a("### パーツ割り当て")
    a("")
    for deformer in sorted(by_deformer):
        a(f"**{deformer}**")
        for p in sorted(by_deformer[deformer], key=lambda x: -x.z_order):
            usage = ", ".join(p.live2d.usage) or "-"
            a(f"- `{p.id}`({p.name_jp}): {usage}")
        a("")
    a("## 3. メッシュ分割方針")
    a("")
    a("- 髪の房・揺れもの: 縦方向に細かく(変形の滑らかさ優先)")
    a("- 顔ベース: 標準密度。輪郭に沿って頂点を配置")
    a("- 目・口の小パーツ: 自動メッシュで十分。ハイライトは低密度")
    a("- 塗り足し領域までメッシュを含めること(欠け防止)")
    a("")
    a("## 4. 物理演算設定方針")
    a("")
    if physics_parts:
        a("| パーツ | 物理ヒント | 設定目安 |")
        a("|---|---|---|")
        for p in physics_parts:
            hint = p.live2d.physics_hint
            preset = "揺れ幅 小・減衰 高" if "soft" in hint else "振り子標準"
            a(f"| {p.name_jp}(`{p.id}`) | {hint} | {preset} |")
    else:
        a("物理演算対象のパーツはありません。")
    a("")
    a("## 5. 表情差分案")
    a("")
    if preferences.expression_variants:
        a("- 笑顔(目を弧に・口角上げ)")
        a("- 驚き(目を大きく・口を開く)")
        a("- 照れ(頬に赤み・目線をそらす)")
        a("- ジト目(まぶたを半分下げる)")
    else:
        a("表情差分は要件に含まれていません(preferences.expression_variants = false)。")
    a("")
    a("## 6. VTube Studio 向け注意点")
    a("")
    a("- ParamEyeBallX/Y はトラッキング感度を 0.7 前後から調整")
    a("- 口パクは ParamMouthOpenY にマイク入力をバインド")
    a(f"- 口の仕様: {preferences.mouth_type.value}")
    a("- 物理演算はエディタ側でフレームレート 60 を前提に調整")
    a("- 出力時は .model3.json と一緒にテクスチャアトラスを 2048px 以上で")
    a("")
    a("## 7. 作業手順")
    a("")
    a("1. `live2d_import.psd` を Cubism Editor で開く")
    a("2. レイヤー構造を確認(グループ = デフォーマ計画に対応)")
    a("3. 各パーツにメッシュを生成(上記方針)")
    a("4. デフォーマを親子構造どおりに作成")
    a("5. パラメータをバインド(セクション1の一覧)")
    a("6. 物理演算を設定(セクション4)")
    a("7. VTube Studio へエクスポートして動作確認")
    return "\n".join(lines)


def generate_rigging_plan(project_id: str) -> str:
    """rigging_plan.md を生成・保存し、相対パスを返す。"""
    project = load_project(project_id)
    plan = load_parts(project_id)
    md = render_rigging_plan(plan, project.preferences)
    paths = ProjectPaths(project_id)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)
    paths.rigging_plan_md.write_text(md, encoding="utf-8")
    return paths.rel(paths.rigging_plan_md)
