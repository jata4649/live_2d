import { create } from 'zustand'
import { api } from '../api/client'
import type { Project, ProjectSummary, UserPreferences } from '../types'

interface ProjectState {
  current: Project | null
  list: ProjectSummary[]
  loading: boolean
  error: string | null
  loadList: () => Promise<void>
  loadProject: (id: string) => Promise<Project>
  createProject: (name: string, image: File) => Promise<Project>
  deleteProject: (id: string) => Promise<void>
  savePreferences: (prefs: UserPreferences) => Promise<void>
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  current: null,
  list: [],
  loading: false,
  error: null,

  async loadList() {
    set({ loading: true, error: null })
    try {
      set({ list: await api.listProjects() })
    } catch (e) {
      set({ error: String(e) })
    } finally {
      set({ loading: false })
    }
  },

  async loadProject(id) {
    const project = await api.getProject(id)
    set({ current: project })
    return project
  },

  async createProject(name, image) {
    const project = await api.createProject(name, image)
    set({ current: project })
    return project
  },

  async deleteProject(id) {
    await api.deleteProject(id)
    if (get().current?.project_id === id) set({ current: null })
    await get().loadList()
  },

  async savePreferences(prefs) {
    const current = get().current
    if (!current) throw new Error('プロジェクトが選択されていません')
    const project = await api.updatePreferences(current.project_id, prefs)
    set({ current: project })
  },
}))
