import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fileUrl } from '../api/client'
import { useProjectStore } from '../stores/projectStore'

export function HomePage() {
  const { list, loading, loadList, deleteProject, loadProject } = useProjectStore()
  const navigate = useNavigate()

  useEffect(() => {
    void loadList()
  }, [loadList])

  const openProject = async (id: string) => {
    const project = await loadProject(id)
    if (!project.status.analysis_done) {
      navigate(`/projects/${id}/interview`)
    } else {
      navigate(`/projects/${id}/parts`)
    }
  }

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">プロジェクト</h1>
        <Link
          to="/projects/new"
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500"
        >
          + 新規プロジェクト
        </Link>
      </div>

      {loading && <p className="text-neutral-400">読み込み中...</p>}
      {!loading && list.length === 0 && (
        <div className="rounded-lg border border-dashed border-neutral-600 p-12 text-center text-neutral-400">
          プロジェクトがありません。立ち絵画像から新規作成してください。
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        {list.map((p) => (
          <div
            key={p.project_id}
            className="group cursor-pointer rounded-lg border border-neutral-700 bg-neutral-800 p-3 hover:border-indigo-500"
            onClick={() => void openProject(p.project_id)}
          >
            <div className="checkerboard mb-2 flex h-40 items-center justify-center overflow-hidden rounded">
              <img
                src={fileUrl(p.project_id, 'source/working.png', 1)}
                alt={p.name}
                className="max-h-full max-w-full object-contain"
                onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">{p.name}</div>
                <div className="text-xs text-neutral-500">
                  {new Date(p.updated_at).toLocaleString('ja-JP')}
                </div>
              </div>
              <button
                className="hidden rounded px-2 py-1 text-xs text-red-400 hover:bg-red-950 group-hover:block"
                onClick={(e) => {
                  e.stopPropagation()
                  if (confirm(`「${p.name}」を削除しますか?この操作は元に戻せません。`)) {
                    void deleteProject(p.project_id)
                  }
                }}
              >
                削除
              </button>
            </div>
            <div className="mt-2 flex gap-1">
              {p.status.analysis_done && <Badge>解析済</Badge>}
              {p.status.segmentation_done && <Badge>分割済</Badge>}
              {p.status.export_done && <Badge>出力済</Badge>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-neutral-700 px-1.5 py-0.5 text-[10px] text-neutral-300">
      {children}
    </span>
  )
}
