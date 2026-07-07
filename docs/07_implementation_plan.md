# 07. 実装タスク分解

指定された Step 1〜13 の順序を厳守する。各 Step に完了条件(DoD)を定義。

## Step 1: 全体設計 ✅(本ドキュメント群)

- DoD: docs/ に設計一式がコミットされ、レビュー可能な状態。

## Step 2: ディレクトリ構成

- モノレポ骨格作成(`apps/api`, `apps/desktop`, `packages/shared`, `outputs/` gitignore)
- `pyproject.toml`(Python 3.11+, FastAPI, Pydantic v2, Pillow, OpenCV, numpy, psd-tools, pytest)
- `package.json`(Vite + React + TS + Zustand + Tailwind + react-konva + Vitest)
- prompts/ に7つのプロンプトテンプレート配置
- DoD: `uvicorn main:app` と `npm run dev` が空アプリとして起動する。

## Step 3: スキーマ設計

- `app/models/` に Pydantic モデル一式(docs/04 準拠)
- JSON Schema エクスポートスクリプト + TS 型生成(`packages/shared`)
- DoD: `pytest` でモデルのシリアライズ/デシリアライズが通り、TS 型が生成される。

## Step 4: FastAPI 最小実装

- `core/config.py` / `core/paths.py`(ProjectPaths)/ `core/logging.py`
- SQLite 接続 + projects / jobs テーブル
- エラーハンドラ(統一エラー形式)、CORS(localhost)
- DoD: `/api/v1/projects`(空一覧)と `/healthz` が応答。

## Step 5: 画像アップロードとプロジェクト保存

- `POST /projects`(multipart)→ ディレクトリ作成 → original 保存
- `image_processing/normalize.py`: PNG化 / sRGB / RGBA化 / 作業サイズ生成 / アルファなし時の背景除去候補マスク
- project.json 生成、`GET/DELETE /projects` 完成、files 配信ルーター
- DoD: pytest で「JPG入稿 → normalized.png が RGBA/sRGB/同解像度」を検証。

## Step 6: MockAnalyzer

- `ai/base.py`(CharacterAnalyzer ABC)+ `ai/templates/standard_parts.py`(標準VTuberパーツテンプレート: Face/Eye_L/Eye_R/Mouth/Hair/Body/Clothes/Accessories)
- preferences に応じたテンプレート調整(例: mouth_type=open_close なら teeth/tongue を required=false)
- 初期 bbox は画像サイズ比の推定配置(顔上半分に目、中央に鼻口 等の粗い比率)
- `POST /analyze` → parts.json、`GET/PUT /parts`、静的 `QuestionList` の `generate-questions`
- `prompt_manager.py`(prompts/ ロード + 変数埋め込み — 実AIはまだ呼ばない)
- DoD: analyze 実行で 40〜60 パーツの parts.json が生成され、PUT で編集が永続化。

## Step 7: ManualBoxSegmenter

- `segmentation/base.py`(Segmenter ABC + MaskResult)+ `registry.py`
- `MockSegmenter`(bbox 矩形マスク)
- `ManualBoxSegmenter`(bbox 内をアルファ/色ベースで簡易切り抜き: GrabCut or 色クラスタリング + アルファ考慮)
- `segmentation/tasks` 生成、`run`(Job化)/ `run/{part_id}`(同期)
- `image_processing/masks.py`: fill_holes / remove_small_noise / dilate / erode / smooth_edges
- DoD: 固定テスト画像でマスクPNG(8bit grayscale・同サイズ)が生成され、refinement が各々ピクセル検証される。

## Step 8: レイヤーPNG生成

- `layer_service.py`: normalized.png × mask → RGBA レイヤー(元画像と同キャンバス・位置ずれなし)
- overlap_bleed_px 膨張 / edge_feather_px ぼかしの適用
- `inpaint/task_planner.py`: needs_inpaint_under → inpaint_tasks.json
- DoD: 「全レイヤーのアルファ和 ≒ 元画像アルファ」のスナップショットテスト。

## Step 9: 合成プレビュー

- `composite.py`(z_order 降順合成)/ `difference.py`(差分画像 + 統計)
- `POST /preview/composite`
- DoD: 全パーツマスクが完全被覆のケースで差分ゼロを確認するテスト。

## Step 10: 品質チェック初期実装

- `quality_service.py`: docs/04 のチェックコード11種をルールベース実装
- スコアリング(severity 重み付き減点方式)、quality_report.json 出力
- DoD: 意図的に壊したフィクスチャ(重複名・空レイヤー等)で各コードが検出される。

## Step 11: PSD出力

- `exporters/base.py`(PsdExporter ABC)
- `PsdToolsExporter`: グループ階層 + z_order 順 + RGB/8bit、生成後ラウンドトリップ検証
- `LayerZipExporter`(manifest.json 付き)、`PhotoshopScriptExporter`(JSX 生成、フォールバック)
- export API(実行前 quality チェック、score<50 は 409)
- DoD: 生成 PSD を psd-tools で再読込し、レイヤー名/階層/順序/サイズが一致。

## Step 12: React UI MVP

順序: API クライアント + 型 → Home → Upload → Interview → PartsEditor → MaskEditor → Preview → Export

- 12a. 型付き API クライアント、jobStore(ポーリング)
- 12b. Home / Upload / Interview
- 12c. PartsEditor(ツリー / Konva キャンバス bbox 編集 / 詳細パネル / ログ)
- 12d. MaskEditor(ブラシ / Undo/Redo / refine / 保存)
- 12e. Preview(合成 / 差分 / A/B)
- 12f. Export(レポート表示 / 出力ボタン群)
- DoD: ブラウザで Upload → Interview → analyze → bbox 調整 → マスク生成/修正 → プレビュー → PSD 出力が一気通貫で完了。

## Step 13: README

- セットアップ(Python/Node)、起動方法(api / desktop 個別 + 同時起動スクリプト)、開発コマンド、テスト実行方法
- Cubism Editor への PSD 読み込み手順ガイド
- DoD: クリーンな環境で README の手順どおりに MVP が起動する。

## 見積り目安(1人開発想定)

| Step | 目安 |
|---|---|
| 2-4(骨格+スキーマ+API基盤) | 2-3日 |
| 5-6(画像+解析) | 2-3日 |
| 7-9(セグメンテーション+レイヤー+プレビュー) | 3-4日 |
| 10-11(品質+PSD) | 3-4日 |
| 12(UI) | 5-7日 |
| 13 + バッファ | 1-2日 |

合計: 約3〜4週間で MVP。
