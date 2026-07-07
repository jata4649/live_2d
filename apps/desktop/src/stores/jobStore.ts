import { create } from 'zustand'
import { api } from '../api/client'
import type { Job } from '../types'

// 実行中ジョブのポーリングと処理ログの蓄積。
interface LogEntry {
  time: string
  message: string
  level: 'info' | 'error'
}

interface JobState {
  activeJob: Job | null
  logs: LogEntry[]
  log: (message: string, level?: 'info' | 'error') => void
  runJob: (start: () => Promise<Job>, label: string) => Promise<Job>
  clearLogs: () => void
}

export const useJobStore = create<JobState>((set, get) => ({
  activeJob: null,
  logs: [],

  log(message, level = 'info') {
    const entry: LogEntry = {
      time: new Date().toLocaleTimeString('ja-JP'),
      message,
      level,
    }
    set({ logs: [...get().logs.slice(-199), entry] })
  },

  async runJob(start, label) {
    get().log(`${label} を開始しました`)
    let job = await start()
    set({ activeJob: job })
    while (job.status === 'queued' || job.status === 'running') {
      await new Promise((r) => setTimeout(r, 500))
      job = await api.getJob(job.job_id)
      set({ activeJob: job })
      if (job.message) get().log(`${label}: ${job.message}`)
    }
    set({ activeJob: null })
    if (job.status === 'failed') {
      get().log(`${label} が失敗しました: ${job.error}`, 'error')
      throw new Error(job.error ?? `${label} が失敗しました`)
    }
    get().log(`${label} が完了しました`)
    return job
  },

  clearLogs() {
    set({ logs: [] })
  },
}))
