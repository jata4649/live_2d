"""AI 環境の診断スクリプト。

apps/api で `python scripts/check_ai.py` を実行すると、
Claude / SAM2 / GPU / 背景除去の利用可否と対処方法を表示する。
(アプリの GET /api/v1/environment と同じ判定ロジック)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from app.ai.mock_analyzer import list_analyzers
    from app.image_processing.bg_removal import bg_removal_available
    from app.segmentation.registry import list_segmenters

    print()
    print("=== AutoLive2D Layer Studio — AI 環境診断 ===")
    print()

    claude = next(a for a in list_analyzers() if a["name"] == "claude")
    mark = "✓" if claude["available"] else "✗"
    print(f"[{mark}] Claude 解析: ", end="")
    print("利用可能" if claude["available"] else claude["reason"])

    sam2 = next(s for s in list_segmenters() if s["method"] == "sam2_box")
    mark = "✓" if sam2["available"] else "✗"
    print(f"[{mark}] SAM2 セグメンテーション: ", end="")
    print("利用可能" if sam2["available"] else sam2["reason"])

    try:
        import torch

        if torch.cuda.is_available():
            print(f"[✓] GPU: {torch.cuda.get_device_name(0)}"
                  "(ALS_SAM2_DEVICE=cuda を設定してください)")
        else:
            print("[−] GPU: CUDA が使えません(CPU で実行します)")
    except ImportError:
        print("[✗] torch: 未インストール")

    bg_ok, bg_reason = bg_removal_available()
    mark = "✓" if bg_ok else "✗"
    print(f"[{mark}] 背景除去 (rembg): ", end="")
    print("利用可能" if bg_ok else bg_reason)

    print()
    if not claude["available"]:
        print("→ Claude を使うには: ")
        print("   1. https://console.anthropic.com で API キーを作成")
        print('   2. setx ANTHROPIC_API_KEY "sk-ant-..."(Windows)/ '
              'export ANTHROPIC_API_KEY=...(Mac/Linux)')
        print("   3. バックエンドを再起動")
    print("バックエンド起動後、アプリの画面下部でも状態を確認できます。")


if __name__ == "__main__":
    main()
