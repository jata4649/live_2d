"""AI 環境ステータス診断 API。

Claude API / SAM2 / GPU / 背景除去の利用可否と、
足りないものの導入方法をフロントの1画面で確認できるようにする。
"""
from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["environment"])


@router.get("/environment")
def environment() -> dict:
    from app.ai.mock_analyzer import list_analyzers
    from app.image_processing.bg_removal import bg_removal_available
    from app.segmentation.registry import list_segmenters

    torch_info = {"installed": False, "cuda": False, "device_name": ""}
    try:
        import torch

        torch_info["installed"] = True
        if torch.cuda.is_available():
            torch_info["cuda"] = True
            torch_info["device_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass

    bg_ok, bg_reason = bg_removal_available()
    key_set = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )

    hints: list[str] = []
    analyzers = list_analyzers()
    claude = next((a for a in analyzers if a["name"] == "claude"), None)
    if claude and not claude["available"]:
        hints.append(
            "Claude 解析を有効化: pip install anthropic を実行し、"
            "環境変数 ANTHROPIC_API_KEY を設定してバックエンドを再起動"
        )
    segmenters = list_segmenters()
    sam2 = next((s for s in segmenters if s["method"] == "sam2_box"), None)
    if sam2 and not sam2["available"]:
        hints.append(
            "SAM2 を有効化: scripts/setup_ai.ps1(Windows)または "
            "scripts/setup_ai.sh を実行(torch + sam2 を導入)"
        )
    if torch_info["installed"] and not torch_info["cuda"]:
        hints.append(
            "GPU を使う場合: CUDA 版 torch を導入し ALS_SAM2_DEVICE=cuda を設定"
        )
    if not bg_ok:
        hints.append("背景つきJPG対応: pip install rembg onnxruntime")

    return {
        "analyzers": analyzers,
        "segmenters": segmenters,
        "bg_removal": {"available": bg_ok, "reason": bg_reason},
        "torch": torch_info,
        "anthropic_key_set": key_set,
        "sam2_device": os.environ.get("ALS_SAM2_DEVICE", "cpu"),
        "hints": hints,
    }
