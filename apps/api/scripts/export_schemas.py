"""Pydantic モデルから JSON Schema を packages/shared/schemas へエクスポートする。

TypeScript 型の自動生成(json-schema-to-typescript 等)の入力に使う。
実行: cd apps/api && python3 scripts/export_schemas.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.models.export import ExportResult  # noqa: E402
from app.models.jobs import Job  # noqa: E402
from app.models.parts import PartsPlan  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.quality import QualityReport  # noqa: E402
from app.models.segmentation import (  # noqa: E402
    InpaintTaskList,
    QuestionList,
    SegmentationTaskList,
)

SCHEMAS_DIR = API_ROOT.parents[1] / "packages" / "shared" / "schemas"

MODELS = {
    "project": Project,
    "parts_plan": PartsPlan,
    "segmentation_tasks": SegmentationTaskList,
    "inpaint_tasks": InpaintTaskList,
    "questions": QuestionList,
    "quality_report": QualityReport,
    "job": Job,
    "export_result": ExportResult,
}


def main() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        out = SCHEMAS_DIR / f"{name}.schema.json"
        out.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"wrote {out.relative_to(API_ROOT.parents[1])}")


if __name__ == "__main__":
    main()
