// 選択パーツの詳細設定パネル。
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useJobStore } from '../../stores/jobStore'
import { usePartsStore } from '../../stores/partsStore'
import type { Part, SegmentationMethod } from '../../types'

type SegmenterInfo = { method: string; label: string; available: boolean; reason: string }
let segmentersCache: SegmenterInfo[] | null = null

export function PartDetailPanel() {
  const [segmenters, setSegmenters] = useState<SegmenterInfo[]>(segmentersCache ?? [])
  useEffect(() => {
    if (segmentersCache) return
    void api.listSegmenters().then((s) => {
      segmentersCache = s
      setSegmenters(s)
    }).catch(() => {})
  }, [])
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const plan = usePartsStore((s) => s.plan)
  const selectedId = usePartsStore((s) => s.selectedId)
  const updatePart = usePartsStore((s) => s.updatePart)
  const updatePartDeep = usePartsStore((s) => s.updatePartDeep)
  const removePart = usePartsStore((s) => s.removePart)
  const save = usePartsStore((s) => s.save)
  const bumpMaskVersion = usePartsStore((s) => s.bumpMaskVersion)
  const { log } = useJobStore()

  const part = plan?.parts.find((p) => p.id === selectedId)
  if (!part || !projectId) {
    return (
      <div className="p-4 text-xs text-neutral-500">
        パーツを選択すると詳細設定が表示されます
      </div>
    )
  }

  const seg = <K extends keyof Part['segmentation']>(key: K, value: Part['segmentation'][K]) =>
    updatePartDeep(part.id, (p) => ({
      ...p,
      segmentation: { ...p.segmentation, [key]: value },
    }))

  const proc = <K extends keyof Part['processing']>(key: K, value: Part['processing'][K]) =>
    updatePartDeep(part.id, (p) => ({
      ...p,
      processing: { ...p.processing, [key]: value },
    }))

  const runSegmentation = async () => {
    try {
      await save() // bbox 等の編集を反映してから実行
      const res = await api.runSegmentationPart(projectId, part.id)
      res.warnings.forEach((w) => log(`${part.name_jp}: ${w}`))
      log(`${part.name_jp} のマスクを生成しました`)
      bumpMaskVersion()
    } catch (e) {
      log(`マスク生成に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const twinId = (() => {
    const tokens = part.id.split('_')
    for (let i = tokens.length - 1; i >= 0; i--) {
      if (tokens[i] === 'l') return [...tokens.slice(0, i), 'r', ...tokens.slice(i + 1)].join('_')
      if (tokens[i] === 'r') return [...tokens.slice(0, i), 'l', ...tokens.slice(i + 1)].join('_')
    }
    return null
  })()
  const twinExists = twinId != null && plan!.parts.some((p) => p.id === twinId)

  const runMirror = async () => {
    if (!twinId) return
    try {
      await save()
      const res = await api.mirrorMask(projectId, part.id)
      log(
        `ミラーコピー完了: ${part.id} → ${res.twin_part_id}` +
          (res.bbox_updated ? '(bboxも更新)' : ''),
      )
      bumpMaskVersion()
      await usePartsStore.getState().load(projectId) // サーバー側でbboxが更新されるため再読込
    } catch (e) {
      log(`ミラーコピーに失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const runSyncBbox = async () => {
    try {
      await save()
      const res = await api.syncBbox(projectId, part.id)
      log(`bbox をマスク範囲に同期: [${res.bbox.join(', ')}]`)
      await usePartsStore.getState().load(projectId)
    } catch (e) {
      log(`bbox 同期に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  const runLayer = async () => {
    try {
      await save()
      await api.generateLayer(projectId, part.id)
      log(`${part.name_jp} のレイヤーPNGを生成しました`)
    } catch (e) {
      log(`レイヤー生成に失敗: ${e instanceof Error ? e.message : e}`, 'error')
    }
  }

  return (
    <div className="space-y-3 overflow-y-auto p-3 text-xs">
      <div className="text-sm font-bold">{part.name_jp}</div>
      <Field label="ID"><span className="font-mono text-neutral-400">{part.id}</span></Field>

      <Field label="表示名(日本語)">
        <input
          className="input"
          value={part.name_jp}
          onChange={(e) => updatePart(part.id, { name_jp: e.target.value })}
        />
      </Field>
      <Field label="表示名(英語 / PSDレイヤー名)">
        <input
          className="input"
          value={part.name_en}
          onChange={(e) => updatePart(part.id, { name_en: e.target.value })}
        />
      </Field>
      <Field label="グループ(/ 区切り)">
        <input
          className="input"
          value={part.group}
          onChange={(e) => updatePart(part.id, { group: e.target.value })}
        />
      </Field>
      <Field label="レイヤー順(大きいほど手前)">
        <input
          type="number"
          className="input"
          value={part.z_order}
          onChange={(e) => updatePart(part.id, { z_order: Number(e.target.value) })}
        />
      </Field>

      <Field label="セグメンテーション方法">
        <select
          className="input"
          value={part.segmentation.method}
          onChange={(e) => seg('method', e.target.value as SegmentationMethod)}
        >
          {(segmenters.length > 0
            ? segmenters
            : [
                { method: 'manual_box', label: '矩形 + 簡易切り抜き', available: true, reason: '' },
                { method: 'mock', label: 'モック(楕円)', available: true, reason: '' },
              ]
          ).map((s) => (
            <option key={s.method} value={s.method} disabled={!s.available}>
              {s.label}
              {!s.available ? `(${s.reason})` : ''}
            </option>
          ))}
        </select>
      </Field>

      <Field label="矩形 [x, y, w, h]">
        <div className="grid grid-cols-4 gap-1">
          {(part.segmentation.bbox ?? [0, 0, 100, 100]).map((v, i) => (
            <input
              key={i}
              type="number"
              className="input"
              value={v}
              onChange={(e) => {
                const bbox = [...(part.segmentation.bbox ?? [0, 0, 100, 100])] as [
                  number, number, number, number,
                ]
                bbox[i] = Number(e.target.value)
                seg('bbox', bbox)
              }}
            />
          ))}
        </div>
      </Field>

      <Field label="ポイントプロンプト(前景/背景)">
        <div className="flex items-center gap-2 text-neutral-300">
          <span className="text-green-400">
            ● {part.segmentation.positive_points.length}
          </span>
          <span className="text-red-400">
            ● {part.segmentation.negative_points.length}
          </span>
          {(part.segmentation.positive_points.length > 0 ||
            part.segmentation.negative_points.length > 0) && (
            <button
              className="ml-auto rounded border border-neutral-600 px-2 py-0.5 hover:bg-neutral-700"
              onClick={() => {
                seg('positive_points', [])
                seg('negative_points', [])
              }}
            >
              クリア
            </button>
          )}
        </div>
        <div className="mt-1 text-[10px] text-neutral-500">
          キャンバスで Shift+クリック=前景(緑)/ Alt+クリック=背景(赤)、
          点クリックで削除。SAM2・色分離の精度向上に使われます
        </div>
      </Field>

      <Field label={`塗り足し: ${part.processing.overlap_bleed_px}px`}>
        <input
          type="range"
          min={0}
          max={32}
          value={part.processing.overlap_bleed_px}
          onChange={(e) => proc('overlap_bleed_px', Number(e.target.value))}
          className="w-full"
        />
      </Field>
      <Field label={`境界ぼかし: ${part.processing.edge_feather_px}px`}>
        <input
          type="range"
          min={0}
          max={8}
          value={part.processing.edge_feather_px}
          onChange={(e) => proc('edge_feather_px', Number(e.target.value))}
          className="w-full"
        />
      </Field>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={part.processing.needs_inpaint_under}
          onChange={(e) => proc('needs_inpaint_under', e.target.checked)}
        />
        <span>下レイヤーの欠損補完が必要</span>
      </label>
      {part.processing.needs_inpaint_under && (
        <Field label="補完理由">
          <input
            className="input"
            value={part.processing.inpaint_reason}
            onChange={(e) => proc('inpaint_reason', e.target.value)}
          />
        </Field>
      )}

      <Field label="Live2D 用途">
        <div className="text-neutral-400">
          {part.live2d.usage.join(', ') || '-'}
          {part.live2d.parent_deformer_hint && (
            <div>デフォーマ: {part.live2d.parent_deformer_hint}</div>
          )}
          {part.live2d.physics_hint && <div>物理: {part.live2d.physics_hint}</div>}
        </div>
      </Field>

      <div className="space-y-1.5 border-t border-neutral-700 pt-3">
        <button className="btn w-full" onClick={() => void runSegmentation()}>
          このパーツのマスク生成
        </button>
        <button
          className="btn w-full"
          onClick={() => navigate(`/projects/${projectId}/mask/${part.id}`)}
        >
          マスク編集へ
        </button>
        <button
          className="btn w-full"
          title="bbox を生成済みマスクの実範囲(+余白4px)へ吸着させます"
          onClick={() => void runSyncBbox()}
        >
          bboxをマスク範囲に同期
        </button>
        <button className="btn w-full" onClick={() => void runLayer()}>
          レイヤーPNG生成
        </button>
        {twinExists && (
          <button
            className="btn w-full"
            title="このマスクを左右反転して相方パーツへコピーします(bboxも更新)"
            onClick={() => void runMirror()}
          >
            {twinId} へミラーコピー
          </button>
        )}
        <button
          className="w-full rounded border border-red-900 px-2 py-1.5 text-red-400 hover:bg-red-950"
          onClick={() => {
            if (confirm(`パーツ「${part.name_jp}」を削除しますか?`)) removePart(part.id)
          }}
        >
          パーツを削除
        </button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[11px] text-neutral-400">{label}</div>
      {children}
    </div>
  )
}
