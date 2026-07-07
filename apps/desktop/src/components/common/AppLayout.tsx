import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'

const STEPS = [
  { key: 'interview', label: 'ヒアリング' },
  { key: 'parts', label: 'パーツ設計' },
  { key: 'preview', label: 'プレビュー' },
  { key: 'export', label: '出力' },
] as const

export function AppLayout() {
  const { id } = useParams()
  const location = useLocation()
  const current = useProjectStore((s) => s.current)
  const projectId = id ?? current?.project_id

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-6 border-b border-neutral-700 bg-neutral-800 px-4 py-2">
        <Link to="/" className="text-sm font-bold tracking-wide text-indigo-300">
          AutoLive2D Layer Studio
        </Link>
        {projectId && current && (
          <>
            <span className="text-xs text-neutral-400">{current.name}</span>
            <nav className="flex gap-1 text-xs">
              {STEPS.map((step) => {
                const path = `/projects/${projectId}/${step.key}`
                const active = location.pathname.startsWith(path)
                return (
                  <Link
                    key={step.key}
                    to={path}
                    className={`rounded px-2 py-1 ${
                      active
                        ? 'bg-indigo-600 text-white'
                        : 'text-neutral-300 hover:bg-neutral-700'
                    }`}
                  >
                    {step.label}
                  </Link>
                )
              })}
            </nav>
          </>
        )}
      </header>
      <main className="min-h-0 flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
