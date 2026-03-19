# -*- coding: utf-8 -*-
"""Chart debug API."""

from __future__ import annotations

from typing import Any

from app.agents.chart_agent import ChartAgent
from app.schemas.request import ChartGenerateRequest

try:  # pragma: no cover - optional dependency
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None


router: Any = APIRouter(prefix="/api/chart", tags=["chart"]) if APIRouter else None
chart_agent = ChartAgent()


def generate_chart(request: ChartGenerateRequest) -> dict:
    sql_result = {
        "rows": request.dataset,
        "columns": list(request.dataset[0].keys()) if request.dataset else [],
        "summary": request.title or "",
    }
    return chart_agent.run(question=request.title or "Generate chart", sql_result=sql_result)


if router is not None:  # pragma: no branch

    @router.post("/generate")
    def generate_chart_endpoint(request: ChartGenerateRequest) -> dict:
        return generate_chart(request)
