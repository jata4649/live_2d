import { create } from 'zustand'
import { api } from '../api/client'
import type { Part, PartsPlan } from '../types'

// parts.json のワーキングコピー。サーバーのファイルが真実であり、
// save() を呼ぶまで変更はローカルに留まる(手動保存文化)。
interface PartsState {
  projectId: string | null
  plan: PartsPlan | null
  selectedId: string | null
  dirty: boolean
  maskVersion: number // マスク更新時にインクリメントして画像を再読込させる

  load: (projectId: string) => Promise<void>
  analyze: (projectId: string) => Promise<void>
  save: () => Promise<void>
  select: (partId: string | null) => void
  updatePart: (partId: string, patch: Partial<Part>) => void
  updatePartDeep: (partId: string, updater: (p: Part) => Part) => void
  addPart: (part: Part) => void
  removePart: (partId: string) => void
  bumpMaskVersion: () => void
  selected: () => Part | null
}

export const usePartsStore = create<PartsState>((set, get) => ({
  projectId: null,
  plan: null,
  selectedId: null,
  dirty: false,
  maskVersion: 0,

  async load(projectId) {
    try {
      const plan = await api.getParts(projectId)
      set({ projectId, plan, dirty: false })
    } catch {
      set({ projectId, plan: null, dirty: false })
    }
  },

  async analyze(projectId) {
    const plan = await api.analyze(projectId)
    set({ projectId, plan, dirty: false, selectedId: null })
  },

  async save() {
    const { projectId, plan } = get()
    if (!projectId || !plan) return
    const saved = await api.putParts(projectId, plan)
    set({ plan: saved, dirty: false })
  },

  select(partId) {
    set({ selectedId: partId })
  },

  updatePart(partId, patch) {
    get().updatePartDeep(partId, (p) => ({ ...p, ...patch }))
  },

  updatePartDeep(partId, updater) {
    const plan = get().plan
    if (!plan) return
    set({
      plan: {
        ...plan,
        parts: plan.parts.map((p) => (p.id === partId ? updater(p) : p)),
      },
      dirty: true,
    })
  },

  addPart(part) {
    const plan = get().plan
    if (!plan) return
    set({
      plan: { ...plan, parts: [...plan.parts, part] },
      dirty: true,
      selectedId: part.id,
    })
  },

  removePart(partId) {
    const plan = get().plan
    if (!plan) return
    set({
      plan: { ...plan, parts: plan.parts.filter((p) => p.id !== partId) },
      dirty: true,
      selectedId: get().selectedId === partId ? null : get().selectedId,
    })
  },

  bumpMaskVersion() {
    set({ maskVersion: get().maskVersion + 1 })
  },

  selected() {
    const { plan, selectedId } = get()
    return plan?.parts.find((p) => p.id === selectedId) ?? null
  },
}))
