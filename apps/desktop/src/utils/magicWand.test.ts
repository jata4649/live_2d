import { describe, expect, it } from 'vitest'
import { magicWandRegion } from './magicWand'

// 6x4 のテスト画像: 左半分=赤、右半分=青、(5,3)=透明
function makeImage(): { data: Uint8ClampedArray; w: number; h: number } {
  const w = 6
  const h = 4
  const data = new Uint8ClampedArray(w * h * 4)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4
      if (x < 3) {
        data.set([200, 30, 30, 255], i) // 赤
      } else {
        data.set([30, 30, 200, 255], i) // 青
      }
    }
  }
  data[(3 * w + 5) * 4 + 3] = 0 // 透明ピクセル
  return { data, w, h }
}

describe('magicWandRegion', () => {
  it('連結モード: クリック側の色領域のみ選択する', () => {
    const { data, w, h } = makeImage()
    const region = magicWandRegion(data, w, h, 1, 1, 30, true)
    expect(region[1 * w + 1]).toBe(1) // 赤側
    expect(region[1 * w + 4]).toBe(0) // 青側は選ばれない
    // 赤は 3x4=12px すべて選択
    expect(region.reduce((a, b) => a + b, 0)).toBe(12)
  })

  it('非連結モード: 画像全体から近似色を選択する', () => {
    const { data, w, h } = makeImage()
    // 離れた赤があるケースを作る: (5,0) を赤にする
    data.set([200, 30, 30, 255], (0 * w + 5) * 4)
    const region = magicWandRegion(data, w, h, 0, 0, 30, false)
    expect(region[0 * w + 5]).toBe(1) // 非連結の赤も選択
    expect(region[1 * w + 4]).toBe(0)
  })

  it('許容差が大きいと隣の色も選択する', () => {
    const { data, w, h } = makeImage()
    const region = magicWandRegion(data, w, h, 1, 1, 255, true)
    // 全不透明ピクセル(6*4 - 透明1)が選択される
    expect(region.reduce((a, b) => a + b, 0)).toBe(w * h - 1)
  })

  it('透明ピクセルは選択されない・透明クリックは無効', () => {
    const { data, w, h } = makeImage()
    const region = magicWandRegion(data, w, h, 1, 1, 255, true)
    expect(region[3 * w + 5]).toBe(0)
    const none = magicWandRegion(data, w, h, 5, 3, 50, true)
    expect(none.reduce((a, b) => a + b, 0)).toBe(0)
  })

  it('画像外クリックは空選択', () => {
    const { data, w, h } = makeImage()
    const region = magicWandRegion(data, w, h, -1, 10, 50, true)
    expect(region.reduce((a, b) => a + b, 0)).toBe(0)
  })
})
