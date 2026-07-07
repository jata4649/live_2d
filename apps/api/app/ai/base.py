"""CharacterAnalyzer 抽象基底クラス。

実AI(Claude / GPT / Gemini / ローカルVLM)への差し替えは
このインターフェースの実装追加のみで行う。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.parts import PartsPlan
from app.models.project import UserPreferences
from app.models.segmentation import QuestionList, SegmentationTaskList


class CharacterAnalyzer(ABC):
    name: str = "base"

    @abstractmethod
    def analyze_character_image(
        self, image_path: Path, user_preferences: UserPreferences
    ) -> PartsPlan:
        """立ち絵画像からパーツ設計を生成する。"""

    @abstractmethod
    def generate_questions(self, user_preferences: UserPreferences) -> QuestionList:
        """ユーザーへのヒアリング質問を生成する。"""

    @abstractmethod
    def generate_segmentation_tasks(
        self, parts_plan: PartsPlan
    ) -> SegmentationTaskList:
        """パーツ設計からセグメンテーションタスクを生成する。"""

    @abstractmethod
    def generate_rigging_plan(
        self, parts_plan: PartsPlan, user_preferences: UserPreferences
    ) -> str:
        """リギング設計書(Markdown)を生成する。"""
