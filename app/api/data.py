# -*- coding: utf-8 -*-
"""Data refresh API."""

from __future__ import annotations

from typing import Any

from app.schemas.request import DataRefreshRequest

try:  # pragma: no cover - optional dependency
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None


router: Any = APIRouter(prefix="/api/data", tags=["data"]) if APIRouter else None


def refresh_data(request: DataRefreshRequest) -> dict:
    return {
        "task_status": "not_implemented",
        "insert_count": 0,
        "update_count": 0,
        "inactive_count": 0,
        "error_count": 0,
        "message": (
            "Data refresh orchestration is not wired yet. Existing crawl scripts remain the source of truth."
        ),
        "company_name": request.company_name,
        "mode": request.mode,
    }


if router is not None:  # pragma: no branch

    @router.post("/refresh")
    def refresh_data_endpoint(request: DataRefreshRequest) -> dict:
        return refresh_data(request)
