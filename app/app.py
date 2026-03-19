# -*- coding: utf-8 -*-
"""FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.api.chart import router as chart_router
from app.api.chat import router as chat_router
from app.api.data import router as data_router
from app.api.rag import router as rag_router
from app.api.sql import router as sql_router

try:  # pragma: no cover - optional dependency
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = None
    FileResponse = None
    StaticFiles = None


STATIC_DIR = Path(__file__).resolve().parent / "static"
FRONTEND_DIST_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"


def create_app() -> Any:
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Install the dependency before starting the API server."
        )

    app = FastAPI(title="Game Intel Agent API", version="1.0.0")
    if StaticFiles is not None:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        if FRONTEND_ASSETS_DIR.exists():
            app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS_DIR)), name="assets")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def index() -> Any:
        if FileResponse is None:
            return {"message": "Frontend is unavailable because FastAPI responses are missing."}
        if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
            return FileResponse(FRONTEND_DIST_DIR / "index.html")
        return FileResponse(STATIC_DIR / "index.html")

    for router in (chat_router, sql_router, rag_router, chart_router, data_router):
        if router is not None:
            app.include_router(router)

    return app


app = create_app() if FastAPI is not None else None
