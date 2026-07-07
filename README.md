# AutoLive2D Layer Studio

1枚のキャラクター立ち絵画像から、Live2D Cubism で読み込みやすい高精度なパーツ分け PSD を生成する、human-in-the-loop 型の Live2D 素材分け支援ソフトウェア。

> **重要な設計原則**: 本プロジェクトは `.moc3` / `.cmo3` を独自生成しません。
> 最初の価値は「1枚絵から Live2D 用の高精度 PSD を作ること」です。
> Live2D 化(リギング自動化)は後続フェーズで扱います。

## 現在のフェーズ

**Step 1: 全体設計** — 設計ドキュメントを `docs/` に整備中。実装は設計承認後に開始します。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/01_overview.md](docs/01_overview.md) | プロジェクト理解まとめ / MVP範囲 / 将来拡張範囲 |
| [docs/02_architecture.md](docs/02_architecture.md) | アーキテクチャ提案(抽象化戦略・処理パイプライン) |
| [docs/03_directory_structure.md](docs/03_directory_structure.md) | ディレクトリ構成 |
| [docs/04_data_models.md](docs/04_data_models.md) | 主要データモデル(Pydantic / TypeScript 共有スキーマ) |
| [docs/05_api.md](docs/05_api.md) | FastAPI エンドポイント一覧 |
| [docs/06_ui.md](docs/06_ui.md) | フロントエンド画面設計 |
| [docs/07_implementation_plan.md](docs/07_implementation_plan.md) | 実装タスク分解(Step 1〜13) |
| [docs/08_risks.md](docs/08_risks.md) | リスクと対策 |

## 予定技術スタック

- **Frontend**: React + TypeScript + Vite + Zustand + Tailwind CSS + Konva.js
- **Desktop**: Tauri(第一候補)/ Electron(代替)
- **Backend**: Python + FastAPI + Pydantic + Pillow + OpenCV + numpy + psd-tools + SQLite
- **AI / セグメンテーション**: MVP はモック実装。SAM2 / VLM / Inpainting API へ差し替え可能な抽象化を実装
- **Testing**: pytest / Vitest / 画像スナップショットテスト

## 出力物(最終形)

- Live2D Cubism 用 PSD(`live2d_import.psd`)
- 各パーツ PNG / マスク PNG / 合成プレビュー PNG
- `parts.json` / `project.json` / `segmentation_tasks.json` / `quality_report.json`
- `rigging_plan.md`(リギング設計書)
