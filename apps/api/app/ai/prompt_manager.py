"""prompts/*.md のロードと変数埋め込み。

実装クラスにプロンプトをハードコードせず、必ずここを経由する。
テンプレート変数は {{variable_name}} 形式。
"""
from __future__ import annotations

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptManager:
    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self.prompts_dir = prompts_dir

    def load(self, name: str, variables: dict[str, str] | None = None) -> str:
        path = self.prompts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"プロンプトが見つかりません: {name}")
        text = path.read_text(encoding="utf-8")
        for key, value in (variables or {}).items():
            text = text.replace("{{" + key + "}}", value)
        unresolved = re.findall(r"\{\{(\w+)\}\}", text)
        if unresolved:
            raise ValueError(f"未解決のテンプレート変数: {unresolved} in {name}")
        return text


prompt_manager = PromptManager()
