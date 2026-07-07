# 05. API 設計(FastAPI)

ベースURL: `http://127.0.0.1:8787/api/v1`(ポートは config で変更可)

共通仕様:
- エラーは `{ "code": "PROJECT_NOT_FOUND", "message": "日本語の説明", "detail": {...} }`
- 長時間処理は `202 Accepted` + `Job` を返し、`GET /jobs/{job_id}` でポーリング
- 画像ファイルは `files` ルーターで配信(キャッシュ制御: `no-cache`、編集直後の反映のため)

## Project

| Method | Path | 内容 | 返り値 |
|---|---|---|---|
| POST | `/projects` | プロジェクト作成(multipart: `name`, `image`) | `Project` |
| GET | `/projects` | 一覧(更新日時降順) | `Project[]` |
| GET | `/projects/{project_id}` | 詳細 | `Project` |
| DELETE | `/projects/{project_id}` | 削除(ディレクトリごと) | 204 |
| PUT | `/projects/{project_id}/preferences` | ヒアリング回答保存 | `Project` |

## Image

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/upload-image` | 画像差し替え(multipart) |
| POST | `/projects/{project_id}/normalize-image` | 正規化実行(PNG化・sRGB・RGBA・作業サイズ生成・背景除去候補) |

## Analysis

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/analyze` | CharacterAnalyzer 実行 → parts.json 生成(MVP: MockAnalyzer)。body: `{analyzer?: "mock"}` |
| GET | `/projects/{project_id}/parts` | parts.json 取得 |
| PUT | `/projects/{project_id}/parts` | parts.json 全体更新(バリデーション: id一意・group形式・z_order) |
| POST | `/projects/{project_id}/generate-questions` | ヒアリング質問リスト生成 → `QuestionList` |

## Segmentation

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/segmentation/tasks` | parts.json → segmentation_tasks.json 生成 |
| POST | `/projects/{project_id}/segmentation/run` | 全タスク実行(202 + Job) |
| POST | `/projects/{project_id}/segmentation/run/{part_id}` | 単一パーツ実行(同期・小さいので即応答) |
| GET | `/projects/{project_id}/masks/{part_id}` | マスクPNG取得(image/png) |
| PUT | `/projects/{project_id}/masks/{part_id}` | 編集済みマスクPNG書き戻し(body: image/png)。サイズ検証必須 |
| POST | `/projects/{project_id}/masks/{part_id}/refine` | 膨張/収縮/穴埋め/ノイズ除去/ぼかし。body: `RefinementParams` |

## Layer / Preview

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/layers/generate` | 全パーツのレイヤーPNG生成(202 + Job) |
| POST | `/projects/{project_id}/layers/generate/{part_id}` | 単一パーツ生成(同期) |
| GET | `/projects/{project_id}/layers/{part_id}` | レイヤーPNG取得 |
| POST | `/projects/{project_id}/preview/composite` | 合成プレビュー + 差分プレビュー生成 → パスと差分統計を返す |

## Quality

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/quality/check` | 品質チェック実行 → quality_report.json |
| GET | `/projects/{project_id}/quality/report` | 最新レポート取得 |
| POST | `/projects/{project_id}/quality/autofix/{issue_index}` | `auto_fix_available: true` の issue を自動修正(Phase 1.5) |

## Export

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/export/psd` | PSD出力(202 + Job)。body: `{exporter?: "psd_tools"}`。失敗時フォールバック情報を Job.message に記録 |
| POST | `/projects/{project_id}/export/layers-zip` | layers.zip + manifest.json |
| POST | `/projects/{project_id}/export/rigging-plan` | rigging_plan.md 生成 |
| GET | `/projects/{project_id}/exports/{filename}` | 出力ファイルダウンロード |

## Inpaint(MVPは計画生成のみ)

| Method | Path | 内容 |
|---|---|---|
| POST | `/projects/{project_id}/inpaint/plan` | needs_inpaint_under から inpaint_tasks.json 生成 |
| GET | `/projects/{project_id}/inpaint/tasks` | タスク一覧取得 |

## Jobs / Files

| Method | Path | 内容 |
|---|---|---|
| GET | `/jobs/{job_id}` | ジョブ状態取得(ポーリング用) |
| GET | `/projects/{project_id}/files/{path:path}` | プロジェクト内ファイル配信(source/previews等。パストラバーサル対策必須) |

## バリデーション方針

- `PUT /parts`: part_id 重複、`files.*_path` の命名規則、bbox が画像範囲内、z_order の型、を Pydantic + サービス層で二重検証。
- `PUT /masks/{part_id}`: 受信PNGが 8bit grayscale かつ正規化画像と同サイズであることを検証。不一致は 422 で理由を日本語返却。
- export 系: 実行前に quality_check を内部呼び出しし、`overall_score < 50` の場合は `409` + レポートを返す(`force: true` で強制出力可)。
