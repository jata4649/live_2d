# AutoLive2D Layer Studio

1枚のキャラクター立ち絵画像から、Live2D Cubism で読み込みやすい高精度なパーツ分け PSD を生成する、human-in-the-loop 型の Live2D 素材分け支援ソフトウェア。

> **設計原則**: 本プロジェクトは `.moc3` / `.cmo3` を生成しません。
> 最初の価値は「1枚絵から Live2D 用の高精度 PSD を作ること」です。
> AI が9割の作業を行い、最後の1割(マスク修正・確認)を人間が行います。

## MVP でできること

0. **★ 全自動仕上げ** — セグメント → レイヤー → 未割当整合 → 欠損補完 → モーション穴補完 → 品質チェック → 自動修正 → 最終スコア、までワンボタン(1ジョブ)で実行
1. 立ち絵画像(PNG/JPG/WEBP)のアップロードとプロジェクト管理
2. ヒアリング(品質レベル・口/目の仕様・髪揺れ・装飾など)
3. AI パーツ設計 — MockAnalyzer が標準VTuberパーツ(最大約60)を回答に応じた粒度で生成し、**画像から検出した人物範囲へ自動フィット**
4. パーツ一覧編集(ツリー / bbox のキャンバス編集 / z_order / グループ)
5. セグメンテーション — 輪郭系はアルファ切り抜き、**目・口など内部の小パーツは色ベース(GrabCut)で自動分離**、大パーツは広め採用。**前景/背景ポイントを自動生成**(SAM2 導入時は自動で SAM2 経路へ昇格。キャンバスの Shift/Alt+クリックで手動追加も可能)
6. マスクのブラシ修正(追加/消し・**投げ縄**・**マジックワンド(色域選択・許容差/連結指定)**・**ブラシ硬さ**・Undo/Redo・膨張/収縮/穴埋め/ノイズ除去/ぼかし)+ **左右対称パーツへのミラーコピー** + **未割当ピクセル整合**(どのマスクにも入らなかったピクセルを隣接と色で最適なパーツへ自動編入 → 合成差分をほぼゼロに)
7. レイヤーPNG生成(塗り足し膨張 + 透明フチ対策)+ **欠損補完(最近傍フィル)**+ **ソフトエッジ化**(境界帯を guided filter で連続アルファに。髪の毛先のカクつき対策、`ALS_SOFT_EDGES=0` で無効化)
8. 合成プレビューと元画像との差分表示 + **疑似モーションチェック**(髪・装飾を揺らして「動かすと欠ける穴」を事前検出、マゼンタのヒートマップ表示)+ **穴の自動補完**(検出した穴を下のレイヤーへ OpenCV inpaint で焼き込み → 再チェックまでワンボタン)+ **モーション再生GIF**(揺れをアニメで確認)
9. ルールベース品質チェック(14種・100点スコアリング)+ **自動修正(auto-fix)**+ **色統計ベースの混入検出**(「目のマスクに肌色が2割混ざっている」等を自動指摘)。自動修正は左右ツインの**ミラーコピーによるマスク自動生成**・**断片化マスクの清掃**・**孤児ピクセル整合**まで対応
10. **PSD 出力**(グループ階層 / RLE圧縮 / psd-tools による再読込検証付き)
    - 失敗時は layers.zip + Photoshop JSX スクリプトへ自動フォールバック
11. リギング設計書(`rigging_plan.md`)の生成 — **Mermaid デフォーマツリー・ヒアリング反映の可動域・bbox比から算出した物理演算推奨値**つき
12. **OpenRaster (.ora) 出力** — Krita / GIMP でそのまま開けるオープン形式

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
- HF に到達できない環境ではローカルの checkpoint を使用可能:
  `ALS_SAM2_CHECKPOINT=/path/to/sam2.1_hiera_tiny.pt`(config は `ALS_SAM2_CONFIG`)
- 可用性は `GET /api/v1/segmenters` で確認できます

## 背景除去 — JPG 立ち絵対応(オプション)

背景つき JPG などアルファのない画像は、rembg(isnet-anime)を導入すると
アップロード時に人物アルファが自動生成され、透過PNG向けの高精度経路が
そのまま使えるようになります(未導入なら従来動作)。

```bash
pip install rembg onnxruntime
```

- モデル(約170MB)は初回に GitHub Releases から自動ダウンロード
- ネットワーク制限環境では `~/.u2net/isnet-anime.onnx` へ手動配置でも可
- `ALS_BG_REMOVAL=0` で無効化、`ALS_BG_REMOVAL_MODEL` でモデル変更

## デスクトップアプリ(Tauri・オプション)

ブラウザ運用のままでも全機能が使えますが、Tauri でデスクトップアプリ化できます。

前提: Rust ツールチェーン + OS ごとの WebView 依存
(Linux: `libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev` / macOS・Windows: 追加不要)

```bash
cd apps/desktop

# 開発(uvicorn は別ターミナルで起動しておく)
npm run tauri:dev

# 配布用ビルド(API は http://127.0.0.1:8787 固定でバンドル)
npm run tauri:build
```

- 環境変数 `ALS_API_DIR=/path/to/apps/api` を付けてアプリを起動すると、
  シェルが `python3 -m uvicorn main:app` を自動起動・終了時に停止します
  (未設定なら uvicorn を手動起動する開発スタイル)
- Python バックエンドの単一バイナリ化(PyInstaller + Tauri sidecar)は
  今後の配布フェーズで対応予定です(docs/08 R5)

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
| `PsdExporter` | 自前PSDライター + JSXフォールバック + **OpenRaster/.ora(実装済)** | Photoshop UXP |
| `Inpainter` | **最近傍フィル(実装済)**+ inpaint_tasks.json | Inpainting API / ローカルモデル |

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
