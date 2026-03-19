# -*- coding: utf-8 -*-
"""RAG debug API."""

from __future__ import annotations

from typing import Any

from app.agents.rag_agent import RAGAgent
from app.schemas.request import RAGSearchRequest

try:  # pragma: no cover - optional dependency
    from fastapi import APIRouter
except ImportError:  # pragma: no cover - optional dependency
    APIRouter = None


router: Any = APIRouter(prefix="/api/rag", tags=["rag"]) if APIRouter else None


def search_rag(request: RAGSearchRequest) -> dict:
    try:
        rag_agent = RAGAgent()
        filters = {
            "company_name": request.company_filter,
            "product_line": request.product_line_filter,
            "job_location": request.job_location_filter,
            "keyword": None,
        }
        result = rag_agent.run(
            question=request.query,
            retrieval_scope=request.source_scope,
            filters=filters,
            top_k=request.top_k,
            generate_answer=True,
        )
        return {
            "job_docs": result["job_docs"],
            "news_docs": result["news_docs"],
            "total_count": result["total_count"],
            "answer": result.get("answer"),
            "error": result.get("error"),
        }
    except Exception as exc:
        return {
            "job_docs": [],
            "news_docs": [],
            "total_count": 0,
            "answer": None,
            "error": str(exc),
        }


if router is not None:  # pragma: no branch

    @router.post("/search")
    def search_rag_endpoint(request: RAGSearchRequest) -> dict:
        return search_rag(request)
