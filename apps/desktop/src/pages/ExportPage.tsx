import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, exportFileUrl, fileUrl } from '../api/client'
import { useJobStore } from '../stores/jobStore'
import { useProjectStore } from '../stores/projectStore'
import type { ExportResult, QualityReport, Severity } from '../types'

const SEVERITY_COLOR: Record<Severity, string> = {
  high: 'bg-red-900 text-red-200',
  medium: 'bg-amber-900 text-amber-200',
  low: 'bg-yellow-900 text-yellow-200',
  info: 'bg-neutral-700 text-neutral-300',
}

export function ExportPage() {
  const { id } = useParams<{ id: string }>()
  const { current, loadProject } = useProjectStore()
  const { log } = useJobStore()
  const [report, setReport] = useState<QualityReport | null>(null)
  const [force, setForce] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [results, setResults] = useState<ExportResult[]>([])
  const [riggingDone, setRiggingDone] = useState(false)

  useEffect(() => {
    if (!id) return
    if (current?.project_id !== id) void loadProject(id)
    void api.qualityCheck(id).then(setReport).catch(() => setReport(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (!id || !current) return <p className="p-8 text-neutral-400">読み込み中...</p>

  const run = async (label: string, fn: () => Promise<ExportResult>) => {
    setBusy(label)
    try {
      const r = await fn()
      setResults((rs) => [r, ...rs])
      r.warnings.forEach((w) => log(`${label}: ${w}`))
      log(`${label} 完了: ${r.output_path}`)
    } catch (e) {
      log(`${label} 失敗: ${e instanceof Error ? e.message : e}`, 'error')
      alert(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  const score = report?.overall_score ?? 0
  const scoreColor =
    score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-lime-400' : score >= 50 ? 'text-amber-400' : 'text-red-400'
  const scoreLabel =
    score >= 90 ? '良好' : score >= 70 ? '軽微な修正推奨' : score >= 50 ? '要修正' : '出力非推奨'

  return (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-2xl font-bold">出力</h1>

      {/* 品質レポート */}
      <section className="mb-8 rounded-lg border border-neutral-700 bg-neutral-800 p-4">
        <div className="mb-3 flex items-center gap-4">
          <h2 className="text-lg font-semibold">品質レポート</h2>
          {report && (
            <span className={`text-3xl font-bold ${scoreColor}`}>
              {score}
              <span className="ml-1 text-sm font-normal">点 / {scoreLabel}</span>
            </span>
          )}
          <div className="ml-auto flex gap-2">
            {report?.issues.some((i) => i.auto_fix_available) && (
              <button
                className="rounded bg-emerald-700 px-2 py-1 text-xs hover:bg-emerald-600"
                onClick={() =>
                  void api.qualityAutofix(id).then(({ applied, report: r }) => {
                    applied.forEach((a) => log(`自動修正: ${a.part_id} — ${a.action}`))
                    setReport(r)
                  })
                }
              >
                自動修正を適用
              </button>
            )}
            <button
              className="btn text-xs"
              onClick={() => void api.qualityCheck(id).then(setReport)}
            >
              再チェック
            </button>
          </div>
        </div>
        <div className="max-h-60 space-y-1 overflow-y-auto">
          {report?.issues.map((issue, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className={`rounded px-1.5 py-0.5 ${SEVERITY_COLOR[issue.severity]}`}>
                {issue.severity}
              </span>
              <div>
                <span className="text-neutral-500">{issue.part_id ?? '-'}</span> {issue.message}
                {issue.suggested_fix && (
                  <div className="text-neutral-500">→ {issue.suggested_fix}</div>
                )}
              </div>
            </div>
          ))}
          {report && report.issues.length === 0 && (
            <p className="text-sm text-emerald-400">問題は検出されませんでした</p>
          )}
        </div>
        {score < 50 && (
          <label className="mt-3 flex items-center gap-2 text-sm text-amber-300">
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            品質スコアが低いことを理解した上で強制出力する
          </label>
        )}
      </section>

      {/* 出力ボタン群 */}
      <section className="mb-8 grid grid-cols-2 gap-3">
        <ExportButton
          label="Live2D Cubism 用 PSD"
          description="live2d_import.psd(グループ階層 / z_order 反映)"
          busy={busy === 'PSD出力'}
          onClick={() => void run('PSD出力', () => api.exportPsd(id, force || score >= 50))}
        />
        <ExportButton
          label="レイヤーPNG一式 (ZIP)"
          description="layers.zip + manifest.json"
          busy={busy === 'ZIP出力'}
          onClick={() => void run('ZIP出力', () => api.exportLayersZip(id, force || score >= 50))}
        />
        <ExportButton
          label="リギング設計書"
          description="rigging_plan.md(推奨パラメータ / デフォーマ構成)"
          busy={busy === 'リギング設計書'}
          onClick={() =>
            void (async () => {
              setBusy('リギング設計書')
              try {
                await api.exportRiggingPlan(id)
                setRiggingDone(true)
                log('リギング設計書を生成しました')
              } finally {
                setBusy(null)
              }
            })()
          }
        />
        <ExportButton
          label="JSON一式"
          description="project.json / parts.json / quality_report.json"
          busy={false}
          onClick={() => {
            window.open(fileUrl(id, 'json/parts.json'), '_blank')
          }}
        />
      </section>

      {/* ダウンロード */}
      <section className="rounded-lg border border-neutral-700 bg-neutral-800 p-4">
        <h2 className="mb-3 text-lg font-semibold">ダウンロード</h2>
        <ul className="space-y-2 text-sm">
          {results.some((r) => r.ok && r.exporter === 'psd_tools') && (
            <li>
              <a className="link" href={exportFileUrl(id, 'live2d_import.psd')}>
                📄 live2d_import.psd
              </a>
              <span className="ml-2 text-xs text-neutral-500">
                Cubism Editor で「ファイル → 開く」から読み込めます
              </span>
            </li>
          )}
          {results.some((r) => r.ok && r.exporter === 'photoshop_script') && (
            <li>
              <a className="link" href={exportFileUrl(id, 'import_script.jsx')}>
                📄 import_script.jsx(Photoshopフォールバック)
              </a>
            </li>
          )}
          {results.some((r) => r.ok && (r.exporter === 'layer_zip' || r.fallback_used)) && (
            <li>
              <a className="link" href={exportFileUrl(id, 'layers.zip')}>
                📦 layers.zip
              </a>
            </li>
          )}
          {riggingDone && (
            <li>
              <a className="link" href={fileUrl(id, 'docs/rigging_plan.md')} target="_blank">
                📝 rigging_plan.md
              </a>
            </li>
          )}
          {results.length === 0 && !riggingDone && (
            <li className="text-neutral-500">出力を実行するとここに表示されます</li>
          )}
        </ul>
        {results.some((r) => r.fallback_used) && (
          <p className="mt-3 rounded bg-amber-950 p-2 text-xs text-amber-300">
            PSD直接生成に失敗したため Photoshop スクリプトを生成しました。layers.zip を展開し、
            import_script.jsx を Photoshop で実行して PSD を作成してください。
          </p>
        )}
      </section>
    </div>
  )
}

function ExportButton({
  label,
  description,
  busy,
  onClick,
}: {
  label: string
  description: string
  busy: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="rounded-lg border border-neutral-700 bg-neutral-800 p-4 text-left hover:border-indigo-500 disabled:opacity-50"
    >
      <div className="font-medium">{busy ? '出力中...' : label}</div>
      <div className="mt-1 text-xs text-neutral-400">{description}</div>
    </button>
  )
}
