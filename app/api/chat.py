# -*- coding: utf-8 -*-
"""Chat API."""

from __future__ import annotations

from typing import Any

from app.schemas.request import ChatQueryRequest
from app.schemas.response import ChatQueryResponse
from app.workflows.graph_flow import run_query

try:  # pragma: no cover - optional dependency
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None


router: Any = APIRouter(prefix="/api/chat", tags=["chat"]) if APIRouter else None


def query_chat(request: ChatQueryRequest) -> ChatQueryResponse:
    try:
        payload = run_query(
            request.question,
            need_chart=request.need_chart,
            refresh_mode=request.refresh_mode,
        )
    except Exception as exc:
        payload = {
            "success": False,
            "answer": "Processing failed. Check model, database, and vector store settings.",
            "intent_type": None,
            "trace": {},
            "sql_result": None,
            "retrieved_docs": {"job_docs": [], "news_docs": [], "total_count": 0},
            "chart_result": None,
            "analysis_result": None,
            "error_message": str(exc),
        }
    return ChatQueryResponse(**payload)


if router is not None:  # pragma: no branch

    @router.post("/query", response_model=ChatQueryResponse)
    def query_chat_endpoint(request: ChatQueryRequest) -> ChatQueryResponse:
        return query_chat(request)
