# 03. ディレクトリ構成

## 1. リポジトリ構成(モノレポ)

```
live_2d/
├── README.md
├── docs/                          # 設計ドキュメント(本ディレクトリ)
│   └── ...
├── apps/
│   ├── api/                       # Python バックエンド
│   │   ├── main.py                # uvicorn エントリポイント
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── config.py      # 設定(ポート・outputs ルート・feature flags)
│   │   │   │   ├── paths.py       # ProjectPaths — パス一元管理(唯一の真実)
│   │   │   │   └── logging.py
│   │   │   ├── models/            # Pydantic スキーマ
│   │   │   │   ├── project.py
│   │   │   │   ├── parts.py
│   │   │   │   ├── segmentation.py
│   │   │   │   ├── quality.py
│   │   │   │   ├── export.py
│   │   │   │   └── jobs.py
│   │   │   ├── services/          # ユースケース層
│   │   │   │   ├── project_service.py
│   │   │   │   ├── image_service.py
│   │   │   │   ├── analysis_service.py
│   │   │   │   ├── segmentation_service.py
│   │   │   │   ├── mask_service.py
│   │   │   │   ├── layer_service.py
│   │   │   │   ├── preview_service.py
│   │   │   │   ├── quality_service.py
│   │   │   │   ├── export_service.py
│   │   │   │   └── rigging_plan_service.py
│   │   │   ├── ai/                # CharacterAnalyzer 抽象化
│   │   │   │   ├── base.py
│   │   │   │   ├── mock_analyzer.py
│   │   │   │   ├── prompt_manager.py
│   │   │   │   └── templates/
│   │   │   │       └── standard_parts.py   # 標準VTuberパーツテンプレート
│   │   │   ├── segmentation/      # Segmenter 抽象化
│   │   │   │   ├── base.py
│   │   │   │   ├── registry.py
│   │   │   │   ├── mock_segmenter.py
│   │   │   │   ├── manual_box_segmenter.py
│   │   │   │   └── sam2_segmenter.py        # Phase 2(スタブを先に置く)
│   │   │   ├── exporters/         # PsdExporter 抽象化
│   │   │   │   ├── base.py
│   │   │   │   ├── psd_tools_exporter.py
│   │   │   │   ├── photoshop_script_exporter.py
│   │   │   │   └── layer_zip_exporter.py
│   │   │   ├── inpaint/           # Inpainter 抽象化(MVPはタスク生成のみ)
│   │   │   │   ├── base.py
│   │   │   │   └── task_planner.py
│   │   │   ├── image_processing/  # 純関数群(ndarray in/out)
│   │   │   │   ├── normalize.py   # PNG化・sRGB・RGBA・リサイズ
│   │   │   │   ├── masks.py       # 膨張・収縮・穴埋め・ノイズ除去
│   │   │   │   ├── alpha.py       # アルファ操作・透明フチ対策
│   │   │   │   ├── composite.py   # レイヤー合成
│   │   │   │   ├── difference.py  # 元画像との差分
│   │   │   │   └── cleanup.py     # 境界ぼかし・エッジ処理
│   │   │   ├── routers/
│   │   │   │   ├── projects.py
│   │   │   │   ├── image.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── segmentation.py
│   │   │   │   ├── layers.py
│   │   │   │   ├── quality.py
│   │   │   │   ├── export.py
│   │   │   │   └── files.py       # プロジェクトファイル静的配信
│   │   │   ├── prompts/           # AIプロンプトテンプレート(外部APIへ渡せる形)
│   │   │   │   ├── character_analysis_prompt.md
│   │   │   │   ├── user_interview_prompt.md
│   │   │   │   ├── parts_plan_prompt.md
│   │   │   │   ├── segmentation_instruction_prompt.md
│   │   │   │   ├── psd_structure_prompt.md
│   │   │   │   ├── quality_check_prompt.md
│   │   │   │   └── rigging_plan_prompt.md
│   │   │   ├── db/
│   │   │   │   ├── database.py    # SQLite 接続
│   │   │   │   └── repository.py  # projects / jobs テーブル
│   │   │   └── tests/
│   │   │       ├── fixtures/      # 小型テスト画像
│   │   │       ├── test_image_processing/
│   │   │       ├── test_services/
│   │   │       └── test_exporters/
│   └── desktop/                   # フロントエンド + デスクトップシェル
│       ├── package.json
│       ├── src-tauri/             # Tauri シェル(サイドカー起動のみ)
│       └── src/
│           ├── main.tsx
│           ├── api/               # APIクライアント(型付き fetch ラッパ)
│           ├── stores/            # Zustand ストア
│           │   ├── projectStore.ts
│           │   ├── partsStore.ts
│           │   ├── maskEditorStore.ts
│           │   └── jobStore.ts
│           ├── pages/
│           │   ├── HomePage.tsx
│           │   ├── UploadPage.tsx
│           │   ├── InterviewPage.tsx
│           │   ├── PartsEditorPage.tsx
│           │   ├── MaskEditorPage.tsx
│           │   ├── PreviewPage.tsx
│           │   └── ExportPage.tsx
│           ├── components/
│           │   ├── parts-tree/
│           │   ├── canvas/        # Konva.js ラッパ(BBoxLayer, MaskBrushLayer, ...)
│           │   ├── panels/
│           │   └── common/
│           ├── types/             # packages/shared から生成された型を import
│           └── utils/
├── packages/
│   └── shared/
│       ├── schemas/               # JSON Schema(Pydantic からエクスポート)
│       └── types/                 # TypeScript 型(スキーマから自動生成)
└── outputs/                       # 実行時生成(gitignore)
    └── projects/
        └── {project_id}/          # 下記 2. 参照
```

## 2. プロジェクト保存構造(実行時)

```
outputs/projects/{project_id}/
├── source/
│   ├── original.png               # 元画像(必ず無変換で保存)
│   └── normalized.png             # sRGB / RGBA / PNG 正規化済み
│   └── working_{size}.png         # 内部処理用縮小版(長辺基準)
├── masks/
│   └── {part_id}_mask.png         # 8bit grayscale
├── layers/
│   └── {part_id}.png              # RGBA・元画像と同キャンバスサイズ
├── previews/
│   ├── composite_preview.png
│   └── difference_preview.png
├── exports/
│   ├── live2d_import.psd
│   ├── layers.zip
│   └── import_script.jsx          # Photoshop フォールバック用
├── json/
│   ├── project.json
│   ├── parts.json
│   ├── segmentation_tasks.json
│   ├── inpaint_tasks.json
│   └── quality_report.json
└── docs/
    └── rigging_plan.md
```

## 3. 型共有の方針

1. **Pydantic モデルが唯一のスキーマ定義元**(`apps/api/app/models/`)。
2. CI/スクリプトで `model_json_schema()` → `packages/shared/schemas/*.json` へエクスポート。
3. `json-schema-to-typescript` で `packages/shared/types/*.ts` を生成。
4. フロントは生成された型のみを import。手書きの重複型定義を禁止。
