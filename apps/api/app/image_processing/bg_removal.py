"""アニメ特化背景除去(rembg / isnet-anime)。

背景つき JPG などアルファのない立ち絵は、これまで矩形 GrabCut しか
使えず精度が大幅に落ちていた。rembg(isnet-anime, ONNX)で人物の
アルファを生成すれば、透過PNG向けの高精度経路(アルファ切り抜き・
色分離・人物範囲フィット)がそのまま使えるようになる。

- optional 依存: `pip install rembg onnxruntime`(未導入なら従来動作)
- モデルは初回に GitHub Releases から自動ダウンロード(約170MB)
- ALS_BG_REMOVAL=0 で無効化、ALS_BG_REMOVAL_MODEL でモデル変更可
"""
from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np
from PIL import Image

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "isnet-anime"

_session: Any = None
_failure: Optional[str] = None


def bg_removal_available() -> tuple[bool, str]:
    """rembg が import できるか(モデル取得は初回実行時)。"""
    if _failure is not None:
        return False, f"背景除去の初期化に失敗しています: {_failure}"
    try:
        import rembg  # noqa: F401

        return True, ""
    except ImportError:
        return False, "rembg / onnxruntime が未インストールです"


def _get_session() -> Any:
    global _session
    if _session is None:
        from rembg import new_session

        model = os.environ.get("ALS_BG_REMOVAL_MODEL", DEFAULT_MODEL)
        logger.info("背景除去モデルをロード中: %s", model)
        _session = new_session(model)
    return _session


def _run_removal(img: Image.Image) -> Image.Image:
    """人物マスク(L, 255=前景)を返す。テストではここを差し替える。"""
    from rembg import remove

    return remove(img, session=_get_session(), only_mask=True)


def remove_background(rgba: np.ndarray) -> Optional[np.ndarray]:
    """背景を除去したアルファつき画像を返す。失敗時は None(従来動作)。

    一度失敗したら以降は高コストな再試行をしない。
    """
    global _failure
    if _failure is not None:
        return None
    try:
        src = Image.fromarray(rgba, "RGBA").convert("RGB")
        mask = _run_removal(src).convert("L")
        if mask.size != src.size:
            mask = mask.resize(src.size, Image.BILINEAR)
        alpha = np.asarray(mask)
        fg_ratio = float((alpha > 32).mean())
        if fg_ratio < 0.02 or fg_ratio > 0.98:
            # 全消し/全残しは人物検出失敗とみなし、従来動作へ
            logger.warning("背景除去の結果が不自然です(前景率 %.0f%%)。スキップします",
                           fg_ratio * 100)
            return None
        out = rgba.copy()
        out[:, :, 3] = alpha
        return out
    except Exception as e:
        _failure = str(e)
        logger.warning("背景除去に失敗しました(以降スキップ): %s", e)
        return None
