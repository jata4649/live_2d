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

const BASE = '/api/v1'

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
  getParts: (id: string) => request<PartsPlan>(`/projects/${id}/parts`),
  putParts: (id: string, plan: PartsPlan) =>
    request<PartsPlan>(`/projects/${id}/parts`, { ...json(plan), method: 'PUT' }),
  generateQuestions: (id: string) =>
    request<QuestionList>(`/projects/${id}/generate-questions`, { method: 'POST' }),

  // --- Segmentation ---
  runSegmentationAll: (id: string) =>
    request<Job>(`/projects/${id}/segmentation/run`, { method: 'POST' }),
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
  getQualityReport: (id: string) =>
    request<QualityReport>(`/projects/${id}/quality/report`),
  exportPsd: (id: string, force = false) =>
    request<ExportResult>(`/projects/${id}/export/psd`, json({ force })),
  exportLayersZip: (id: string, force = false) =>
    request<ExportResult>(`/projects/${id}/export/layers-zip`, json({ force })),
  exportRiggingPlan: (id: string) =>
    request<{ rigging_plan_path: string }>(`/projects/${id}/export/rigging-plan`, {
      method: 'POST',
    }),

  // --- Jobs ---
  getJob: (jobId: string) => request<Job>(`/jobs/${jobId}`),
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
