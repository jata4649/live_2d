// group パス("Hair/Front")によるツリー表示。
import { useMemo } from 'react'
import { usePartsStore } from '../../stores/partsStore'
import type { Part } from '../../types'

interface TreeGroup {
  name: string
  path: string
  children: TreeGroup[]
  parts: Part[]
}

export function buildTree(parts: Part[]): TreeGroup {
  const root: TreeGroup = { name: '', path: '', children: [], parts: [] }
  const nodes = new Map<string, TreeGroup>([['', root]])
  // z_order 降順(手前が上)
  const sorted = [...parts].sort((a, b) => b.z_order - a.z_order)
  for (const part of sorted) {
    let parent = root
    let path = ''
    for (const seg of part.group.split('/').filter(Boolean)) {
      path = path ? `${path}/${seg}` : seg
      let node = nodes.get(path)
      if (!node) {
        node = { name: seg, path, children: [], parts: [] }
        nodes.set(path, node)
        parent.children.push(node)
      }
      parent = node
    }
    parent.parts.push(part)
  }
  return root
}

export function PartsTree({ maskExists }: { maskExists: (id: string) => boolean }) {
  const plan = usePartsStore((s) => s.plan)
  const tree = useMemo(() => (plan ? buildTree(plan.parts) : null), [plan])
  if (!tree) return <p className="p-3 text-xs text-neutral-500">パーツがありません</p>
  return (
    <div className="p-2 text-sm">
      <GroupNode node={tree} depth={0} maskExists={maskExists} />
    </div>
  )
}

function GroupNode({
  node,
  depth,
  maskExists,
}: {
  node: TreeGroup
  depth: number
  maskExists: (id: string) => boolean
}) {
  return (
    <div>
      {node.name && (
        <div
          className="py-0.5 text-xs font-semibold text-neutral-400"
          style={{ paddingLeft: depth * 12 }}
        >
          📁 {node.name}
        </div>
      )}
      {node.parts.map((p) => (
        <PartRow key={p.id} part={p} depth={depth + (node.name ? 1 : 0)} maskExists={maskExists} />
      ))}
      {node.children.map((c) => (
        <GroupNode key={c.path} node={c} depth={depth + (node.name ? 1 : 0)} maskExists={maskExists} />
      ))}
    </div>
  )
}

function PartRow({
  part,
  depth,
  maskExists,
}: {
  part: Part
  depth: number
  maskExists: (id: string) => boolean
}) {
  const selectedId = usePartsStore((s) => s.selectedId)
  const select = usePartsStore((s) => s.select)
  const updatePart = usePartsStore((s) => s.updatePart)
  const active = selectedId === part.id
  return (
    <div
      className={`flex cursor-pointer items-center gap-1 rounded px-1 py-0.5 ${
        active ? 'bg-indigo-900/60' : 'hover:bg-neutral-700/50'
      }`}
      style={{ paddingLeft: depth * 12 + 4 }}
      onClick={() => select(part.id)}
    >
      <button
        title={part.visible ? '非表示にする' : '表示する'}
        className="w-5 text-xs"
        onClick={(e) => {
          e.stopPropagation()
          updatePart(part.id, { visible: !part.visible })
        }}
      >
        {part.visible ? '👁' : '·'}
      </button>
      <button
        title={part.locked ? 'ロック解除' : 'ロック'}
        className="w-5 text-xs opacity-60"
        onClick={(e) => {
          e.stopPropagation()
          updatePart(part.id, { locked: !part.locked })
        }}
      >
        {part.locked ? '🔒' : ''}
      </button>
      <span className={`flex-1 truncate text-xs ${part.visible ? '' : 'text-neutral-500'}`}>
        {part.name_jp}
      </span>
      <span
        title={maskExists(part.id) ? 'マスク生成済み' : 'マスク未生成'}
        className={`h-2 w-2 rounded-full ${
          maskExists(part.id) ? 'bg-emerald-400' : 'bg-neutral-600'
        }`}
      />
      <span className="w-8 text-right text-[10px] text-neutral-500">{part.z_order}</span>
    </div>
  )
}
