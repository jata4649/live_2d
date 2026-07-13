"""MockAnalyzer: 外部AIなしで動作する CharacterAnalyzer 実装。

標準VTuberパーツテンプレートと静的な質問セットを返す。
実AI導入時はこのクラスを差し替えるだけでよい。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image

from app.ai.base import CharacterAnalyzer
from app.ai.templates.standard_parts import build_standard_parts
from app.models.parts import PartsPlan
from app.models.project import UserPreferences
from app.models.segmentation import (
    Question,
    QuestionList,
    RefinementParams,
    SegmentationTask,
    SegmentationTaskList,
)

_STATIC_QUESTIONS: list[Question] = [
    Question(id="q001", category="quality",
             question="品質レベルはどれにしますか?",
             choices=["簡易", "標準", "高品質", "商用品質"],
             maps_to="preferences.quality_level"),
    Question(id="q002", category="target",
             question="使用目的を教えてください。",
             choices=["VTube Studio", "nizima", "ゲーム", "配信", "その他"],
             maps_to="preferences.target"),
    Question(id="q003", category="face",
             question="顔の可動域はどのくらいにしますか?",
             choices=["小", "中", "大"],
             maps_to="preferences.face_range"),
    Question(id="q004", category="mouth",
             question="口は「あいうえお」差分まで作りますか?それとも開閉のみでよいですか?",
             choices=["開閉のみ", "あいうえお対応", "歌唱向けに細かく", "おまかせ"],
             maps_to="preferences.mouth_type"),
    Question(id="q005", category="eye",
             question="目の仕様を選んでください。",
             choices=["瞬きのみ", "目線移動あり", "笑顔目・ジト目まで"],
             maps_to="preferences.eye_type"),
    Question(id="q006", category="hair", type="boolean",
             question="髪揺れ(前髪・横髪・後ろ髪・アホ毛)の物理を入れますか?",
             choices=["はい", "いいえ"],
             maps_to="preferences.hair_physics"),
    Question(id="q007", category="accessory", type="multi_choice",
             question="揺らしたい装飾があれば選んでください。",
             choices=["ヘアピン", "イヤリング", "ネックレス", "メガネ", "帽子", "なし"],
             maps_to="preferences.accessories"),
    Question(id="q008", category="arm", type="boolean",
             question="腕を動かしますか?",
             choices=["はい", "いいえ"],
             maps_to="preferences.arm_movement"),
    Question(id="q009", category="expression", type="boolean",
             question="表情差分は必要ですか?",
             choices=["はい", "いいえ"],
             maps_to="preferences.expression_variants"),
]


class MockAnalyzer(CharacterAnalyzer):
    name = "mock"

    def analyze_character_image(
        self, image_path: Path, user_preferences: UserPreferences
    ) -> PartsPlan:
        import numpy as np

        from app.core.config import settings

        with Image.open(image_path) as img:
            width, height = img.size
            rgba = np.asarray(img.convert("RGBA"))
        parts = build_standard_parts(user_preferences, width, height)

        # テンプレートは「人物がキャンバス全体を占める」前提の比率のため、
        # 実際の人物範囲を検出して bbox を再マッピングする(精度向上)
        if settings.fit_template:
            self._fit_to_character(parts, rgba)
        return PartsPlan(version="1.0", parts=parts)

    @staticmethod
    def _fit_to_character(parts, rgba) -> None:
        from app.image_processing.character_bounds import character_bbox, fit_bbox

        target = character_bbox(rgba)
        if target is None:
            return
        boxes = [p.segmentation.bbox for p in parts if p.segmentation.bbox]
        if not boxes:
            return
        # テンプレート自身が想定している人物範囲(全パーツbboxの外接矩形)
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        template_extent = [x0, y0, x1 - x0, y1 - y0]
        for p in parts:
            if p.segmentation.bbox:
                p.segmentation.bbox = fit_bbox(
                    p.segmentation.bbox, template_extent, target
                )

    def generate_questions(self, user_preferences: UserPreferences) -> QuestionList:
        return QuestionList(questions=list(_STATIC_QUESTIONS))

    def generate_segmentation_tasks(
        self, parts_plan: PartsPlan
    ) -> SegmentationTaskList:
        tasks = []
        for part in parts_plan.parts:
            if part.locked:
                continue
            tasks.append(
                SegmentationTask(
                    task_id=str(uuid.uuid4()),
                    part_id=part.id,
                    method=part.segmentation.method,
                    bbox=part.segmentation.bbox,
                    positive_points=part.segmentation.positive_points,
                    negative_points=part.segmentation.negative_points,
                    text_prompt=part.segmentation.text_prompt,
                    expected_output=part.files.mask_path or f"masks/{part.id}_mask.png",
                    refinement=RefinementParams(
                        dilate_px=max(0, part.processing.overlap_bleed_px // 4),
                    ),
                )
            )
        return SegmentationTaskList(tasks=tasks)

    def generate_rigging_plan(
        self, parts_plan: PartsPlan, user_preferences: UserPreferences
    ) -> str:
        from app.services.rigging_plan_service import render_rigging_plan

        return render_rigging_plan(parts_plan, user_preferences)


def get_analyzer(name: str = "mock") -> CharacterAnalyzer:
    """Analyzer レジストリ。gpt / gemini / ローカルVLM は将来ここに追加する。"""
    if name == "mock":
        return MockAnalyzer()
    if name == "claude":
        from app.ai.claude_analyzer import ClaudeAnalyzer

        return ClaudeAnalyzer()
    raise ValueError(f"未対応の analyzer です: {name}(利用可能: mock, claude)")


def list_analyzers() -> list[dict]:
    """利用可能な analyzer と利用可否を返す(UI のセレクタ用)。"""
    from app.ai.claude_analyzer import claude_available

    available, reason = claude_available()
    return [
        {
            "name": "mock",
            "label": "標準テンプレート(オフライン)",
            "available": True,
            "reason": "",
        },
        {
            "name": "claude",
            "label": "Claude AI 解析",
            "available": available,
            "reason": reason,
        },
    ]
