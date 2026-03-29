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
            session_id=request.session_id,
            need_chart=request.need_chart,
            refresh_mode=request.refresh_mode,
        )
    except Exception as exc:
        error_text = str(exc) or "Unknown backend error."
        payload = {
            "success": False,
            "answer": f"Processing failed: {error_text}",
            "session_id": request.session_id,
            "intent_type": None,
            "trace": {},
            "sql_result": None,
            "retrieved_docs": {"job_docs": [], "news_docs": [], "total_count": 0},
            "chart_result": None,
            "analysis_result": None,
            "memory": {
                "session_id": request.session_id,
                "recent_message_count": 0,
                "session_summary": None,
                "summary_updated": False,
                "summary_updated_at": None,
                "memory_error": None,
            },
            "error_message": error_text,
        }
    return ChatQueryResponse(**payload)


if router is not None:  # pragma: no branch

    @router.post("/query", response_model=ChatQueryResponse)
    def query_chat_endpoint(request: ChatQueryRequest) -> ChatQueryResponse:
        return query_chat(request)
