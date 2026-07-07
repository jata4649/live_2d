# 02. アーキテクチャ提案

## 1. 全体構成

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop Shell (Tauri 第一候補 / Electron 代替)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Frontend: React + TS + Vite + Zustand + Tailwind      │  │
│  │  Canvas: Konva.js (bbox編集 / マスクブラシ / プレビュー) │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │ HTTP (localhost REST + 静的ファイル) │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │  Backend: FastAPI (Python) — サイドカープロセス          │  │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │  │
│  │  │ routers │→│ services │→│ domain  │→│ 抽象化層    │  │  │
│  │  └─────────┘ └──────────┘ └─────────┘ │ ai/         │  │  │
│  │                                        │ segmentation│  │  │
│  │  Storage: SQLite(メタ) +               │ exporters/  │  │  │
│  │  outputs/projects/{id}/(実ファイル)     └────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 採用理由

- **Web UI + ローカル FastAPI サイドカー**: 画像処理・PSD 生成は Python エコシステム(Pillow/OpenCV/psd-tools)が最強。UI は React が最速。両者を localhost REST で接続するのが最も疎結合で、将来「サーバー版」への展開も可能。
- **Tauri 第一候補**: バイナリが軽量で配布が容易。Python バックエンドはどちらにせよサイドカーなので、シェルの重い Electron を選ぶ理由が薄い。ただし Tauri のサイドカー管理に問題が出た場合は Electron に切り替え可能な構成にする(シェル層は起動・終了・ファイルダイアログのみに限定)。
- **開発時はブラウザで動作**: デスクトップシェルなしでも `vite dev` + `uvicorn` で全機能が動くこと。シェル依存コードを作らない。

## 2. 抽象化戦略(最重要)

将来の高精度化を妨げないため、以下 4 つの差し替えポイントを**必ず抽象基底クラス(Python ABC / Protocol)で定義**する。MVP のモック実装と将来の本実装は同一インターフェースを実装する。

### 2.1 CharacterAnalyzer(AI解析)

```python
class CharacterAnalyzer(ABC):
    def analyze_character_image(self, image_path: Path, user_preferences: UserPreferences) -> PartsPlan: ...
    def generate_questions(self, image_analysis: ImageAnalysis) -> QuestionList: ...
    def generate_segmentation_tasks(self, parts_plan: PartsPlan) -> SegmentationTaskList: ...
    def generate_rigging_plan(self, parts_plan: PartsPlan) -> str:  # Markdown
```

| 実装 | フェーズ |
|---|---|
| `MockAnalyzer` — 標準パーツテンプレート + 静的質問 + テンプレリギング設計書 | MVP |
| `ClaudeAnalyzer` / `OpenAIAnalyzer` / `GeminiAnalyzer` / `LocalVlmAnalyzer` | Phase 2 |

プロンプトは `prompts/*.md` からロードし、`PromptManager` が変数埋め込みを行う。実装クラスにプロンプトをハードコードしない。

### 2.2 Segmenter(セグメンテーション)

```python
class Segmenter(ABC):
    def segment(self, image: np.ndarray, task: SegmentationTask) -> MaskResult: ...
    @property
    def supported_methods(self) -> set[SegmentationMethod]: ...
```

| 実装 | 手法 | フェーズ |
|---|---|---|
| `MockSegmenter` | bbox 内を仮マスク(楕円/矩形) | MVP |
| `ManualBoxSegmenter` | bbox 内でアルファ/色クラスタリングによる簡易切り抜き | MVP |
| `Sam2Segmenter` | box/point/negative point prompt + refinement | Phase 2 |
| `ExternalApiSegmenter` | リモートAPI委譲 | Phase 2+ |

`SegmenterRegistry` が `task.method` に応じて実装を選択。SAM2 未導入環境では自動で ManualBox にフォールバックし、`quality_report` に「簡易マスクである」旨を記録する。

### 2.3 PsdExporter(PSD出力)

```python
class PsdExporter(ABC):
    def export(self, project: Project, parts: PartsPlan, layers_dir: Path, out_path: Path) -> ExportResult: ...
    def validate_capabilities(self) -> ExporterCapabilities: ...
```

| 実装 | フェーズ |
|---|---|
| `PsdToolsExporter` — psd-tools でグループ階層付きPSD生成 | MVP |
| `LayerZipExporter` — layers.zip + manifest.json(常時提供・保険) | MVP |
| `PhotoshopScriptExporter` — manifest + JSX/UXP スクリプト生成 | MVP(フォールバック)〜 Phase 4 |
| `KritaExporter` / `OpenRasterExporter` | Phase 4 |

**フォールバック戦略**: psd-tools での生成後に必ず再読込検証(ラウンドトリップ)を行い、失敗時は LayerZip + PhotoshopScript 出力に自動フォールバックして quality_report に記録する。

### 2.4 Inpainter(欠損補完)— 設計のみMVP

```python
class Inpainter(ABC):
    def inpaint(self, image: np.ndarray, mask: np.ndarray, task: InpaintTask) -> np.ndarray: ...
```

MVP では `inpaint_tasks.json` の生成まで(`NoopInpainter`)。Phase 3 で API/ローカルモデル実装を追加。

## 3. バックエンド層構造

```
routers(HTTP境界・入出力バリデーションのみ)
  → services(ユースケース調整・トランザクション・ログ)
    → image_processing / ai / segmentation / exporters(純粋ロジック)
      → core.paths(パス一元管理)/ SQLite / ファイルシステム
```

原則:
- **routers に画像処理コードを書かない**。services 経由のみ。
- **パスは `core/paths.py` の `ProjectPaths` クラスだけが知る**。他の場所で `os.path.join` によるパス組み立てを禁止。
- 画像処理関数は `np.ndarray in → np.ndarray out` の純関数とし、ファイルI/Oは services 層に置く(テスト容易性)。
- 全 API エラーは `{code, message, detail}` 形式で返し、ユーザーに分かる日本語メッセージを付す。

## 4. 実行モデル

- セグメンテーション一括実行・PSD出力など長時間処理は **ジョブとして非同期実行**(FastAPI `BackgroundTasks` + ジョブテーブル)。MVP はポーリング(`GET /jobs/{job_id}`)、Phase 2 で WebSocket/SSE 進捗通知。
- 画像はバックエンドがマスタを保持。フロントは `GET /projects/{id}/files/...` 経由の静的配信で取得し、編集結果(マスク等)を PUT で書き戻す。
- マスク編集の Undo/Redo はフロント側(ストローク履歴)で完結。保存時のみ PNG をバックエンドへ送る。

## 5. データフロー(1パーツの一生)

```
parts.json のエントリ生成 (MockAnalyzer)
 → bbox 編集 (PartsEditor)
 → segmentation_tasks.json 生成
 → Segmenter 実行 → masks/{part_id}_mask.png (8bit grayscale)
 → マスク修正 (MaskEditor) → PUT で上書き
 → refinement (穴埋め・ノイズ除去・overlap_bleed_px 膨張・edge_feather ぼかし)
 → layers/{part_id}.png (RGBA・元画像と同キャンバス・位置ずれなし)
 → composite_preview / difference_preview
 → quality_report.json
 → PSD レイヤーとして exports/live2d_import.psd へ
```

## 6. Live2D PSD 制約の実装方針

| 制約 | 実装 |
|---|---|
| RGB / 8bit / sRGB | 正規化段階で強制変換。エクスポート時に再検証 |
| 1パーツ1レイヤー | parts.json と PSD レイヤーを 1:1 対応。結合が必要な場合は parts.json 側で統合 |
| レイヤー名重複禁止 | quality_check + export 前バリデーションで拒否 |
| レイヤーマスク / クリッピング不使用 | エクスポータはフラット RGBA レイヤーのみ生成(マスクは事前に焼き込み) |
| グループ階層保持 | parts.json の `group`(`Hair/Front` 形式)から PSD グループを構築 |
| 非表示レイヤー | `visible: false` は PSD にも非表示で出力し、manifest に明記 |
| レイヤー順 | `z_order` 降順 = PSD 上から下。同値はグループ内定義順 |

## 7. テスト戦略

- **pytest**: services / image_processing の単体テスト。合成→差分ゼロ検証、マスク膨張のピクセル数検証など。
- **画像スナップショットテスト**: 固定シード入力画像に対する mask/layer/preview のハッシュ or 差分閾値比較。`tests/fixtures/` に小型テスト画像を同梱。
- **PSD ラウンドトリップテスト**: psd-tools で書いた PSD を読み戻し、レイヤー名・階層・サイズ・ピクセルを検証。
- **Vitest**: ストア・API クライアント・キャンバス座標変換の単体テスト。
