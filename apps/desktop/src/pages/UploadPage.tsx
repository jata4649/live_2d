import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../stores/projectStore'

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [info, setInfo] = useState<{ w: number; h: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const createProject = useProjectStore((s) => s.createProject)
  const navigate = useNavigate()

  const onFile = useCallback((f: File) => {
    setFile(f)
    if (!name) setName(f.name.replace(/\.[^.]+$/, ''))
    const url = URL.createObjectURL(f)
    setPreview(url)
    const img = new Image()
    img.onload = () => setInfo({ w: img.naturalWidth, h: img.naturalHeight })
    img.src = url
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name])

  const submit = async () => {
    if (!file || !name.trim()) return
    setBusy(true)
    setError(null)
    try {
      const project = await createProject(name.trim(), file)
      navigate(`/projects/${project.project_id}/interview`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="mb-6 text-2xl font-bold">新規プロジェクト</h1>

      <label
        className="checkerboard mb-4 flex h-80 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-neutral-600 hover:border-indigo-500"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const f = e.dataTransfer.files[0]
          if (f) onFile(f)
        }}
      >
        {preview ? (
          <img src={preview} alt="preview" className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="rounded bg-neutral-900/80 px-4 py-2 text-neutral-300">
            立ち絵画像をドロップ、またはクリックして選択(PNG / JPG / WEBP)
          </span>
        )}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) onFile(f)
          }}
        />
      </label>

      {info && file && (
        <p className="mb-4 text-xs text-neutral-400">
          {info.w} × {info.h} px / {(file.size / 1024 / 1024).toFixed(1)} MB / {file.type}
        </p>
      )}

      <div className="mb-6">
        <label className="mb-1 block text-sm text-neutral-300">プロジェクト名</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded border border-neutral-600 bg-neutral-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          placeholder="my_vtuber"
        />
      </div>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

      <button
        disabled={!file || !name.trim() || busy}
        onClick={() => void submit()}
        className="rounded bg-indigo-600 px-6 py-2 font-medium hover:bg-indigo-500 disabled:opacity-40"
      >
        {busy ? '作成中(画像を正規化しています)...' : '作成して次へ'}
      </button>
    </div>
  )
}
