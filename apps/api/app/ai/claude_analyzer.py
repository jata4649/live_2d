"""ClaudeAnalyzer: Claude API による実AIパーツ解析。

CharacterAnalyzer インターフェースの Phase 2 実装。
- 画像は内部処理用の縮小版(working.png)を送信し、bbox を元解像度へ換算する
- プロンプトは prompts/*.md からロード(ハードコード禁止)
- 出力は parts.json スキーマの JSON。Pydantic 検証に失敗した場合は
  エラー内容をフィードバックして 1 回だけ再試行する
- ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN が無い環境では利用不可として扱う
  (MVP のモック動作には影響しない)
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from app.ai.base import CharacterAnalyzer
from app.ai.mock_analyzer import MockAnalyzer
from app.ai.prompt_manager import prompt_manager
from app.ai.templates.standard_parts import build_standard_parts
from app.core.logging import get_logger
from app.models.parts import Part, PartsPlan
from app.models.project import UserPreferences
from app.models.segmentation import QuestionList, SegmentationTaskList

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-opus-4-8"
MAX_OUTPUT_TOKENS = 64000

_SCHEMA_INSTRUCTION = """
出力は必ず以下の parts.json スキーマに準拠した JSON のみとしてください。
コードフェンスや説明文は不要です。

{
  "version": "1.0",
  "parts": [
    {
      "id": "snake_case の一意ID(英小文字・数字・_ のみ。左右は _l / _r)",
      "name_jp": "日本語表示名",
      "name_en": "English Name (PSDレイヤー名として一意)",
      "group": "Hair/Front のような / 区切り階層",
      "z_order": 120,
      "visible": true,
      "locked": false,
      "required": true,
      "part_type": "face|eye|eyebrow|mouth|hair|body|clothes|accessory|other",
      "visual_description": "見た目の説明",
      "segmentation": {
        "method": "manual_box",
        "bbox": [x, y, w, h],
        "positive_points": [],
        "negative_points": [],
        "text_prompt": "english segmentation prompt"
      },
      "files": {"mask_path": "masks/{id}_mask.png", "layer_path": "layers/{id}.png"},
      "live2d": {
        "usage": ["ParamAngleX"],
        "parent_deformer_hint": "D_Head",
        "physics_hint": ""
      },
      "processing": {
        "overlap_bleed_px": 8,
        "edge_feather_px": 1,
        "needs_inpaint_under": true,
        "inpaint_reason": "理由"
      },
      "quality": {"priority": "low|normal|high", "manual_review_required": false, "score": null}
    }
  ]
}

bbox は添付画像のピクセル座標([x, y, w, h])で、パーツを確実に含む範囲を指定してください。
"""


class AnalyzerUnavailableError(Exception):
    """API キー未設定など、この analyzer が利用できない状態。"""


def claude_available() -> tuple[bool, str]:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True, ""
    return False, "ANTHROPIC_API_KEY が設定されていません"


class ClaudeAnalyzer(CharacterAnalyzer):
    name = "claude"

    def __init__(self, model: Optional[str] = None, client: Any = None):
        if client is None:
            available, reason = claude_available()
            if not available:
                raise AnalyzerUnavailableError(
                    f"Claude 解析は利用できません: {reason}。"
                    "モック解析(mock)を使用してください"
                )
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or os.environ.get("ALS_CLAUDE_MODEL", DEFAULT_MODEL)
        # 質問・セグメンテーションタスクは決定的な処理で十分なため Mock を再利用
        self._fallback = MockAnalyzer()

    # ------------------------------------------------------------ API 呼び出し

    def _call(self, prompt: str, image_path: Optional[Path] = None) -> str:
        """テキスト(+画像)を送り、テキスト応答を返す。長い出力に備えて streaming。"""
        content: list[dict] = []
        if image_path is not None:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(
                        image_path.read_bytes()
                    ).decode("utf-8"),
                },
            })
        content.append({"type": "text", "text": prompt})

        with self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": content}],
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            raise ValueError(
                "Claude が解析リクエストを処理できませんでした(refusal)。"
                "画像の内容を確認するか、モック解析を使用してください"
            )
        return "".join(
            block.text for block in message.content if block.type == "text"
        )

    # ------------------------------------------------------------ 解析本体

    def analyze_character_image(
        self, image_path: Path, user_preferences: UserPreferences
    ) -> PartsPlan:
        # 送信は縮小版(あれば)。bbox は元解像度へ換算する。
        send_path, scale = self._pick_image(image_path)
        with Image.open(send_path) as img:
            send_w, send_h = img.size

        standard = build_standard_parts(user_preferences, send_w, send_h)
        prompt = prompt_manager.load(
            "parts_plan_prompt.md",
            {
                "image_analysis_json": "(添付画像を直接分析してください)",
                "user_preferences_json": user_preferences.model_dump_json(),
                "standard_parts_json": json.dumps(
                    [
                        {"id": p.id, "name_jp": p.name_jp, "group": p.group,
                         "z_order": p.z_order}
                        for p in standard
                    ],
                    ensure_ascii=False,
                ),
            },
        )
        prompt += (
            f"\n\n画像サイズ: {send_w} x {send_h} px\n" + _SCHEMA_INSTRUCTION
        )

        text = self._call(prompt, image_path=send_path)
        plan = self._parse_plan_with_retry(text, prompt, send_path)
        return self._rescale_plan(plan, scale)

    def _parse_plan_with_retry(
        self, text: str, prompt: str, image_path: Path
    ) -> PartsPlan:
        try:
            return self._parse_plan(text)
        except Exception as e:
            logger.warning("parts.json 検証に失敗。再試行します: %s", e)
            retry_prompt = (
                f"{prompt}\n\n前回の出力は次のエラーで検証に失敗しました:\n{e}\n"
                "エラーを修正した JSON のみを出力してください。"
            )
            return self._parse_plan(self._call(retry_prompt, image_path=image_path))

    @staticmethod
    def _parse_plan(text: str) -> PartsPlan:
        data = extract_json(text)
        plan = PartsPlan.model_validate(data)
        # ファイルパスの補完(AIが省略した場合)
        for p in plan.parts:
            if not p.files.mask_path:
                p.files.mask_path = f"masks/{p.id}_mask.png"
            if not p.files.layer_path:
                p.files.layer_path = f"layers/{p.id}.png"
        return plan

    @staticmethod
    def _pick_image(image_path: Path) -> tuple[Path, float]:
        """working.png があればそれを使い、元画像への拡大率を返す。"""
        working = image_path.parent / "working.png"
        if not working.exists():
            return image_path, 1.0
        with Image.open(image_path) as full, Image.open(working) as small:
            scale = full.width / small.width
        return working, scale

    @staticmethod
    def _rescale_plan(plan: PartsPlan, scale: float) -> PartsPlan:
        if scale == 1.0:
            return plan
        for part in plan.parts:
            bbox = part.segmentation.bbox
            if bbox:
                part.segmentation.bbox = [round(v * scale) for v in bbox]
            part.segmentation.positive_points = [
                [round(x * scale), round(y * scale)]
                for x, y in part.segmentation.positive_points
            ]
            part.segmentation.negative_points = [
                [round(x * scale), round(y * scale)]
                for x, y in part.segmentation.negative_points
            ]
        return plan

    # ------------------------------------------------------------ その他の生成

    def generate_questions(self, user_preferences: UserPreferences) -> QuestionList:
        # 質問は静的セットで十分(動的質問は Phase 2.5)
        return self._fallback.generate_questions(user_preferences)

    def generate_segmentation_tasks(
        self, parts_plan: PartsPlan
    ) -> SegmentationTaskList:
        return self._fallback.generate_segmentation_tasks(parts_plan)

    def generate_rigging_plan(
        self, parts_plan: PartsPlan, user_preferences: UserPreferences
    ) -> str:
        prompt = prompt_manager.load(
            "rigging_plan_prompt.md",
            {
                "parts_json": parts_plan.model_dump_json(),
                "user_preferences_json": user_preferences.model_dump_json(),
            },
        )
        return self._call(prompt)


def extract_json(text: str) -> dict:
    """コードフェンスや前後の文章を取り除いて JSON を抽出する。"""
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("応答から JSON を抽出できませんでした")
    return json.loads(text[start : end + 1])
