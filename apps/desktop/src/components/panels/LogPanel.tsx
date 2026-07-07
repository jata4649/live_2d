// 処理ログ / 品質チェック結果(タブ切替)。
import { useEffect, useRef, useState } from 'react'
import { useJobStore } from '../../stores/jobStore'
import { usePartsStore } from '../../stores/partsStore'
import type { QualityReport, Severity } from '../../types'

const SEVERITY_COLOR: Record<Severity, string> = {
  high: 'text-red-400',
  medium: 'text-amber-400',
  low: 'text-yellow-200',
  info: 'text-neutral-400',
}

export function LogPanel({ report }: { report: QualityReport | null }) {
  const [tab, setTab] = useState<'log' | 'quality'>('log')
  const logs = useJobStore((s) => s.logs)
  const activeJob = useJobStore((s) => s.activeJob)
  const select = usePartsStore((s) => s.select)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-neutral-700 px-3 py-1">
        <button
          className={`text-xs ${tab === 'log' ? 'font-bold text-indigo-300' : 'text-neutral-400'}`}
          onClick={() => setTab('log')}
        >
          処理ログ
        </button>
        <button
          className={`text-xs ${tab === 'quality' ? 'font-bold text-indigo-300' : 'text-neutral-400'}`}
          onClick={() => setTab('quality')}
        >
          品質チェック {report ? `(${report.overall_score}点)` : ''}
        </button>
        {activeJob && (
          <span className="ml-auto flex items-center gap-2 text-xs text-indigo-300">
            <span className="h-2 w-24 overflow-hidden rounded bg-neutral-700">
              <span
                className="block h-full bg-indigo-500 transition-all"
                style={{ width: `${activeJob.progress * 100}%` }}
              />
            </span>
            {activeJob.message}
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2 font-mono text-[11px]">
        {tab === 'log' &&
          logs.map((l, i) => (
            <div key={i} className={l.level === 'error' ? 'text-red-400' : 'text-neutral-300'}>
              <span className="text-neutral-600">{l.time}</span> {l.message}
            </div>
          ))}
        {tab === 'log' && <div ref={bottomRef} />}
        {tab === 'quality' && !report && (
          <p className="text-neutral-500">品質チェックが未実行です</p>
        )}
        {tab === 'quality' &&
          report?.issues.map((issue, i) => (
            <div
              key={i}
              className="cursor-pointer py-0.5 hover:bg-neutral-800"
              onClick={() => issue.part_id && select(issue.part_id)}
            >
              <span className={SEVERITY_COLOR[issue.severity]}>
                [{issue.severity.toUpperCase()}]
              </span>{' '}
              <span className="text-neutral-500">{issue.code}</span> {issue.message}
              {issue.suggested_fix && (
                <span className="text-neutral-500"> → {issue.suggested_fix}</span>
              )}
            </div>
          ))}
        {tab === 'quality' && report && report.issues.length === 0 && (
          <p className="text-emerald-400">問題は検出されませんでした</p>
        )}
      </div>
    </div>
  )
}
