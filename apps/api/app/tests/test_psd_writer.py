"""PSD ライターのラウンドトリップテスト。"""
from __future__ import annotations

import numpy as np
import pytest

psd_tools = pytest.importorskip("psd_tools")


def _layer(color, region, size=64, name="layer", group=""):
    rgba = np.zeros((size, size, 4), np.uint8)
    y0, y1, x0, x1 = region
    rgba[y0:y1, x0:x1] = color
    return {"name": name, "group": group, "visible": True, "rgba": rgba}


def test_psd_roundtrip(tmp_path):
    from psd_tools import PSDImage

    from app.exporters.psd_writer import write_psd

    entries = [
        _layer((255, 0, 0, 255), (0, 32, 0, 32), name="Front Hair", group="Hair/Front"),
        _layer((0, 255, 0, 255), (16, 48, 16, 48), name="Face Base", group="Face"),
        _layer((0, 0, 255, 255), (32, 64, 32, 64), name="Back Hair", group="Hair/Back"),
    ]
    out = tmp_path / "test.psd"
    write_psd(out, 64, 64, entries)

    psd = PSDImage.open(out)
    assert (psd.width, psd.height) == (64, 64)

    layers = [l for l in psd.descendants() if not l.is_group()]
    groups = [l for l in psd.descendants() if l.is_group()]
    assert sorted(l.name for l in layers) == ["Back Hair", "Face Base", "Front Hair"]
    group_names = {g.name for g in groups}
    assert {"Hair", "Front", "Face", "Back"} <= group_names

    # ピクセル検証: Front Hair レイヤーが赤
    front = next(l for l in layers if l.name == "Front Hair")
    pil = front.topil()
    assert pil is not None
    px = pil.convert("RGBA").getpixel((5, 5))
    assert px[0] == 255 and px[3] == 255


def test_psd_layer_order_top_down(tmp_path):
    """entries の先頭が PSD の最前面になる。"""
    from psd_tools import PSDImage

    from app.exporters.psd_writer import write_psd

    entries = [
        _layer((255, 0, 0, 255), (0, 64, 0, 64), name="Top"),
        _layer((0, 0, 255, 255), (0, 64, 0, 64), name="Bottom"),
    ]
    out = tmp_path / "order.psd"
    write_psd(out, 64, 64, entries)
    psd = PSDImage.open(out)
    names = [l.name for l in psd]  # psd-tools は下から上に列挙する
    assert names == ["Bottom", "Top"]

    # 合成画像は Top(赤)が勝つ
    comp = psd.composite()
    assert comp.getpixel((32, 32))[0] > 200


def test_hidden_layer_flag(tmp_path):
    from psd_tools import PSDImage

    from app.exporters.psd_writer import write_psd

    e = _layer((0, 255, 0, 255), (0, 64, 0, 64), name="Hidden")
    e["visible"] = False
    write_psd(tmp_path / "h.psd", 64, 64, [e])
    psd = PSDImage.open(tmp_path / "h.psd")
    layer = next(l for l in psd.descendants() if not l.is_group())
    assert layer.visible is False
