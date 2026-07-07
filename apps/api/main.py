"""AutoLive2D Layer Studio API エントリポイント。

起動: cd apps/api && uvicorn main:app --port 8787
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db
from app.routers import (
    analysis,
    export,
    files,
    image,
    layers,
    projects,
    quality,
    segmentation,
)
from app.ai.claude_analyzer import AnalyzerUnavailableError
from app.services.export_service import ExportBlockedError
from app.services.image_service import InvalidImageError
from app.services.mask_service import MaskError
from app.services.project_service import ProjectNotFoundError

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="AutoLive2D Layer Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for router in (
    projects.router,
    image.router,
    analysis.router,
    segmentation.router,
    layers.router,
    quality.router,
    export.router,
    files.router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.on_event("startup")
def startup() -> None:
    settings.projects_root.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("outputs: %s", settings.outputs_root)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "version": app.version}


# --- 統一エラーハンドリング: {code, message, detail} 形式 ---

def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "detail": None},
    )


@app.exception_handler(ProjectNotFoundError)
def handle_not_found(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
    return _error(404, "PROJECT_NOT_FOUND", str(exc))


@app.exception_handler(InvalidImageError)
def handle_invalid_image(request: Request, exc: InvalidImageError) -> JSONResponse:
    return _error(422, "INVALID_IMAGE", str(exc))


@app.exception_handler(MaskError)
def handle_mask_error(request: Request, exc: MaskError) -> JSONResponse:
    return _error(422, "MASK_ERROR", str(exc))


@app.exception_handler(ExportBlockedError)
def handle_export_blocked(request: Request, exc: ExportBlockedError) -> JSONResponse:
    return _error(409, "EXPORT_BLOCKED", str(exc))


@app.exception_handler(AnalyzerUnavailableError)
def handle_analyzer_unavailable(
    request: Request, exc: AnalyzerUnavailableError
) -> JSONResponse:
    return _error(503, "ANALYZER_UNAVAILABLE", str(exc))


@app.exception_handler(ValueError)
def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return _error(400, "BAD_REQUEST", str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
