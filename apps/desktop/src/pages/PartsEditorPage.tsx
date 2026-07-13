import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, fileUrl } from '../api/client'
import { BBoxCanvas } from '../components/canvas/BBoxCanvas'
import { LogPanel } from '../components/panels/LogPanel'
import { PartDetailPanel } from '../components/panels/PartDetailPanel'
import { PartsTree } from '../components/parts-tree/PartsTree'
import { useJobStore } from '../stores/jobStore'
import { usePartsStore } from '../stores/partsStore'
import { useProjectStore } from '../stores/projectStore'
import type { Part, QualityReport } from '../types'

export function PartsEditorPage() {
  const { id } = useParams<{ id: string }>()
  const { current, loadProject } = useProjectStore()
  const plan = usePartsStore((s) => s.plan)
  const dirty = usePartsStore((s) => s.dirty)
  const load = usePartsStore((s) => s.load)
  const save = usePartsStore((s) => s.save)
  const addPart = usePartsStore((s) => s.addPart)
  const bumpMaskVersion = usePartsStore((s) => s.bumpMaskVersion)
  const { runJob, log } = useJobStore()
  const [showAllBoxes, setShowAllBoxes] = useState(false)
  const [showMask, setShowMask] = useState(true)
  const [report, setReport] = useState<QualityReport | null>(null)
  const [masks, setMasks] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!id) return
    if (current?.project_id !== id) void loadProject(id)
    void load(id)
    api.getQualityReport(id).then(setReport).catch(() => setReport(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // マスク生成状態の把握(HEAD 代わりに segmentation_tasks を見る簡易版)
  const refreshMasks = useCallback(async () => {
    if (!id || !plan) return
    const found = new Set<string>()
    await Promise.all(
      plan.parts.map(async (p) => {
        const res = await fetch(
          `/api/v1/projects/${id}/files/masks/${p.id}_mask.png`,
          { method: 'HEAD' },
        )
        if (res.ok) found.add(p.id)
      }),
    )
    setMasks(found)
  }, [id, plan])

  useEffect(() => {
    void refreshMasks()
  }, [refreshMasks])

  if (!id || !current) return <p className="p-8 text-neutral-400">読み込み中...</p>

  const runAutoPipeline = async () => {
    await save()
    await runJob(() => api.autoPipeline(id), '全自動仕上げ')
    try {
      const s = await api.pipelineSummary(id)
      s.steps.forEach((st) => log(`${st.step}: ${st.detail}`))
      log(
        `全自動仕上げ完了: 最終スコア ${s.final_score} 点 / ` +
          `モーション穴 ${s.motion_holes_after} 件 / 未割当 ${s.orphan_px_after}px`,
      )
      const r = await api.getQualityReport(id)
      setReport(r)
    } catch {
      /* サマリ未生成(失敗時)はジョブ側のログに任せる */
    }
    bumpMaskVersion()
    await refreshMasks()
  }

  const runAllSegmentation = async () => {
    await save()
    await runJob(() => api.runSegmentationAll(id), 'セグメンテーション一括実行')
    bumpMaskVersion()
    await refreshMasks()
  }

  const runAllLayers = async () => {
    await save()
    await runJob(() => api.generateLayers(id), 'レイヤー一括生成')
  }

  const runQualityCheck = async () => {
    await save()
    const r = await api.qualityCheck(id)
    setReport(r)
    log(`品質チェック完了: ${r.overall_score}点 / issue ${r.issues.length}件`)
  }

  const runInpaint = async () => {
    await save()
    await api.inpaintPlan(id)
    const { results } = await api.inpaintRun(id)
    const done = results.filter((r) => r.status === 'done')
    done.forEach((r) =>
      log(`補完: ${r.target_part_id} ← ${r.occluder_part_id} の下 ${r.region_px}px`),
    )
    log(`欠損補完完了: ${done.length}件実行 / ${results.length - done.length}件スキップ`)
    bumpMaskVersion()
  }

  const runMotionCheck = async () => {
    await save()
    try {
      const r = await api.motionCheck(id)
      if (r.entries.length === 0) {
        log(
          `モーションチェック完了: 穴なし(可動 ${r.checked_parts} パーツ / 振幅 ${r.amplitude_px}px)`,
        )
      } else {
        r.entries.slice(0, 5).forEach((e) =>
          log(
            `穴: ${e.part_id} を (${e.shift[0]}, ${e.shift[1]}) 動かすと ${e.hole_px}px 欠けます`,
            'error',
          ),
        )
        log(
          `モーションチェック完了: 穴 ${r.entries.length}件。プレビュー画面の「モーション」表示、または「欠損補完(簡易)」で対処してください`,
        )
      }
    } catch (e) {
      log(`モーションチェックに失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const runResolveOrphans = async () => {
    await save()
    try {
      const r = await api.resolveOrphans(id)
      if (r.orphan_px_before === 0) {
        log('未割当ピクセルはありません(全ピクセルがいずれかのパーツに所属済み)')
      } else {
        r.assignments.slice(0, 5).forEach((a) =>
          log(`編入: ${a.part_id} へ ${a.pixels}px(${a.components}成分)`),
        )
        log(
          `未割当ピクセル整合完了: ${r.orphan_px_before}px → ${r.orphan_px_after}px。` +
            `レイヤー ${r.layers_regenerated.length} 件を再生成しました`,
        )
        bumpMaskVersion()
      }
    } catch (e) {
      log(`未割当ピクセル整合に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const runMotionFix = async () => {
    await save()
    try {
      const r = await api.motionFix(id)
      r.fills.forEach((f) =>
        log(`穴補完: ${f.moved_part_id} の下(${f.target_part_id})へ ${f.filled_px}px 焼き込み`),
      )
      r.skipped.forEach((s) => log(`スキップ: ${s}`, 'error'))
      log(
        r.report_after.entries.length === 0
          ? `モーション穴補完完了: 再チェックで穴なし(${r.fills.length}件補完)`
          : `モーション穴補完完了: 残り穴 ${r.report_after.entries.length}件`,
      )
    } catch (e) {
      log(`モーション穴補完に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const addEmptyPart = () => {
    const n = (plan?.parts.length ?? 0) + 1
    const w = current.source_image.width
    const h = current.source_image.height
    const part: Part = {
      id: `custom_part_${String(n).padStart(2, '0')}`,
      name_jp: `新規パーツ${n}`,
      name_en: `Custom Part ${n}`,
      group: 'Custom',
      z_order: 200,
      visible: true,
      locked: false,
      required: false,
      part_type: 'other',
      visual_description: '',
      segmentation: {
        method: 'manual_box',
        bbox: [Math.round(w * 0.4), Math.round(h * 0.4), Math.round(w * 0.2), Math.round(h * 0.2)],
        positive_points: [],
        negative_points: [],
        text_prompt: '',
      },
      files: { mask_path: `masks/custom_part_${n}_mask.png`, layer_path: `layers/custom_part_${n}.png` },
      live2d: { usage: [], parent_deformer_hint: '', physics_hint: '' },
      processing: {
        overlap_bleed_px: 4,
        edge_feather_px: 1,
        needs_inpaint_under: false,
        inpaint_reason: '',
      },
      quality: { priority: 'normal', manual_review_required: false, score: null },
    }
    addPart(part)
  }

  return (
    <div className="flex h-full flex-col">
      {/* ツールバー */}
      <div className="flex items-center gap-2 border-b border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs">
        <button
          className="rounded bg-indigo-600 px-3 py-1 font-medium hover:bg-indigo-500"
          title="セグメント → レイヤー → 未割当整合 → 欠損補完 → モーション穴補完 → 品質チェック → 自動修正 を一括実行します"
          onClick={() => void runAutoPipeline()}
        >
          ★ 全自動仕上げ
        </button>
        <button className="btn" onClick={() => void runAllSegmentation()}>
          全マスク一括生成
        </button>
        <button className="btn" onClick={() => void runAllLayers()}>
          全レイヤー生成
        </button>
        <button className="btn" onClick={() => void runQualityCheck()}>
          品質チェック
        </button>
        <button
          className="btn"
          title="髪の下の額など、動かすと見える領域を簡易補完します"
          onClick={() => void runInpaint()}
        >
          欠損補完(簡易)
        </button>
        <button
          className="btn"
          title="髪・装飾を疑似的に揺らし、動かしたとき欠ける領域(穴)を検出します(要レイヤー生成)"
          onClick={() => void runMotionCheck()}
        >
          モーションチェック
        </button>
        <button
          className="btn"
          title="モーションチェックの穴を、下のレイヤーへ自動で塗って埋めます"
          onClick={() => void runMotionFix()}
        >
          穴を自動補完
        </button>
        <button
          className="btn"
          title="どのマスクにも入っていない元画像のピクセルを、隣接と色で最適なパーツへ編入します(合成差分の解消)"
          onClick={() => void runResolveOrphans()}
        >
          未割当ピクセル整合
        </button>
        <button className="btn" onClick={addEmptyPart}>
          + パーツ追加
        </button>
        <label className="ml-4 flex items-center gap-1 text-neutral-300">
          <input
            type="checkbox"
            checked={showAllBoxes}
            onChange={(e) => setShowAllBoxes(e.target.checked)}
          />
          全bbox表示
        </label>
        <label className="flex items-center gap-1 text-neutral-300">
          <input
            type="checkbox"
            checked={showMask}
            onChange={(e) => setShowMask(e.target.checked)}
          />
          マスク重畳
        </label>
        <button
          className={`ml-auto rounded px-4 py-1 font-medium ${
            dirty ? 'bg-amber-600 hover:bg-amber-500' : 'bg-neutral-700 text-neutral-400'
          }`}
          onClick={() => void save().then(() => log('parts.json を保存しました'))}
        >
          {dirty ? '保存(未保存の変更あり)' : '保存済み'}
        </button>
      </div>

      {/* 3ペイン */}
      <div className="flex min-h-0 flex-1">
        <aside className="w-64 shrink-0 overflow-y-auto border-r border-neutral-700 bg-neutral-850 bg-neutral-800/50">
          <PartsTree maskExists={(pid) => masks.has(pid)} />
        </aside>
        <section className="min-w-0 flex-1">
          <BBoxCanvas
            projectId={id}
            imageUrl={fileUrl(id, 'source/normalized.png', 1)}
            imageWidth={current.source_image.width}
            imageHeight={current.source_image.height}
            showAllBoxes={showAllBoxes}
            showMask={showMask}
          />
        </section>
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-neutral-700 bg-neutral-800/50">
          <PartDetailPanel />
        </aside>
      </div>

      {/* 下部ログ */}
      <div className="h-40 shrink-0 border-t border-neutral-700 bg-neutral-800/70">
        <LogPanel report={report} />
      </div>
    </div>
  )
}
