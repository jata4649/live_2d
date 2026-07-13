#!/usr/bin/env bash
# AutoLive2D Layer Studio — AI高精度セットアップ(Mac / Linux)
#
# 使い方(リポジトリのルートで):
#   bash scripts/setup_ai.sh          # NVIDIA GPU あり(Linux)
#   bash scripts/setup_ai.sh --cpu    # GPU なし / Mac
set -euo pipefail

CPU=0
[[ "${1:-}" == "--cpu" ]] && CPU=1

echo "=== 1/4 Claude API クライアント (anthropic) ==="
python3 -m pip install anthropic

echo "=== 2/4 torch ==="
if [[ "$CPU" == "1" || "$(uname)" == "Darwin" ]]; then
  python3 -m pip install torch
else
  python3 -m pip install torch --index-url https://download.pytorch.org/whl/cu121
fi

echo "=== 3/4 SAM2 ==="
python3 -m pip install "git+https://github.com/facebookresearch/sam2.git"

echo "=== 4/4 背景除去 (rembg) ==="
python3 -m pip install rembg onnxruntime

echo "=== 診断 ==="
cd "$(dirname "$0")/../apps/api"
python3 scripts/check_ai.py
