# AutoLive2D Layer Studio

1枚のキャラクター立ち絵画像から、Live2D Cubism で読み込みやすい高精度なパーツ分け PSD を生成する、human-in-the-loop 型の Live2D 素材分け支援ソフトウェア。

> **設計原則**: 本プロジェクトは `.moc3` / `.cmo3` を生成しません。
> 最初の価値は「1枚絵から Live2D 用の高精度 PSD を作ること」です。
> AI が9割の作業を行い、最後の1割(マスク修正・確認)を人間が行います。

## MVP でできること

1. 立ち絵画像(PNG/JPG/WEBP)のアップロードとプロジェクト管理
2. ヒアリング(品質レベル・口/目の仕様・髪揺れ・装飾など)
3. AI パーツ設計 — MockAnalyzer が標準VTuberパーツ(最大約60)を回答に応じた粒度で生成
4. パーツ一覧編集(ツリー / bbox のキャンバス編集 / z_order / グループ)
5. セグメンテーション — アルファ・GrabCut・矩形の簡易切り抜き(SAM2 は差し替え可能な設計)
6. マスクのブラシ修正(追加/消し・Undo/Redo・膨張/収縮/穴埋め/ノイズ除去/ぼかし)
7. レイヤーPNG生成(塗り足し膨張 + 透明フチ対策)
8. 合成プレビューと元画像との差分表示
9. ルールベース品質チェック(11種・100点スコアリング)
10. **PSD 出力**(グループ階層 / RLE圧縮 / psd-tools による再読込検証付き)
    - 失敗時は layers.zip + Photoshop JSX スクリプトへ自動フォールバック
11. リギング設計書(`rigging_plan.md`)の生成

## セットアップ

必要環境: Python 3.11+ / Node.js 20+

```bash
# バックエンド
cd apps/api
pip install -e '.[dev]'          # または: pip install fastapi 'uvicorn[standard]' pydantic pillow opencv-python-headless numpy scikit-image psd-tools python-multipart pytest httpx

# フロントエンド
cd ../desktop
npm install
```

## 起動

ターミナルを2つ使います。

```bash
# 1) バックエンド API (http://127.0.0.1:8787)
cd apps/api
python3 -m uvicorn main:app --port 8787

# 2) フロントエンド (http://localhost:5173)
cd apps/desktop
npm run dev
```

ブラウザで http://localhost:5173 を開いてください。
`/api` へのリクエストは Vite が 8787 へプロキシします。

生成物は `outputs/projects/{project_id}/` に保存されます(masks / layers / previews / exports / json / docs)。

## テスト

```bash
# バックエンド(画像処理 / PSDラウンドトリップ / API一気通貫)
cd apps/api && python3 -m pytest app/tests

# フロントエンド
cd apps/desktop && npm test        # Vitest
npm run typecheck                  # tsc
```

## Claude AI 解析(オプション)

`ANTHROPIC_API_KEY` を設定してバックエンドを起動すると、ヒアリング画面で
「Claude AI 解析」を選択できます(未設定でもモック解析でフル動作します)。

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# pip install anthropic  (未導入の場合)
python3 -m uvicorn main:app --port 8787
```

- 画像は内部処理用の縮小版を送信し、bbox は元解像度へ自動換算されます
- モデルは既定で `claude-opus-4-8`(`ALS_CLAUDE_MODEL` で変更可)
- 出力 JSON は Pydantic で検証し、失敗時はエラーをフィードバックして1回再試行します

## SAM2 セグメンテーション(オプション)

torch と SAM2 をインストールすると、パーツ編集画面で「SAM2(矩形/ポイントプロンプト)」を
選択できます(未導入でも簡易切り抜きへ自動フォールバックします)。

```bash
pip install torch
pip install "git+https://github.com/facebookresearch/sam2.git"
```

- モデルは初回実行時に Hugging Face Hub から自動ダウンロード
  (既定: `facebook/sam2-hiera-tiny`、`ALS_SAM2_MODEL` で変更可)
- デバイスは `ALS_SAM2_DEVICE`(既定 `cpu`、GPU があれば `cuda`)
- 可用性は `GET /api/v1/segmenters` で確認できます

## Cubism Editor への読み込み

1. 出力画面から `live2d_import.psd` をダウンロード
2. Live2D Cubism Editor で「ファイル → 開く」
3. グループ階層 = デフォーマ計画に対応(`docs/rigging_plan.md` を参照)
4. 品質レポートが70点未満の場合はマスク修正後の再出力を推奨

## アーキテクチャ概要

```
React + TS + Vite + Zustand + Konva.js  (apps/desktop)
        │ REST (localhost)
FastAPI + Pillow + OpenCV + psd-tools   (apps/api)
        │
outputs/projects/{id}/  +  SQLite(一覧・ジョブ)
```

4つの差し替えポイントを抽象化しています(将来の高精度化のため):

| 抽象クラス | MVP実装 | 将来 |
|---|---|---|
| `CharacterAnalyzer` | MockAnalyzer(標準テンプレート)+ **ClaudeAnalyzer(実装済)** | GPT / Gemini / ローカルVLM |
| `Segmenter` | Mock / ManualBox(アルファ+GrabCut)+ **Sam2Segmenter(実装済)** | 外部API |
| `PsdExporter` | 自前PSDライター + JSXフォールバック | Photoshop UXP / Krita / ORA |
| `Inpainter` | Noop(inpaint_tasks.json 生成のみ) | Inpainting API / ローカルモデル |

AI プロンプトは `apps/api/app/prompts/*.md` に集約(実装へのハードコード禁止)。
スキーマは Pydantic が唯一の定義元で、`apps/api/scripts/export_schemas.py` が
`packages/shared/schemas/` へ JSON Schema をエクスポートします。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/01_overview.md](docs/01_overview.md) | 理解まとめ / MVP範囲 / 将来拡張(Phase 2〜4) |
| [docs/02_architecture.md](docs/02_architecture.md) | アーキテクチャ・抽象化戦略 |
| [docs/03_directory_structure.md](docs/03_directory_structure.md) | ディレクトリ構成 |
| [docs/04_data_models.md](docs/04_data_models.md) | データモデル / 品質チェックコード |
| [docs/05_api.md](docs/05_api.md) | API 一覧 |
| [docs/06_ui.md](docs/06_ui.md) | 画面設計 |
| [docs/07_implementation_plan.md](docs/07_implementation_plan.md) | 実装タスク分解 |
| [docs/08_risks.md](docs/08_risks.md) | リスクと対策 |
