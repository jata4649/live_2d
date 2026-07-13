import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, fileUrl } from '../api/client'
import { useJobStore } from '../stores/jobStore'
import { useProjectStore } from '../stores/projectStore'
import type { PreviewResult } from '../types'

type Mode = 'composite' | 'original' | 'difference' | 'blink' | 'motion' | 'motion_anim'

export function PreviewPage() {
  const { id } = useParams<{ id: string }>()
  const { current, loadProject } = useProjectStore()
  const { log } = useJobStore()
  const [result, setResult] = useState<PreviewResult | null>(null)
  const [mode, setMode] = useState<Mode>('composite')
  const [version, setVersion] = useState(Date.now())
  const [blinkOn, setBlinkOn] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (id && current?.project_id !== id) void loadProject(id)
  }, [id, current, loadProject])

  useEffect(() => {
    if (mode !== 'blink') return
    const t = setInterval(() => setBlinkOn((b) => !b), 700)
    return () => clearInterval(t)
  }, [mode])

  const generate = async () => {
    if (!id) return
    setBusy(true)
    try {
      const r = await api.compositePreview(id)
      setResult(r)
      setVersion(Date.now())
      log(
        `合成プレビュー生成: ${r.layers_used}レイヤー / 差分 ${(r.diff_pixel_ratio * 100).toFixed(2)}%`,
      )
    } catch (e) {
      log(`プレビュー生成に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    void generate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (!id || !current) return <p className="p-8 text-neutral-400">読み込み中...</p>

  const originalUrl = fileUrl(id, 'source/normalized.png', 1)
  const compositeUrl = fileUrl(id, 'previews/composite_preview.png', version)
  const diffUrl = fileUrl(id, 'previews/difference_preview.png', version)
  const motionUrl = fileUrl(id, 'previews/motion_check.png', version)
  const motionGifUrl = fileUrl(id, 'previews/motion_preview.gif', version)

  const shown =
    mode === 'motion'
      ? motionUrl
      : mode === 'motion_anim'
        ? motionGifUrl
        : mode === 'original' || (mode === 'blink' && blinkOn)
          ? originalUrl
          : compositeUrl

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs">
        <div className="inline-flex overflow-hidden rounded border border-neutral-600">
          {(
            [
              ['composite', '合成'],
              ['original', '元画像'],
              ['difference', '差分'],
              ['blink', 'A/B比較'],
              ['motion', 'モーション'],
              ['motion_anim', 'モーション再生'],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1 ${mode === m ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <button className="btn" onClick={() => void generate()} disabled={busy}>
          {busy ? '生成中...' : '再生成'}
        </button>
        {mode === 'motion' && (
          <span className="ml-4 text-neutral-400">
            マゼンタ = 揺れものを動かすと欠ける領域(パーツ編集画面の「モーションチェック」で生成)
          </span>
        )}
        {mode === 'motion_anim' && (
          <span className="ml-4 text-neutral-400">
            疑似モーションの再生(髪・装飾をサイン波で揺らしたGIF。モーションチェック実行時に生成)
          </span>
        )}
        {result && mode !== 'motion' && mode !== 'motion_anim' && (
          <span className="ml-4 text-neutral-400">
            使用レイヤー: {result.layers_used} / 差分ピクセル: {result.diff_pixel_count}(
            {(result.diff_pixel_ratio * 100).toFixed(2)}%)
            {result.diff_pixel_ratio > 0.05 && (
              <span className="ml-2 text-red-400">⚠ 差分が大きいです。マスクを確認してください</span>
            )}
          </span>
        )}
      </div>
      <div className="checkerboard relative min-h-0 flex-1 overflow-auto p-4">
        <div className="relative mx-auto w-fit">
          <img src={shown} alt="preview" className="max-h-[80vh] object-contain" />
          {mode === 'difference' && (
            <img
              src={diffUrl}
              alt="difference"
              className="absolute inset-0 max-h-[80vh] object-contain"
            />
          )}
        </div>
      </div>
    </div>
  )
}
