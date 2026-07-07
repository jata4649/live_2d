# 01. プロジェクト理解まとめ / MVP範囲 / 将来拡張範囲

## 1. プロジェクトの理解

### 1.1 何を作るか

**AutoLive2D Layer Studio** — 1枚のキャラクター立ち絵画像(PNG/JPG/WEBP)から、Live2D Cubism Editor で読み込みやすい高精度なパーツ分け PSD を半自動生成するデスクトップアプリケーション。

### 1.2 何を作らないか(非目標)

- `.moc3` / `.cmo3` の独自生成 — **絶対にやらない**
- Live2D Cubism Editor の代替ソフト
- 自動リギングの完全実装(MVP対象外。設計書 `rigging_plan.md` の生成まで)
- 完璧な AI 補完(MVP はフラグ立てと `inpaint_tasks.json` 生成まで)
- 外部 API キー必須の設計(モック実装で API キーなしでもフル動作)

### 1.3 コア思想: human-in-the-loop

「完全自動で一発完成」ではなく、**AI が9割・人間が最後の1割を確認修正**する設計。

理由: Live2D 制作では数ピクセルの欠け、髪の裏の未補完、目・口のレイヤー不足、レイヤー順ミスが品質を大きく左右する。自動処理の出力を必ずユーザーが確認・修正できる UI を用意する。

### 1.4 処理パイプライン(固定順序)

```
① AI自動解析 → ② ユーザーヒアリング → ③ パーツ設計 → ④ セグメンテーション
→ ⑤ マスク修正 → ⑥ 欠損補完 → ⑦ 品質チェック → ⑧ PSD出力 → ⑨ リギング設計書出力
```

各段階の成果物は JSON / PNG としてプロジェクトディレクトリに永続化され、どの段階からでもやり直し可能(非破壊編集)。

### 1.5 入力と出力

**入力**
- 正面立ち絵画像(PNG / JPG / WEBP)
- 品質レベル(簡易 / 標準 / 高品質 / 商用品質)
- 動かしたい箇所に関するヒアリング回答

**出力**
- `exports/live2d_import.psd` — Live2D Cubism 用 PSD
- `layers/*.png` — 各パーツ RGBA PNG(元画像と同キャンバスサイズ)
- `masks/*_mask.png` — 各パーツマスク(8bit grayscale PNG)
- `previews/composite_preview.png` / `difference_preview.png`
- `json/parts.json` / `project.json` / `segmentation_tasks.json` / `quality_report.json` / `inpaint_tasks.json`
- `docs/rigging_plan.md`

## 2. MVP の範囲

MVP で「動く」と定義する機能:

| # | 機能 | MVP実装レベル |
|---|---|---|
| 1 | 画像アップロード | 完全実装(PNG/JPG/WEBP → 正規化PNG) |
| 2 | プロジェクト作成・管理 | 完全実装(SQLite + ファイルシステム) |
| 3 | AIパーツ設計JSON生成 | **MockAnalyzer**(標準VTuberパーツテンプレート返却) |
| 4 | ヒアリング | 静的質問セット + user_preferences 保存 |
| 5 | パーツ一覧編集 | 完全実装(ツリー編集・z_order・グループ・追加削除) |
| 6 | パーツごとの矩形指定 | 完全実装(Konva.js キャンバス上で bbox 編集) |
| 7 | セグメンテーション | **ManualBoxSegmenter**(矩形+アルファ/色ベース簡易切り抜き)+ MockSegmenter |
| 8 | マスクPNG・レイヤーPNG生成 | 完全実装(膨張・ぼかし・穴埋め・ノイズ除去含む) |
| 9 | マスク編集UI | 簡易実装(追加/消しブラシ・サイズ変更・Undo/Redo・保存) |
| 10 | 合成プレビュー・差分表示 | 完全実装 |
| 11 | 欠損補完 | フラグ立て + `inpaint_tasks.json` 生成のみ(実補完はしない) |
| 12 | PSD出力 | **PsdToolsExporter** による簡易PSD。不安定ならレイヤーPNG + manifest + Photoshop/Kritaスクリプト生成にフォールバック |
| 13 | 品質チェック | ルールベース初期実装(重複名・空レイヤー・差分・命名整合など) |
| 14 | リギング設計書 | テンプレートベースの `rigging_plan.md` 生成 |

**MVPの合格基準**: 外部 AI API・SAM2・GPU が一切なくても、画像アップロードから PSD 出力・品質レポートまで一気通貫で動作すること。

## 3. 将来拡張の範囲(ポストMVP)

### Phase 2: AI高度化
- SAM2Segmenter(box / point / negative point / mask refinement)
- 実マルチモーダル AI による `analyze_character_image`(Claude / GPT / Gemini / ローカルVLM 差し替え可能)
- GroundingDINO / Florence によるパーツ自動検出(text prompt → bbox)
- BiRefNet による高精度背景除去・アルファマッティング
- AI生成のヒアリング質問(画像解析結果に基づく動的質問)

### Phase 3: 補完・高品質化
- Inpainting API 連携による欠損補完の実行(額・白目・口内・歯・舌・隠れ領域)
- アルファマッティングによる髪の毛先の高精度エッジ
- AI品質チェック(VLMによる合成画像とパーツ画像の視覚検査)
- 表情差分レイヤーの生成支援

### Phase 4: エクスポート強化・エコシステム
- PhotoshopScriptExporter / KritaExporter / OpenRasterExporter
- Cubism Editor 向けインポートガイドの自動生成
- リギング設計書の高度化(parts.json 実データからのデフォーマ構造推論)
- nizima / VTube Studio 向けプリセット
- プラグイン機構(Segmenter / Analyzer / Exporter のサードパーティ拡張)

### 明確にスコープ外のまま維持するもの
- `.moc3` / `.cmo3` 生成、自動メッシュ生成、自動リギング実行
