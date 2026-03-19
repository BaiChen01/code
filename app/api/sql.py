# -*- coding: utf-8 -*-
"""SQL debug API."""

from __future__ import annotations

from typing import Any

from app.agents.sql_agent import SQLAgent
from app.schemas.request import SQLQueryRequest

try:  # pragma: no cover - optional dependency
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None


router: Any = APIRouter(prefix="/api/sql", tags=["sql"]) if APIRouter else None


def query_sql(request: SQLQueryRequest) -> dict:
    try:
        return SQLAgent().run(question=request.nl_query, filters={})
    except Exception as exc:
        return {
            "sql": "",
            "columns": [],
            "rows": [],
            "summary": "SQL endpoint failed.",
            "error": str(exc),
        }


if router is not None:  # pragma: no branch

    @router.post("/query")
    def query_sql_endpoint(request: SQLQueryRequest) -> dict:
        return query_sql(request)
