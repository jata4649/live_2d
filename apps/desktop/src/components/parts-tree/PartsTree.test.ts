import { describe, expect, it } from 'vitest'
import type { Part } from '../../types'
import { buildTree } from './PartsTree'

function part(id: string, group: string, z: number): Part {
  return {
    id,
    name_jp: id,
    name_en: id,
    group,
    z_order: z,
    visible: true,
    locked: false,
    required: false,
    part_type: 'other',
    visual_description: '',
    segmentation: {
      method: 'manual_box',
      bbox: null,
      positive_points: [],
      negative_points: [],
      text_prompt: '',
    },
    files: { mask_path: '', layer_path: '' },
    live2d: { usage: [], parent_deformer_hint: '', physics_hint: '' },
    processing: {
      overlap_bleed_px: 0,
      edge_feather_px: 0,
      needs_inpaint_under: false,
      inpaint_reason: '',
    },
    quality: { priority: 'normal', manual_review_required: false, score: null },
  }
}

describe('buildTree', () => {
  it('group パスから階層を構築する', () => {
    const tree = buildTree([
      part('front_hair', 'Hair/Front', 120),
      part('back_hair', 'Hair/Back', 10),
      part('face_base', 'Face', 70),
    ])
    const hair = tree.children.find((c) => c.name === 'Hair')!
    expect(hair).toBeDefined()
    expect(hair.children.map((c) => c.name).sort()).toEqual(['Back', 'Front'])
    expect(tree.children.find((c) => c.name === 'Face')!.parts[0].id).toBe('face_base')
  })

  it('z_order 降順(手前が先)に並ぶ', () => {
    const tree = buildTree([
      part('low', 'G', 1),
      part('high', 'G', 100),
      part('mid', 'G', 50),
    ])
    const g = tree.children.find((c) => c.name === 'G')!
    expect(g.parts.map((p) => p.id)).toEqual(['high', 'mid', 'low'])
  })

  it('グループなしパーツはルート直下に置く', () => {
    const tree = buildTree([part('solo', '', 5)])
    expect(tree.parts.map((p) => p.id)).toEqual(['solo'])
  })
})
