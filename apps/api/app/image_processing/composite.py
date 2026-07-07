"""レイヤー合成。"""
from __future__ import annotations

import numpy as np
from PIL import Image


def composite_layers(layers: list[np.ndarray], size: tuple[int, int]) -> np.ndarray:
    """RGBA レイヤー群を下から順にアルファ合成する。

    layers は z_order 昇順(先頭が最背面)で渡すこと。
    size は (width, height)。
    """
    w, h = size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for layer in layers:
        img = Image.fromarray(layer, "RGBA")
        canvas = Image.alpha_composite(canvas, img)
    return np.asarray(canvas)
