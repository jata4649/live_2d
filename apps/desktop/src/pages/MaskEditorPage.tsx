// マスク編集画面。
// 実装方針:
// - オフスクリーン canvas にフル解像度のマスク(白=前景)を保持
// - 表示はビュー変換(scale/offset)のみ。保存座標は常に画像ピクセル座標
// - Undo/Redo はストローク履歴を初期マスクから再生する方式
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, fileUrl, maskUrl } from '../api/client'
import { useJobStore } from '../stores/jobStore'
import { usePartsStore } from '../stores/partsStore'
import { useProjectStore } from '../stores/projectStore'
import { magicWandRegion, paintRegion } from '../utils/magicWand'

interface Stroke {
  tool: 'brush' | 'lasso' | 'wand'
  mode: 'add' | 'erase'
  size: number
  hardness: number // 0.1〜1.0(1.0 = ハードエッジ)。lasso/wand では未使用
  points: { x: number; y: number }[] // wand ではクリック点1つ
  tolerance?: number // wand: 色の許容差
  contiguous?: boolean // wand: 連結領域のみ
}

type Tool = 'add' | 'erase' | 'lasso-add' | 'lasso-erase' | 'wand-add' | 'wand-erase' | 'pan'

export function MaskEditorPage() {
  const { id, partId } = useParams<{ id: string; partId: string }>()
  const navigate = useNavigate()
  const { current, loadProject } = useProjectStore()
  const bumpMaskVersion = usePartsStore((s) => s.bumpMaskVersion)
  const { log } = useJobStore()

  const containerRef = useRef<HTMLDivElement>(null)
  const viewCanvasRef = useRef<HTMLCanvasElement>(null)
  const maskCanvasRef = useRef<HTMLCanvasElement | null>(null) // フル解像度マスク
  const baseImageRef = useRef<HTMLImageElement | null>(null)
  const initialMaskRef = useRef<HTMLImageElement | null>(null)

  const [tool, setTool] = useState<Tool>('add')
  const [brushSize, setBrushSize] = useState(24)
  const [hardness, setHardness] = useState(100) // %
  const [tolerance, setTolerance] = useState(30) // マジックワンドの色許容差
  const [contiguous, setContiguous] = useState(true)
  const baseDataRef = useRef<ImageData | null>(null) // ワンド用の元画像ピクセル
  const [showMask, setShowMask] = useState(true)
  const [baseOpacity, setBaseOpacity] = useState(1)
  const [view, setView] = useState({ scale: 0.5, x: 0, y: 0 })
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [redoStack, setRedoStack] = useState<Stroke[]>([])
  const [dirty, setDirty] = useState(false)
  const [ready, setReady] = useState(false)
  const drawingRef = useRef<Stroke | null>(null)
  const panRef = useRef<{ x: number; y: number } | null>(null)

  const width = current?.source_image.width ?? 0
  const height = current?.source_image.height ?? 0

  // 画像とマスクのロード
  useEffect(() => {
    if (!id) return
    if (current?.project_id !== id) void loadProject(id)
  }, [id, current, loadProject])

  useEffect(() => {
    if (!id || !partId || !width) return
    const base = new Image()
    base.onload = () => {
      baseImageRef.current = base
      // マジックワンド用に元画像のピクセルをキャッシュ
      const bc = document.createElement('canvas')
      bc.width = width
      bc.height = height
      const bctx = bc.getContext('2d')!
      bctx.drawImage(base, 0, 0)
      baseDataRef.current = bctx.getImageData(0, 0, width, height)
      const maskImg = new Image()
      const initMask = () => {
        const mc = document.createElement('canvas')
        mc.width = width
        mc.height = height
        const ctx = mc.getContext('2d')!
        ctx.fillStyle = 'black'
        ctx.fillRect(0, 0, width, height)
        if (initialMaskRef.current) ctx.drawImage(initialMaskRef.current, 0, 0)
        maskCanvasRef.current = mc
        setReady(true)
        fitView()
      }
      maskImg.onload = () => {
        initialMaskRef.current = maskImg
        initMask()
      }
      maskImg.onerror = () => {
        initialMaskRef.current = null
        initMask() // マスク未生成なら黒(空)から開始
      }
      maskImg.src = maskUrl(id, partId)
    }
    base.src = fileUrl(id, 'source/normalized.png', 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, partId, width, height])

  const fitView = useCallback(() => {
    const el = containerRef.current
    if (!el || !width) return
    const scale = Math.min(el.clientWidth / width, el.clientHeight / height) * 0.95
    setView({
      scale,
      x: (el.clientWidth - width * scale) / 2,
      y: (el.clientHeight - height * scale) / 2,
    })
  }, [width, height])

  // マスク canvas を初期状態 + strokes から再構築(Undo/Redo 用)
  const rebuildMask = useCallback(
    (strokeList: Stroke[]) => {
      const mc = maskCanvasRef.current
      if (!mc) return
      const ctx = mc.getContext('2d')!
      ctx.globalCompositeOperation = 'source-over'
      ctx.fillStyle = 'black'
      ctx.fillRect(0, 0, mc.width, mc.height)
      if (initialMaskRef.current) ctx.drawImage(initialMaskRef.current, 0, 0)
      for (const s of strokeList) applyStroke(ctx, s, baseDataRef.current)
    },
    [],
  )

  // 描画ループ
  const render = useCallback(() => {
    const canvas = viewCanvasRef.current
    const el = containerRef.current
    if (!canvas || !el) return
    canvas.width = el.clientWidth
    canvas.height = el.clientHeight
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.save()
    ctx.translate(view.x, view.y)
    ctx.scale(view.scale, view.scale)
    if (baseImageRef.current) {
      ctx.globalAlpha = baseOpacity
      ctx.drawImage(baseImageRef.current, 0, 0)
      ctx.globalAlpha = 1
    }
    if (showMask && maskCanvasRef.current) {
      // マスクを赤半透明で重畳(白部分のみ)
      const tint = document.createElement('canvas')
      tint.width = width
      tint.height = height
      const tctx = tint.getContext('2d')!
      tctx.drawImage(maskCanvasRef.current, 0, 0)
      tctx.globalCompositeOperation = 'source-in'
      // 黒地に白マスクのため、輝度をアルファ化する
      tctx.globalCompositeOperation = 'multiply'
      tctx.fillStyle = '#f43f5e'
      tctx.fillRect(0, 0, width, height)
      ctx.globalAlpha = 0.45
      ctx.globalCompositeOperation = 'screen'
      ctx.drawImage(tint, 0, 0)
      ctx.globalCompositeOperation = 'source-over'
      ctx.globalAlpha = 1
    }
    // 投げ縄のプレビュー(ドラッグ中のみ)
    const drawing = drawingRef.current
    if (drawing?.tool === 'lasso' && drawing.points.length > 1) {
      ctx.strokeStyle = drawing.mode === 'add' ? '#4ade80' : '#f87171'
      ctx.lineWidth = 1.5 / view.scale
      ctx.setLineDash([6 / view.scale, 4 / view.scale])
      ctx.beginPath()
      ctx.moveTo(drawing.points[0].x, drawing.points[0].y)
      for (const p of drawing.points) ctx.lineTo(p.x, p.y)
      ctx.stroke()
      ctx.setLineDash([])
    }
    ctx.restore()
  }, [view, showMask, baseOpacity, width, height])

  useEffect(() => {
    render()
  }, [render, strokes, ready])

  useEffect(() => {
    const onResize = () => render()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [render])

  const toImageCoords = (e: React.PointerEvent): { x: number; y: number } => {
    const rect = viewCanvasRef.current!.getBoundingClientRect()
    return {
      x: (e.clientX - rect.left - view.x) / view.scale,
      y: (e.clientY - rect.top - view.y) / view.scale,
    }
  }

  const onPointerDown = (e: React.PointerEvent) => {
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    if (tool === 'pan' || e.button === 1) {
      panRef.current = { x: e.clientX - view.x, y: e.clientY - view.y }
      return
    }
    const p = toImageCoords(e)
    if (tool === 'wand-add' || tool === 'wand-erase') {
      // ワンドはクリック一発で確定(ドラッグなし)
      const stroke: Stroke = {
        tool: 'wand',
        mode: tool === 'wand-add' ? 'add' : 'erase',
        size: 0,
        hardness: 1,
        points: [p],
        tolerance,
        contiguous,
      }
      const ctx = maskCanvasRef.current?.getContext('2d')
      if (ctx) {
        applyStroke(ctx, stroke, baseDataRef.current)
        render()
      }
      setStrokes((s) => [...s, stroke])
      setRedoStack([])
      setDirty(true)
      return
    }
    if (tool === 'lasso-add' || tool === 'lasso-erase') {
      drawingRef.current = {
        tool: 'lasso',
        mode: tool === 'lasso-add' ? 'add' : 'erase',
        size: 0,
        hardness: 1,
        points: [p],
      }
      return
    }
    const stroke: Stroke = {
      tool: 'brush',
      mode: tool === 'add' ? 'add' : 'erase',
      size: brushSize,
      hardness: hardness / 100,
      points: [p],
    }
    drawingRef.current = stroke
    const ctx = maskCanvasRef.current?.getContext('2d')
    if (ctx) {
      applyStroke(ctx, { ...stroke, points: [p] }) // 始点を即スタンプ
      render()
    }
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (panRef.current) {
      setView((v) => ({ ...v, x: e.clientX - panRef.current!.x, y: e.clientY - panRef.current!.y }))
      return
    }
    const stroke = drawingRef.current
    if (!stroke || !maskCanvasRef.current) return
    stroke.points.push(toImageCoords(e))
    if (stroke.tool === 'lasso') {
      render() // プレビューのみ(確定は pointerup)
      return
    }
    const ctx = maskCanvasRef.current.getContext('2d')!
    applyStroke(ctx, {
      ...stroke,
      points: stroke.points.slice(-2), // 差分描画
    })
    render()
  }

  const onPointerUp = () => {
    panRef.current = null
    const stroke = drawingRef.current
    if (!stroke) return
    if (stroke.tool === 'lasso' && maskCanvasRef.current) {
      if (stroke.points.length >= 3) {
        applyStroke(maskCanvasRef.current.getContext('2d')!, stroke)
      }
    }
    drawingRef.current = null
    if (stroke.tool === 'lasso' && stroke.points.length < 3) {
      render() // プレビュー線を消すだけ
      return
    }
    setStrokes((s) => [...s, stroke])
    setRedoStack([])
    setDirty(true)
    render()
  }

  const onWheel = (e: React.WheelEvent) => {
    const rect = viewCanvasRef.current!.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    const factor = e.deltaY > 0 ? 1 / 1.1 : 1.1
    setView((v) => {
      const scale = Math.max(0.05, Math.min(20, v.scale * factor))
      const ix = (px - v.x) / v.scale
      const iy = (py - v.y) / v.scale
      return { scale, x: px - ix * scale, y: py - iy * scale }
    })
  }

  const undo = () => {
    if (!strokes.length) return
    const next = strokes.slice(0, -1)
    setRedoStack((r) => [...r, strokes[strokes.length - 1]])
    setStrokes(next)
    rebuildMask(next)
    render()
    setDirty(true)
  }

  const redo = () => {
    if (!redoStack.length) return
    const stroke = redoStack[redoStack.length - 1]
    const next = [...strokes, stroke]
    setRedoStack((r) => r.slice(0, -1))
    setStrokes(next)
    rebuildMask(next)
    render()
    setDirty(true)
  }

  const saveMask = async () => {
    if (!id || !partId || !maskCanvasRef.current) return
    const blob = await new Promise<Blob>((resolve) =>
      maskCanvasRef.current!.toBlob((b) => resolve(b!), 'image/png'),
    )
    await api.putMask(id, partId, blob)
    log(`${partId} のマスクを保存しました`)
    // レイヤーも自動再生成
    try {
      await api.generateLayer(id, partId)
      log(`${partId} のレイヤーPNGを再生成しました`)
    } catch {
      /* パーツ未保存などは無視 */
    }
    bumpMaskVersion()
    setDirty(false)
  }

  const refine = async (params: Parameters<typeof api.refineMask>[2]) => {
    if (!id || !partId) return
    if (dirty) await saveMask()
    await api.refineMask(id, partId, params)
    log(`${partId} のマスクを後処理しました`)
    // 再読込
    const maskImg = new Image()
    maskImg.onload = () => {
      initialMaskRef.current = maskImg
      setStrokes([])
      setRedoStack([])
      rebuildMask([])
      render()
    }
    maskImg.src = maskUrl(id, partId)
    bumpMaskVersion()
  }

  // ショートカット
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!current) return <p className="p-8 text-neutral-400">読み込み中...</p>

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs">
        <button
          className="btn"
          onClick={() => {
            if (dirty && !confirm('未保存の変更があります。破棄して戻りますか?')) return
            navigate(`/projects/${id}/parts`)
          }}
        >
          ← パーツ編集へ戻る
        </button>
        <span className="font-mono text-neutral-400">{partId}</span>
        <div className="ml-4 inline-flex overflow-hidden rounded border border-neutral-600">
          {(
            [
              ['add', '追加ブラシ'],
              ['erase', '消しブラシ'],
              ['lasso-add', '投げ縄+'],
              ['lasso-erase', '投げ縄−'],
              ['wand-add', 'ワンド+'],
              ['wand-erase', 'ワンド−'],
              ['pan', '移動'],
            ] as const
          ).map(([t, label]) => (
            <button
              key={t}
              onClick={() => setTool(t)}
              className={`px-3 py-1 ${tool === t ? 'bg-indigo-600' : 'bg-neutral-800 hover:bg-neutral-700'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1">
          サイズ {brushSize}px
          <input
            type="range"
            min={2}
            max={200}
            value={brushSize}
            onChange={(e) => setBrushSize(Number(e.target.value))}
          />
        </label>
        <label className="flex items-center gap-1" title="100%でハードエッジ、下げるとぼけたブラシになります">
          硬さ {hardness}%
          <input
            type="range"
            min={10}
            max={100}
            value={hardness}
            onChange={(e) => setHardness(Number(e.target.value))}
          />
        </label>
        {(tool === 'wand-add' || tool === 'wand-erase') && (
          <>
            <label className="flex items-center gap-1" title="クリック点の色との許容差。大きいほど広く選択されます">
              許容差 {tolerance}
              <input
                type="range"
                min={4}
                max={120}
                value={tolerance}
                onChange={(e) => setTolerance(Number(e.target.value))}
              />
            </label>
            <label className="flex items-center gap-1" title="ONでクリック点と連結する領域のみ、OFFで画像全体の近似色を選択">
              <input
                type="checkbox"
                checked={contiguous}
                onChange={(e) => setContiguous(e.target.checked)}
              />
              連結のみ
            </label>
          </>
        )}
        <button className="btn" onClick={undo} disabled={!strokes.length}>
          ↶ Undo
        </button>
        <button className="btn" onClick={redo} disabled={!redoStack.length}>
          ↷ Redo
        </button>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={showMask} onChange={(e) => setShowMask(e.target.checked)} />
          マスク表示
        </label>
        <label className="flex items-center gap-1">
          元画像 {Math.round(baseOpacity * 100)}%
          <input
            type="range"
            min={0}
            max={100}
            value={baseOpacity * 100}
            onChange={(e) => setBaseOpacity(Number(e.target.value) / 100)}
          />
        </label>
        <div className="ml-2 flex gap-1">
          <button className="btn" onClick={() => void refine({ dilate_px: 2 })}>膨張+2</button>
          <button className="btn" onClick={() => void refine({ erode_px: 2 })}>収縮-2</button>
          <button className="btn" onClick={() => void refine({ fill_holes: true })}>穴埋め</button>
          <button className="btn" onClick={() => void refine({ remove_small_noise: true })}>ノイズ除去</button>
          <button className="btn" onClick={() => void refine({ feather_px: 2 })}>ぼかし</button>
        </div>
        <button
          className={`ml-auto rounded px-4 py-1 font-medium ${
            dirty ? 'bg-amber-600 hover:bg-amber-500' : 'bg-neutral-700 text-neutral-400'
          }`}
          onClick={() => void saveMask()}
        >
          {dirty ? '保存(未保存)' : '保存済み'}
        </button>
      </div>
      <div ref={containerRef} className="checkerboard min-h-0 flex-1">
        <canvas
          ref={viewCanvasRef}
          className={tool === 'pan' ? 'cursor-grab' : 'cursor-crosshair'}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onWheel={onWheel}
        />
      </div>
    </div>
  )
}

function applyStroke(
  ctx: CanvasRenderingContext2D,
  stroke: Stroke,
  baseData?: ImageData | null,
) {
  ctx.globalCompositeOperation = 'source-over'
  const color = stroke.mode === 'add' ? 'white' : 'black'
  const pts = stroke.points

  if (stroke.tool === 'wand') {
    if (!baseData) return
    const region = magicWandRegion(
      baseData.data,
      baseData.width,
      baseData.height,
      pts[0].x,
      pts[0].y,
      stroke.tolerance ?? 30,
      stroke.contiguous ?? true,
    )
    paintRegion(ctx, region, baseData.width, baseData.height, stroke.mode)
    return
  }

  if (stroke.tool === 'lasso') {
    if (pts.length < 3) return
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.moveTo(pts[0].x, pts[0].y)
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
    ctx.closePath()
    ctx.fill()
    return
  }

  if (stroke.hardness >= 0.99) {
    // ハードブラシ: 従来どおりの線描画
    ctx.strokeStyle = color
    ctx.fillStyle = color
    ctx.lineWidth = stroke.size
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    if (pts.length === 1) {
      ctx.beginPath()
      ctx.arc(pts[0].x, pts[0].y, stroke.size / 2, 0, Math.PI * 2)
      ctx.fill()
      return
    }
    ctx.beginPath()
    ctx.moveTo(pts[0].x, pts[0].y)
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
    ctx.stroke()
    return
  }

  // ソフトブラシ: 放射状グラデーションのスタンプを軌跡に沿って敷き詰める
  const radius = stroke.size / 2
  const spacing = Math.max(1, stroke.size / 6)
  const stamp = (x: number, y: number) => {
    const g = ctx.createRadialGradient(x, y, radius * stroke.hardness, x, y, radius)
    const rgb = stroke.mode === 'add' ? '255,255,255' : '0,0,0'
    g.addColorStop(0, `rgba(${rgb},1)`)
    g.addColorStop(1, `rgba(${rgb},0)`)
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fill()
  }
  stamp(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i - 1]
    const p1 = pts[i]
    const dist = Math.hypot(p1.x - p0.x, p1.y - p0.y)
    const steps = Math.max(1, Math.floor(dist / spacing))
    for (let s = 1; s <= steps; s++) {
      const t = s / steps
      stamp(p0.x + (p1.x - p0.x) * t, p0.y + (p1.y - p0.y) * t)
    }
  }
}
