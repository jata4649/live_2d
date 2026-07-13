// マジックワンド(色域選択)。
// クリック点の色から、許容差以内の近似色領域を選択する。
// contiguous=true: クリック点から連結する領域のみ(flood fill)
// contiguous=false: 画像全体から近似色ピクセルを選択

/** 選択領域を Uint8Array(1=選択)で返す。 */
export function magicWandRegion(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  seedX: number,
  seedY: number,
  tolerance: number,
  contiguous: boolean,
): Uint8Array {
  const region = new Uint8Array(width * height)
  const sx = Math.round(seedX)
  const sy = Math.round(seedY)
  if (sx < 0 || sy < 0 || sx >= width || sy >= height) return region

  const si = (sy * width + sx) * 4
  const sr = data[si]
  const sg = data[si + 1]
  const sb = data[si + 2]
  const sa = data[si + 3]
  if (sa <= 8) return region // 透明部クリックは無効

  const tol2 = tolerance * tolerance * 3 // 3ch ユークリッド距離の2乗
  const matches = (i: number): boolean => {
    if (data[i + 3] <= 8) return false // 透明部は選択しない
    const dr = data[i] - sr
    const dg = data[i + 1] - sg
    const db = data[i + 2] - sb
    return dr * dr + dg * dg + db * db <= tol2
  }

  if (!contiguous) {
    for (let p = 0; p < width * height; p++) {
      if (matches(p * 4)) region[p] = 1
    }
    return region
  }

  // BFS flood fill
  const queue = new Int32Array(width * height)
  let head = 0
  let tail = 0
  const seed = sy * width + sx
  region[seed] = 1
  queue[tail++] = seed
  while (head < tail) {
    const p = queue[head++]
    const x = p % width
    const y = (p / width) | 0
    // 4近傍
    if (x > 0 && !region[p - 1] && matches((p - 1) * 4)) {
      region[p - 1] = 1
      queue[tail++] = p - 1
    }
    if (x < width - 1 && !region[p + 1] && matches((p + 1) * 4)) {
      region[p + 1] = 1
      queue[tail++] = p + 1
    }
    if (y > 0 && !region[p - width] && matches((p - width) * 4)) {
      region[p - width] = 1
      queue[tail++] = p - width
    }
    if (y < height - 1 && !region[p + width] && matches((p + width) * 4)) {
      region[p + width] = 1
      queue[tail++] = p + width
    }
  }
  return region
}

/** 選択領域をマスク canvas へ描き込む(add=白 / erase=黒)。 */
export function paintRegion(
  ctx: CanvasRenderingContext2D,
  region: Uint8Array,
  width: number,
  height: number,
  mode: 'add' | 'erase',
): void {
  const tmp = document.createElement('canvas')
  tmp.width = width
  tmp.height = height
  const tctx = tmp.getContext('2d')!
  const img = tctx.createImageData(width, height)
  const v = mode === 'add' ? 255 : 0
  for (let p = 0; p < region.length; p++) {
    if (region[p]) {
      const i = p * 4
      img.data[i] = v
      img.data[i + 1] = v
      img.data[i + 2] = v
      img.data[i + 3] = 255
    }
  }
  tctx.putImageData(img, 0, 0)
  ctx.globalCompositeOperation = 'source-over'
  ctx.drawImage(tmp, 0, 0)
}
