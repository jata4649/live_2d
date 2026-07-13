# AutoLive2D Layer Studio — AI高精度セットアップ(Windows)
#
# 使い方(リポジトリのルートで、PowerShell から):
#   powershell -ExecutionPolicy Bypass -File scripts\setup_ai.ps1          # NVIDIA GPU あり
#   powershell -ExecutionPolicy Bypass -File scripts\setup_ai.ps1 -Cpu     # GPU なし
#
# 導入するもの:
#   - anthropic     … Claude 解析(パーツ設計を実画像ベースで行う)
#   - torch (CUDA)  … SAM2 の実行基盤
#   - sam2          … Segment Anything Model 2(高精度セグメンテーション)
#   - rembg         … アニメ特化背景除去(背景つきJPG対応)
#
# 終了後に診断が表示されます。Claude を使うには別途 API キーが必要です:
#   setx ANTHROPIC_API_KEY "sk-ant-..."   (新しいターミナルから有効)

param([switch]$Cpu)

$ErrorActionPreference = "Stop"

Write-Host "=== 1/4 Claude API クライアント (anthropic) ===" -ForegroundColor Cyan
python -m pip install anthropic

Write-Host "=== 2/4 torch $(if ($Cpu) { '(CPU)' } else { '(CUDA 12.1)' }) ===" -ForegroundColor Cyan
if ($Cpu) {
    python -m pip install torch
} else {
    python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
}

Write-Host "=== 3/4 SAM2 ===" -ForegroundColor Cyan
python -m pip install "git+https://github.com/facebookresearch/sam2.git"

Write-Host "=== 4/4 背景除去 (rembg) ===" -ForegroundColor Cyan
python -m pip install rembg onnxruntime

if (-not $Cpu) {
    Write-Host "SAM2 を GPU で動かすには環境変数を設定してください:" -ForegroundColor Yellow
    Write-Host '  setx ALS_SAM2_DEVICE "cuda"'
}

Write-Host "=== 診断 ===" -ForegroundColor Cyan
Push-Location (Join-Path $PSScriptRoot "..\apps\api")
python scripts/check_ai.py
Pop-Location
