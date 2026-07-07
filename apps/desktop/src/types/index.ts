// バックエンド Pydantic モデルに対応する型定義。
// 将来的には packages/shared の JSON Schema から自動生成に置き換える
// (apps/api/scripts/export_schemas.py 参照)。

export type QualityLevel = 'draft' | 'standard' | 'high' | 'commercial'
export type FaceRange = 'small' | 'medium' | 'large'
export type MouthType = 'open_close' | 'aiueo' | 'singing' | 'auto'
export type EyeType = 'blink' | 'gaze' | 'full'

export interface SourceImage {
  original_path: string
  normalized_path: string
  width: number
  height: number
  has_alpha: boolean
  color_profile: string
}

export interface UserPreferences {
  quality_level: QualityLevel
  target: string
  face_range: FaceRange
  mouth_type: MouthType
  eye_type: EyeType
  hair_physics: boolean
  accessory_physics: boolean
  arm_movement: boolean
  expression_variants: boolean
  accessories: string[]
}

export interface ProjectStatus {
  analysis_done: boolean
  interview_done: boolean
  segmentation_done: boolean
  quality_checked: boolean
  export_done: boolean
}

export interface Project {
  project_id: string
  name: string
  created_at: string
  updated_at: string
  source_image: SourceImage
  preferences: UserPreferences
  status: ProjectStatus
}

export interface ProjectSummary {
  project_id: string
  name: string
  created_at: string
  updated_at: string
  status: ProjectStatus
}

export type SegmentationMethod =
  | 'mock' | 'manual_box' | 'alpha_color'
  | 'sam2_box' | 'sam2_points' | 'external_api'

export type PartType =
  | 'face' | 'eye' | 'eyebrow' | 'mouth' | 'hair'
  | 'body' | 'clothes' | 'accessory' | 'other'

export type PriorityLevel = 'low' | 'normal' | 'high'

export interface Part {
  id: string
  name_jp: string
  name_en: string
  group: string
  z_order: number
  visible: boolean
  locked: boolean
  required: boolean
  part_type: PartType
  visual_description: string
  segmentation: {
    method: SegmentationMethod
    bbox: [number, number, number, number] | null
    positive_points: number[][]
    negative_points: number[][]
    text_prompt: string
  }
  files: { mask_path: string; layer_path: string }
  live2d: {
    usage: string[]
    parent_deformer_hint: string
    physics_hint: string
  }
  processing: {
    overlap_bleed_px: number
    edge_feather_px: number
    needs_inpaint_under: boolean
    inpaint_reason: string
  }
  quality: {
    priority: PriorityLevel
    manual_review_required: boolean
    score: number | null
  }
}

export interface PartsPlan {
  version: string
  parts: Part[]
}

export interface Question {
  id: string
  category: string
  question: string
  type: 'single_choice' | 'multi_choice' | 'boolean' | 'text'
  choices: string[]
  maps_to: string
}

export interface QuestionList {
  questions: Question[]
}

export type JobStatus = 'queued' | 'running' | 'done' | 'failed'

export interface Job {
  job_id: string
  project_id: string
  kind: string
  status: JobStatus
  progress: number
  message: string
  error: string | null
  created_at: string
  finished_at: string | null
}

export type Severity = 'high' | 'medium' | 'low' | 'info'

export interface QualityIssue {
  severity: Severity
  part_id: string | null
  code: string
  message: string
  suggested_fix: string
  auto_fix_available: boolean
}

export interface QualityReport {
  overall_score: number
  approved: boolean
  checked_at: string
  issues: QualityIssue[]
}

export interface PreviewResult {
  composite_path: string
  difference_path: string
  diff_pixel_count: number
  diff_pixel_ratio: number
  max_channel_diff: number
  layers_used: number
}

export interface ExportResult {
  ok: boolean
  exporter: string
  output_path: string
  fallback_used: boolean
  warnings: string[]
  error: string | null
}

export interface ApiError {
  code: string
  message: string
  detail: unknown
}
