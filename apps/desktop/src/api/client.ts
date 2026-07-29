// 型付き API クライアント。fetch の薄いラッパ。
import type {
  ExportResult,
  Job,
  PartsPlan,
  PreviewResult,
  Project,
  ProjectSummary,
  QualityReport,
  QuestionList,
  UserPreferences,
} from '../types'

// Tauri 等の file/カスタムプロトコル配信では相対 /api が使えないため、
// ビルド時に VITE_API_BASE=http://127.0.0.1:8787 を指定して絶対URLにする。
const BASE = `${import.meta.env.VITE_API_BASE ?? ''}/api/v1`

export class ApiRequestError extends Error {
  code: string
  status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let code = 'UNKNOWN'
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      code = body.code ?? code
      message = body.message ?? body.detail ?? message
    } catch {
      /* JSON でないエラーはそのまま */
    }
    throw new ApiRequestError(res.status, code, message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function json(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  // --- Project ---
  createProject(name: string, image: File): Promise<Project> {
    const form = new FormData()
    form.append('name', name)
    form.append('image', image)
    return request('/projects', { method: 'POST', body: form })
  },
  listProjects: () => request<ProjectSummary[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: 'DELETE' }),
  updatePreferences: (id: string, prefs: UserPreferences) =>
    request<Project>(`/projects/${id}/preferences`, {
      ...json(prefs),
      method: 'PUT',
    }),

  // --- Analysis ---
  listAnalyzers: () =>
    request<{ name: string; label: string; available: boolean; reason: string }[]>(
      '/analyzers',
    ),
  analyze: (id: string, analyzer = 'mock') =>
    request<PartsPlan>(`/projects/${id}/analyze`, json({ analyzer })),
  listSegmenters: () =>
    request<{ method: string; label: string; available: boolean; reason: string }[]>(
      '/segmenters',
    ),
  getParts: (id: string) => request<PartsPlan>(`/projects/${id}/parts`),
  putParts: (id: string, plan: PartsPlan) =>
    request<PartsPlan>(`/projects/${id}/parts`, { ...json(plan), method: 'PUT' }),
  generateQuestions: (id: string) =>
    request<QuestionList>(`/projects/${id}/generate-questions`, { method: 'POST' }),

  // --- Segmentation ---
  runSegmentationAll: (id: string) =>
    request<Job>(`/projects/${id}/segmentation/run`, { method: 'POST' }),
  autoPipeline: (id: string) =>
    request<Job>(`/projects/${id}/pipeline/auto`, { method: 'POST' }),
  pipelineSummary: (id: string) =>
    request<{
      steps: { step: string; detail: string }[]
      final_score: number
      motion_holes_after: number
      orphan_px_after: number
    }>(`/projects/${id}/pipeline/summary`),
  syncBbox: (id: string, partId: string) =>
    request<{ part_id: string; bbox: [number, number, number, number] }>(
      `/projects/${id}/masks/${partId}/sync-bbox`,
      { method: 'POST' },
    ),
  runSegmentationPart: (id: string, partId: string) =>
    request<{ part_id: string; mask_path: string; warnings: string[] }>(
      `/projects/${id}/segmentation/run/${partId}`,
      { method: 'POST' },
    ),
  putMask: (id: string, partId: string, png: Blob) =>
    request<{ mask_path: string }>(`/projects/${id}/masks/${partId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'image/png' },
      body: png,
    }),
  mirrorMask: (id: string, partId: string) =>
    request<{
      source_part_id: string
      twin_part_id: string
      mask_path: string
      layer_path: string | null
      bbox_updated: boolean
    }>(`/projects/${id}/masks/${partId}/mirror`, { method: 'POST' }),
  refineMask: (
    id: string,
    partId: string,
    params: Partial<{
      remove_small_noise: boolean
      fill_holes: boolean
      smooth_edges: boolean
      dilate_px: number
      erode_px: number
      feather_px: number
    }>,
  ) =>
    request<{ mask_path: string }>(
      `/projects/${id}/masks/${partId}/refine`,
      json(params),
    ),

  // --- Layers / Preview ---
  generateLayers: (id: string) =>
    request<Job>(`/projects/${id}/layers/generate`, { method: 'POST' }),
  generateLayer: (id: string, partId: string) =>
    request<{ layer_path: string }>(`/projects/${id}/layers/generate/${partId}`, {
      method: 'POST',
    }),
  compositePreview: (id: string) =>
    request<PreviewResult>(`/projects/${id}/preview/composite`, { method: 'POST' }),

  // --- Quality / Export ---
  qualityCheck: (id: string) =>
    request<QualityReport>(`/projects/${id}/quality/check`, { method: 'POST' }),
  motionCheck: (id: string) =>
    request<{
      amplitude_px: number
      checked_parts: number
      entries: {
        part_id: string
        shift: [number, number]
        hole_px: number
        hole_ratio: number
      }[]
      preview_path: string
    }>(`/projects/${id}/quality/motion-check`, { method: 'POST' }),
  motionFix: (id: string) =>
    request<{
      fills: { moved_part_id: string; target_part_id: string; filled_px: number }[]
      skipped: string[]
      report_after: { entries: unknown[]; checked_parts: number }
    }>(`/projects/${id}/quality/motion-fix`, { method: 'POST' }),
  resolveOrphans: (id: string) =>
    request<{
      orphan_px_before: number
      orphan_px_after: number
      components: number
      assignments: { part_id: string; components: number; pixels: number }[]
      layers_regenerated: string[]
    }>(`/projects/${id}/masks/resolve-orphans`, { method: 'POST' }),
  qualityAutofix: (id: string) =>
    request<{ applied: { part_id: string; code: string; action: string }[]; report: QualityReport }>(
      `/projects/${id}/quality/autofix`,
      { method: 'POST' },
    ),
  inpaintPlan: (id: string) =>
    request<{ tasks: unknown[] }>(`/projects/${id}/inpaint/plan`, { method: 'POST' }),
  inpaintRun: (id: string) =>
    request<{
      results: {
        target_part_id: string
        occluder_part_id: string
        region_px: number
        status: string
        reason: string
      }[]
    }>(`/projects/${id}/inpaint/run`, { method: 'POST' }),
  getQualityReport: (id: string) =>
    request<QualityReport>(`/projects/${id}/quality/report`),
  exportPsd: (id: string, force = false) =>
    request<ExportResult>(`/projects/${id}/export/psd`, json({ force })),
  exportLayersZip: (id: string, force = false) =>
    request<ExportResult>(`/projects/${id}/export/layers-zip`, json({ force })),
  exportOra: (id: string, force = false) =>
    request<ExportResult>(`/projects/${id}/export/ora`, json({ force })),
  exportRiggingPlan: (id: string) =>
    request<{ rigging_plan_path: string }>(`/projects/${id}/export/rigging-plan`, {
      method: 'POST',
    }),

  // --- Jobs ---
  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),
  getEnvironment: () =>
    request<{
      analyzers: { name: string; label: string; available: boolean; reason: string }[]
      segmenters: { method: string; label: string; available: boolean; reason: string }[]
      bg_removal: { available: boolean; reason: string }
      torch: { installed: boolean; cuda: boolean; device_name: string }
      anthropic_key_set: boolean
      sam2_device: string
      hints: string[]
    }>('/environment'),
}

// プロジェクト内ファイルのURL(キャッシュ回避のためのバージョンパラメータ付き)
export function fileUrl(projectId: string, relPath: string, version?: number): string {
  const v = version ?? Date.now()
  return `${BASE}/projects/${projectId}/files/${relPath}?v=${v}`
}

export function maskUrl(projectId: string, partId: string, version?: number): string {
  const v = version ?? Date.now()
  return `${BASE}/projects/${projectId}/masks/${partId}?v=${v}`
}

export function exportFileUrl(projectId: string, filename: string): string {
  return `${BASE}/projects/${projectId}/export/files/${filename}`
}
