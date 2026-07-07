"""画像正規化: PNG化 / sRGB前提 / RGBA化 / 作業サイズ生成。

すべて Pillow ベース。ICC プロファイルが sRGB 以外の場合は sRGB へ変換を試みる。
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageCms

# 巨大画像の DecompressionBomb 警告を実用上限まで緩和(64MP 程度)
Image.MAX_IMAGE_PIXELS = 128_000_000


@dataclass
class NormalizeResult:
    width: int
    height: int
    has_alpha: bool
    color_profile: str


def load_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def to_srgb_rgba(img: Image.Image) -> tuple[Image.Image, str]:
    """ICC プロファイルを考慮して sRGB / RGBA へ変換する。"""
    profile_name = "sRGB"
    icc = img.info.get("icc_profile")
    if icc:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst = ImageCms.createProfile("sRGB")
            mode = "RGBA" if ("A" in img.mode or img.mode == "P") else "RGB"
            base = img.convert(mode)
            img = ImageCms.profileToProfile(base, src, dst, outputMode=mode)
            profile_name = "sRGB (converted)"
        except Exception:
            # プロファイル変換に失敗しても処理は継続(sRGB 前提とみなす)
            profile_name = "sRGB (assumed)"
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img, profile_name


def has_meaningful_alpha(img: Image.Image) -> bool:
    """完全不透明でないピクセルが存在するか。"""
    if img.mode != "RGBA":
        return False
    alpha = img.getchannel("A")
    lo, hi = alpha.getextrema()
    return lo < 255


def make_working_copy(img: Image.Image, long_edge: int) -> Image.Image:
    """内部処理用の縮小コピー。元より小さい場合のみ縮小する。"""
    w, h = img.size
    scale = long_edge / max(w, h)
    if scale >= 1.0:
        return img.copy()
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def normalize(data: bytes, working_long_edge: int) -> tuple[Image.Image, Image.Image, NormalizeResult]:
    """(normalized, working, meta) を返す。"""
    img = load_image(data)
    img, profile = to_srgb_rgba(img)
    working = make_working_copy(img, working_long_edge)
    meta = NormalizeResult(
        width=img.width,
        height=img.height,
        has_alpha=has_meaningful_alpha(img),
        color_profile=profile,
    )
    return img, working, meta
