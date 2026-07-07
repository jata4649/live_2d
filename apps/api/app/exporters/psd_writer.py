"""最小構成の PSD バイナリライター。

Adobe Photoshop File Format 仕様に準拠した、Live2D Cubism 向けの
フラット RGBA レイヤー + グループ階層のみをサポートする書き込み実装。

- RGB / 8bit / version 1
- レイヤーマスク・クリッピング・調整レイヤーは生成しない(Live2D 制約)
- チャンネルデータは RLE(PackBits)圧縮
- グループは lsct(section divider)で表現
- 末尾の合成画像はレイヤーを事前合成したもの

外部ライブラリに依存しない(検証は psd-tools が担当)。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- PackBits

def _packbits_row(row: bytes) -> bytes:
    """1行を PackBits 圧縮する。"""
    out = bytearray()
    n = len(row)
    i = 0
    while i < n:
        # 連続値の長さを数える
        run = 1
        while i + run < n and run < 128 and row[i + run] == row[i]:
            run += 1
        if run >= 2:
            out.append(257 - run)  # -(run-1) を符号付きで
            out.append(row[i])
            i += run
        else:
            # 非連続領域の長さを数える
            start = i
            i += 1
            while (
                i < n
                and i - start < 128
                and not (i + 1 < n and row[i] == row[i + 1])
            ):
                i += 1
            length = i - start
            out.append(length - 1)
            out.extend(row[start:i])
    return bytes(out)


def _rle_channel(channel: np.ndarray) -> bytes:
    """チャンネル(H, W uint8)を RLE 圧縮データ(圧縮フラグ含む)にする。"""
    rows = [_packbits_row(channel[y].tobytes()) for y in range(channel.shape[0])]
    counts = b"".join(struct.pack(">H", len(r)) for r in rows)
    return struct.pack(">H", 1) + counts + b"".join(rows)


# ---------------------------------------------------------------- 構造体

@dataclass
class _FlatLayer:
    """ファイルに書く1レイヤー(ピクセル or グループ境界)。"""
    name: str
    rgba: np.ndarray | None = None  # None = グループ境界レイヤー
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)  # top, left, bottom, right
    visible: bool = True
    lsct: int | None = None  # 1=開いたフォルダ, 2=閉じたフォルダ, 3=境界


@dataclass
class _GroupNode:
    name: str
    children: list = field(default_factory=list)  # _GroupNode | dict(entry)


def _build_tree(entries: list[dict]) -> _GroupNode:
    """group パス("Hair/Front")からツリーを構築する。

    entries は上(手前)から順。グループの順序は初出順 = z 順の近似。
    """
    root = _GroupNode(name="")
    nodes: dict[str, _GroupNode] = {"": root}
    for entry in entries:
        parent = root
        path = ""
        for seg in [s for s in (entry.get("group") or "").split("/") if s]:
            path = f"{path}/{seg}" if path else seg
            if path not in nodes:
                node = _GroupNode(name=seg)
                nodes[path] = node
                parent.children.append(node)
            parent = nodes[path]
        parent.children.append(entry)
    return root


def _flatten(node: _GroupNode, out: list[_FlatLayer]) -> None:
    """ツリーを上から順の _FlatLayer 列に変換する。"""
    for child in node.children:
        if isinstance(child, _GroupNode):
            out.append(_FlatLayer(name=child.name, lsct=1))
            _flatten(child, out)
            out.append(_FlatLayer(name="</Layer group>", lsct=3))
        else:
            rgba = child["rgba"]
            rect = _alpha_bbox(rgba)
            out.append(_FlatLayer(
                name=child["name"],
                rgba=rgba,
                rect=rect,
                visible=child.get("visible", True),
            ))


def _alpha_bbox(rgba: np.ndarray) -> tuple[int, int, int, int]:
    """不透明領域のバウンディングボックス(top, left, bottom, right)。"""
    alpha = rgba[:, :, 3]
    ys, xs = np.nonzero(alpha)
    if len(ys) == 0:
        return (0, 0, 1, 1)  # 空レイヤーは 1px 枠
    return (int(ys.min()), int(xs.min()), int(ys.max()) + 1, int(xs.max()) + 1)


# ---------------------------------------------------------------- 書き込み

def _pascal_string(name: str, pad_to: int = 4) -> bytes:
    raw = name.encode("ascii", errors="replace")[:255]
    data = bytes([len(raw)]) + raw
    while len(data) % pad_to:
        data += b"\x00"
    return data


def _unicode_string(name: str) -> bytes:
    encoded = name.encode("utf-16-be")
    return struct.pack(">I", len(name)) + encoded


def _additional_info(key: bytes, data: bytes, pad_to: int = 4) -> bytes:
    while len(data) % pad_to:
        data += b"\x00"
    return b"8BIM" + key + struct.pack(">I", len(data)) + data


def _layer_record_and_channels(layer: _FlatLayer) -> tuple[bytes, bytes]:
    top, left, bottom, right = layer.rect

    if layer.rgba is None:
        # グループ境界レイヤー: 空チャンネル4本
        channel_data = [struct.pack(">H", 0)] * 4  # 圧縮フラグのみ(raw, 0byte)
        channel_ids = [0, 1, 2, -1]
        top = left = bottom = right = 0
    else:
        crop = layer.rgba[top:bottom, left:right]
        channel_ids = [-1, 0, 1, 2]  # alpha, R, G, B
        planes = [crop[:, :, 3], crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]]
        channel_data = [_rle_channel(np.ascontiguousarray(p)) for p in planes]

    rec = bytearray()
    rec += struct.pack(">4i", top, left, bottom, right)
    rec += struct.pack(">H", len(channel_ids))
    for cid, cdata in zip(channel_ids, channel_data):
        rec += struct.pack(">hI", cid, len(cdata))
    rec += b"8BIM" + b"norm"          # ブレンドモード: 通常
    rec += bytes([255])               # 不透明度
    rec += bytes([0])                 # クリッピング: なし(Live2D 制約)
    rec += bytes([0 if layer.visible else 2])  # フラグ(bit1 = 非表示)
    rec += bytes([0])                 # filler

    extra = bytearray()
    extra += struct.pack(">I", 0)     # レイヤーマスク: なし(Live2D 制約)
    extra += struct.pack(">I", 0)     # ブレンディングレンジ: なし
    extra += _pascal_string(layer.name)
    extra += _additional_info(b"luni", _unicode_string(layer.name))
    if layer.lsct is not None:
        extra += _additional_info(b"lsct", struct.pack(">I", layer.lsct))

    rec += struct.pack(">I", len(extra))
    rec += extra
    return bytes(rec), b"".join(channel_data)


def _composite_image(width: int, height: int, entries: list[dict]) -> np.ndarray:
    """末尾の合成画像(白背景にフラット化した RGB)。"""
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    for entry in reversed(entries):  # entries は上から順 → 下から合成
        if entry.get("visible", True):
            canvas = Image.alpha_composite(
                canvas, Image.fromarray(entry["rgba"], "RGBA")
            )
    return np.asarray(canvas.convert("RGB"))


def write_psd(
    out_path: Path,
    width: int,
    height: int,
    entries: list[dict],
) -> None:
    """PSD を書き込む。

    entries: 上(手前)から順の
      {"name": str, "group": "Hair/Front", "visible": bool, "rgba": ndarray(H,W,4)}
    """
    tree = _build_tree(entries)
    flat_top_down: list[_FlatLayer] = []
    _flatten(tree, flat_top_down)
    file_order = list(reversed(flat_top_down))  # PSD は下から上に格納

    records, channels = [], []
    for layer in file_order:
        rec, ch = _layer_record_and_channels(layer)
        records.append(rec)
        channels.append(ch)

    layer_info = bytearray()
    layer_info += struct.pack(">h", len(file_order))
    for rec in records:
        layer_info += rec
    for ch in channels:
        layer_info += ch
    if len(layer_info) % 2:
        layer_info += b"\x00"

    layer_and_mask = bytearray()
    layer_and_mask += struct.pack(">I", len(layer_info))
    layer_and_mask += layer_info
    layer_and_mask += struct.pack(">I", 0)  # グローバルレイヤーマスク: なし

    # --- 合成画像(RLE) ---
    comp = _composite_image(width, height, entries)
    comp_rows: list[bytes] = []
    counts = bytearray()
    for c in range(3):
        plane = np.ascontiguousarray(comp[:, :, c])
        for y in range(height):
            packed = _packbits_row(plane[y].tobytes())
            counts += struct.pack(">H", len(packed))
            comp_rows.append(packed)
    image_data = struct.pack(">H", 1) + bytes(counts) + b"".join(comp_rows)

    with open(out_path, "wb") as f:
        # ヘッダ: RGB / 8bit / 3ch
        f.write(b"8BPS")
        f.write(struct.pack(">H", 1))          # version 1
        f.write(b"\x00" * 6)                    # reserved
        f.write(struct.pack(">H", 3))           # channels(合成画像)
        f.write(struct.pack(">II", height, width))
        f.write(struct.pack(">H", 8))           # 8bit/channel
        f.write(struct.pack(">H", 3))           # color mode: RGB
        f.write(struct.pack(">I", 0))           # color mode data: なし
        f.write(struct.pack(">I", 0))           # image resources: なし
        f.write(struct.pack(">I", len(layer_and_mask)))  # セクション全体長
        f.write(bytes(layer_and_mask))
        f.write(image_data)
