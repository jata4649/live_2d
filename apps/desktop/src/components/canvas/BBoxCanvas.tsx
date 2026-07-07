// bbox 編集キャンバス。
// 座標規約: 保存座標は常に正規化画像ピクセル座標。ズーム/パンはビュー変換のみ。
import Konva from 'konva'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Image as KImage, Layer, Rect, Stage, Transformer } from 'react-konva'
import { maskUrl } from '../../api/client'
import { usePartsStore } from '../../stores/partsStore'
import type { Part } from '../../types'

interface Props {
  projectId: string
  imageUrl: string
  imageWidth: number
  imageHeight: number
  showAllBoxes: boolean
  showMask: boolean
}

function useHtmlImage(url: string | null): HTMLImageElement | null {
  const [img, setImg] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    if (!url) {
      setImg(null)
      return
    }
    const el = new window.Image()
    el.onload = () => setImg(el)
    el.onerror = () => setImg(null)
    el.src = url
    return () => setImg(null)
  }, [url])
  return img
}

export function BBoxCanvas({
  projectId,
  imageUrl,
  imageWidth,
  imageHeight,
  showAllBoxes,
  showMask,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 400, h: 400 })
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 })
  const plan = usePartsStore((s) => s.plan)
  const selectedId = usePartsStore((s) => s.selectedId)
  const select = usePartsStore((s) => s.select)
  const updatePartDeep = usePartsStore((s) => s.updatePartDeep)
  const maskVersion = usePartsStore((s) => s.maskVersion)

  const image = useHtmlImage(imageUrl)
  const selected = plan?.parts.find((p) => p.id === selectedId) ?? null
  const maskImg = useHtmlImage(
    showMask && selected ? maskUrl(projectId, selected.id, maskVersion) : null,
  )

  const rectRef = useRef<Konva.Rect>(null)
  const trRef = useRef<Konva.Transformer>(null)

  // コンテナサイズ追従
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // 初期フィット
  useEffect(() => {
    if (!imageWidth || !imageHeight) return
    const scale = Math.min(size.w / imageWidth, size.h / imageHeight) * 0.95
    setView({
      scale,
      x: (size.w - imageWidth * scale) / 2,
      y: (size.h - imageHeight * scale) / 2,
    })
  }, [imageWidth, imageHeight, size.w, size.h])

  // Transformer を選択 rect にアタッチ
  useEffect(() => {
    if (trRef.current && rectRef.current) {
      trRef.current.nodes([rectRef.current])
      trRef.current.getLayer()?.batchDraw()
    }
  }, [selectedId, selected?.segmentation.bbox])

  const onWheel = (e: Konva.KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const stage = e.target.getStage()
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return
    const oldScale = view.scale
    const factor = e.evt.deltaY > 0 ? 1 / 1.1 : 1.1
    const newScale = Math.max(0.05, Math.min(20, oldScale * factor))
    // ポインタ位置を中心にズーム
    const mousePoint = {
      x: (pointer.x - view.x) / oldScale,
      y: (pointer.y - view.y) / oldScale,
    }
    setView({
      scale: newScale,
      x: pointer.x - mousePoint.x * newScale,
      y: pointer.y - mousePoint.y * newScale,
    })
  }

  const commitBBox = (part: Part, x: number, y: number, w: number, h: number) => {
    const bbox: [number, number, number, number] = [
      Math.round(x),
      Math.round(y),
      Math.max(1, Math.round(w)),
      Math.max(1, Math.round(h)),
    ]
    updatePartDeep(part.id, (p) => ({
      ...p,
      segmentation: { ...p.segmentation, bbox },
    }))
  }

  const otherParts = useMemo(
    () =>
      showAllBoxes && plan
        ? plan.parts.filter((p) => p.id !== selectedId && p.segmentation.bbox)
        : [],
    [showAllBoxes, plan, selectedId],
  )

  return (
    <div ref={containerRef} className="checkerboard h-full w-full overflow-hidden">
      <Stage
        width={size.w}
        height={size.h}
        scaleX={view.scale}
        scaleY={view.scale}
        x={view.x}
        y={view.y}
        draggable
        onDragEnd={(e) => {
          if (e.target === e.target.getStage()) {
            setView((v) => ({ ...v, x: e.target.x(), y: e.target.y() }))
          }
        }}
        onWheel={onWheel}
        onMouseDown={(e) => {
          if (e.target === e.target.getStage() || e.target.name() === 'bg-image') {
            select(null)
          }
        }}
      >
        <Layer>
          {image && <KImage name="bg-image" image={image} />}
          {maskImg && selected && (
            <KImage image={maskImg} opacity={0.45} globalCompositeOperation="screen" />
          )}
          {otherParts.map((p) => {
            const [x, y, w, h] = p.segmentation.bbox!
            return (
              <Rect
                key={p.id}
                x={x}
                y={y}
                width={w}
                height={h}
                stroke="#818cf8"
                strokeWidth={1 / view.scale}
                opacity={0.35}
                onClick={() => select(p.id)}
              />
            )
          })}
          {selected?.segmentation.bbox && (
            <>
              <Rect
                ref={rectRef}
                x={selected.segmentation.bbox[0]}
                y={selected.segmentation.bbox[1]}
                width={selected.segmentation.bbox[2]}
                height={selected.segmentation.bbox[3]}
                stroke="#f472b6"
                strokeWidth={2 / view.scale}
                draggable={!selected.locked}
                onDragEnd={(e) =>
                  commitBBox(
                    selected,
                    e.target.x(),
                    e.target.y(),
                    selected.segmentation.bbox![2],
                    selected.segmentation.bbox![3],
                  )
                }
                onTransformEnd={(e) => {
                  const node = e.target
                  const sx = node.scaleX()
                  const sy = node.scaleY()
                  node.scaleX(1)
                  node.scaleY(1)
                  commitBBox(
                    selected,
                    node.x(),
                    node.y(),
                    node.width() * sx,
                    node.height() * sy,
                  )
                }}
              />
              {!selected.locked && (
                <Transformer
                  ref={trRef}
                  rotateEnabled={false}
                  flipEnabled={false}
                  boundBoxFunc={(_, newBox) =>
                    newBox.width < 2 || newBox.height < 2
                      ? { ..._, width: 2, height: 2 }
                      : newBox
                  }
                />
              )}
            </>
          )}
        </Layer>
      </Stage>
    </div>
  )
}
