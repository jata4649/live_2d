"""アプリケーション設定。環境変数で上書き可能。"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


def _repo_root() -> Path:
    # apps/api/app/core/config.py → リポジトリルート
    return Path(__file__).resolve().parents[4]


class Settings(BaseModel):
    host: str = os.environ.get("ALS_HOST", "127.0.0.1")
    port: int = int(os.environ.get("ALS_PORT", "8787"))
    outputs_root: Path = Path(
        os.environ.get("ALS_OUTPUTS_ROOT", str(_repo_root() / "outputs"))
    )
    db_path: Path = Path(
        os.environ.get("ALS_DB_PATH", str(_repo_root() / "outputs" / "als.sqlite3"))
    )
    # アップロード上限(バイト)
    max_upload_bytes: int = int(os.environ.get("ALS_MAX_UPLOAD_BYTES", str(64 * 1024 * 1024)))
    # 内部処理用の作業画像の長辺サイズ
    working_long_edge: int = int(os.environ.get("ALS_WORKING_LONG_EDGE", "2048"))
    # テンプレートのbboxを、画像から検出した人物範囲へフィットさせる
    fit_template: bool = os.environ.get("ALS_FIT_TEMPLATE", "1") not in (
        "0", "false", "False",
    )
    # セグメンテーションを作業サイズで実行し、マスクをフル解像度へ拡大する
    # (大画像での速度・メモリ対策。docs/08 リスクR3)
    segment_on_working: bool = os.environ.get("ALS_SEGMENT_ON_WORKING", "1") not in (
        "0", "false", "False",
    )
    # PSD出力前に品質スコアがこの値未満なら 409 を返す(force で無視可)
    export_min_score: int = int(os.environ.get("ALS_EXPORT_MIN_SCORE", "50"))
    # レイヤー生成時にマスク境界帯をガイデッドフィルタで連続アルファ化する
    # (髪の毛先などのソフトエッジ化。docs/08 R4)
    soft_edges: bool = os.environ.get("ALS_SOFT_EDGES", "1") not in (
        "0", "false", "False",
    )
    # アルファのない画像(背景つきJPG等)に rembg で人物アルファを生成する
    # (rembg 未導入なら自動で従来動作)
    bg_removal: bool = os.environ.get("ALS_BG_REMOVAL", "1") not in (
        "0", "false", "False",
    )

    @property
    def projects_root(self) -> Path:
        return self.outputs_root / "projects"


settings = Settings()
