# 04. 主要データモデル

Pydantic(Python)を定義元とし、JSON Schema 経由で TypeScript 型を自動生成する。
以下は論理スキーマ。フィールド名・構造は `parts.json` / `project.json` 等のファイルとそのまま一致させる。

## 1. project.json — `Project`

```jsonc
{
  "project_id": "uuid",
  "name": "my_vtuber",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "source_image": {
    "original_path": "source/original.png",
    "normalized_path": "source/normalized.png",
    "width": 4096,
    "height": 4096,
    "has_alpha": true,
    "color_profile": "sRGB"
  },
  "preferences": {                    // UserPreferences(ヒアリング回答)
    "quality_level": "high",          // "draft" | "standard" | "high" | "commercial"
    "target": "VTube Studio",         // 使用目的
    "face_range": "medium",           // "small" | "medium" | "large"
    "mouth_type": "aiueo",            // "open_close" | "aiueo" | "singing" | "auto"
    "eye_type": "full",               // "blink" | "gaze" | "full"(笑顔目・ジト目含む)
    "hair_physics": true,
    "accessory_physics": true,
    "arm_movement": false,
    "expression_variants": false,
    "accessories": ["ribbon", "glasses"]
  },
  "status": {
    "analysis_done": false,
    "interview_done": false,
    "segmentation_done": false,
    "quality_checked": false,
    "export_done": false
  }
}
```

### Pydantic 対応

```python
class QualityLevel(str, Enum): draft; standard; high; commercial
class SourceImage(BaseModel): original_path; normalized_path; width; height; has_alpha; color_profile
class UserPreferences(BaseModel): quality_level; target; face_range; mouth_type; eye_type; ...
class ProjectStatus(BaseModel): analysis_done; interview_done; segmentation_done; quality_checked; export_done
class Project(BaseModel): project_id; name; created_at; updated_at; source_image; preferences; status
```

## 2. parts.json — `PartsPlan` / `Part`

```jsonc
{
  "version": "1.0",
  "parts": [
    {
      "id": "front_hair_01",              // 一意・snake_case・左右は _L/_R サフィックス
      "name_jp": "前髪_中央01",
      "name_en": "Front Hair 01",
      "group": "Hair/Front",              // "/" 区切り階層 → PSDグループに写像
      "z_order": 120,                     // 大きいほど手前(PSD上位)
      "visible": true,
      "locked": false,
      "required": true,
      "part_type": "hair",                // "face"|"eye"|"mouth"|"hair"|"body"|"clothes"|"accessory"|"other"
      "visual_description": "顔中央にかかる前髪の房",
      "segmentation": {
        "method": "sam2_box",             // "mock"|"manual_box"|"alpha_color"|"sam2_box"|"sam2_points"|"external_api"
        "bbox": [100, 120, 300, 600],     // [x, y, w, h] 正規化画像ピクセル座標
        "positive_points": [],            // [[x,y], ...]
        "negative_points": [],
        "text_prompt": "central front hair strand"
      },
      "files": {
        "mask_path": "masks/front_hair_01_mask.png",
        "layer_path": "layers/front_hair_01.png"
      },
      "live2d": {
        "usage": ["ParamAngleX", "ParamAngleY", "PhysicsHairFront"],
        "parent_deformer_hint": "D_Hair_Front",
        "physics_hint": "front_hair_soft"
      },
      "processing": {
        "overlap_bleed_px": 8,            // 塗り足し量(マスク膨張px)
        "edge_feather_px": 1,             // 境界ぼかし
        "needs_inpaint_under": true,      // このパーツの下に補完が必要か
        "inpaint_reason": "前髪が揺れた際に額が見えるため"
      },
      "quality": {
        "priority": "high",               // "low"|"normal"|"high"
        "manual_review_required": true,
        "score": null                     // 品質チェック後に 0-100 を記入
      }
    }
  ]
}
```

## 3. segmentation_tasks.json — `SegmentationTaskList`

```jsonc
{
  "tasks": [
    {
      "task_id": "uuid",
      "part_id": "front_hair_01",
      "image_path": "source/normalized.png",
      "method": "sam2_box",
      "bbox": [100, 120, 300, 600],
      "positive_points": [],
      "negative_points": [],
      "text_prompt": "central front hair strand",
      "expected_output": "masks/front_hair_01_mask.png",
      "refinement": {
        "remove_small_noise": true,
        "fill_holes": true,
        "smooth_edges": true,
        "dilate_px": 2
      },
      "status": "pending"                 // "pending"|"running"|"done"|"failed"
    }
  ]
}
```

`MaskResult`(Segmenter の返り値): `mask: np.ndarray(H, W, uint8)` + `confidence: float | None` + `method_used` + `warnings: list[str]`。

## 4. quality_report.json — `QualityReport`

```jsonc
{
  "overall_score": 82,                    // 90+: 良好 / 70-89: 軽微修正推奨 / 50-69: 要修正 / <50: 出力非推奨
  "approved": false,
  "checked_at": "ISO8601",
  "issues": [
    {
      "severity": "high",                 // "high"|"medium"|"low"|"info"
      "part_id": "front_hair_01",
      "code": "EDGE_ARTIFACT",            // 機械可読コード(下記 4.1)
      "message": "境界に透明フチが見られます",
      "suggested_fix": "マスクを1px膨張し、境界を軽くぼかしてください",
      "auto_fix_available": true
    }
  ]
}
```

### 4.1 チェックコード一覧(初期セット)

| code | 内容 |
|---|---|
| `DUPLICATE_LAYER_NAME` | レイヤー名重複 |
| `EMPTY_LAYER` | 空 / 透明ピクセルのみのレイヤー |
| `MISSING_MASK` | マスク未生成のパーツ |
| `COMPOSITE_DIFF` | 合成プレビューと元画像の差分超過 |
| `Z_ORDER_ANOMALY` | レイヤー順の異常(口が髪より手前 等のヒューリスティック) |
| `LR_NAMING_MISMATCH` | 左右命名の不整合(`_L` があるのに `_R` がない等) |
| `MISSING_REQUIRED_PART` | 目・口・髪など必須パーツ不足 |
| `INSUFFICIENT_BLEED` | 塗り足し不足の可能性 |
| `EDGE_ARTIFACT` | 透明フチ・白フチ・黒フチ |
| `PSD_CONSTRAINT_VIOLATION` | PSD制約違反(ビット深度・カラーモード等) |
| `FILE_MISSING` | 参照ファイル欠落 |

## 5. inpaint_tasks.json — `InpaintTaskList`(MVPは生成のみ)

```jsonc
{
  "tasks": [
    {
      "task_id": "uuid",
      "target_part_id": "face_base",        // 補完を焼き込む先のパーツ
      "occluder_part_ids": ["front_hair_01"], // 隠しているパーツ
      "region_mask_path": "masks/inpaint_face_base_under_hair.png",
      "reason": "前髪が揺れた際に額が見えるため",
      "method": "none",                      // MVP: "none" / 将来: "api"|"local_model"
      "priority": "high",
      "status": "planned"
    }
  ]
}
```

## 6. ヒアリング — `QuestionList`

```jsonc
{
  "questions": [
    {
      "id": "q001",
      "category": "mouth",     // "quality"|"target"|"face"|"eye"|"mouth"|"hair"|"accessory"|"arm"|"expression"
      "question": "口は「あいうえお」差分まで作りますか?",
      "type": "single_choice", // "single_choice"|"multi_choice"|"boolean"|"text"
      "choices": ["開閉のみ", "あいうえお対応", "歌唱向けに細かく", "おまかせ"],
      "maps_to": "preferences.mouth_type"   // 回答の保存先
    }
  ]
}
```

## 7. ジョブ — `Job`(SQLite テーブル & API レスポンス)

```jsonc
{
  "job_id": "uuid",
  "project_id": "uuid",
  "kind": "segmentation_run",  // "segmentation_run"|"layer_generate"|"quality_check"|"export_psd"|...
  "status": "running",          // "queued"|"running"|"done"|"failed"
  "progress": 0.42,
  "message": "front_hair_01 を処理中",
  "error": null,
  "created_at": "ISO8601",
  "finished_at": null
}
```

## 8. SQLite スキーマ(メタデータのみ・実体はJSON/PNGファイル)

```sql
CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status_json TEXT NOT NULL        -- ProjectStatus のキャッシュ(一覧表示高速化用)
);
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  progress REAL NOT NULL DEFAULT 0,
  message TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT
);
```

**設計判断**: プロジェクトの実データ(parts.json 等)は SQLite に入れず、ファイルが唯一の真実とする。ユーザーがフォルダごとバックアップ・共有でき、非破壊編集の思想と一致するため。SQLite は一覧・検索・ジョブ管理のみ。
