# -*- coding: utf-8 -*-
"""LangGraph workflow state."""

from __future__ import annotations

from uuid import uuid4
from typing import Any, Dict, List, Optional, TypedDict


class WorkflowState(TypedDict, total=False):
    session_id: str
    user_question: str
    resolved_question: str
    need_chart_requested: bool
    refresh_mode: str
    recent_messages: List[Dict[str, Any]]
    session_summary: str
    memory_context: str
    memory_error: Optional[str]
    summary_updated_at: Optional[str]
    summary_updated: bool
    route: Dict[str, Any]
    plan_steps: List[str]
    completed_steps: List[str]
    sql_result: Optional[Dict[str, Any]]
    job_docs: List[Dict[str, Any]]
    news_docs: List[Dict[str, Any]]
    rag_result: Dict[str, Any]
    chart_result: Optional[Dict[str, Any]]
    analysis_result: Optional[Dict[str, Any]]
    answer: str
    error_message: Optional[str]


def build_initial_state(
    question: str,
    *,
    session_id: str | None = None,
    need_chart: bool = False,
    refresh_mode: str = "none",
) -> WorkflowState:
    return WorkflowState(
        session_id=session_id or uuid4().hex,
        user_question=question,
        resolved_question=question,
        need_chart_requested=need_chart,
        refresh_mode=refresh_mode,
        recent_messages=[],
        session_summary="",
        memory_context="",
        memory_error=None,
        summary_updated_at=None,
        summary_updated=False,
        route={},
        plan_steps=[],
        completed_steps=[],
        sql_result=None,
        job_docs=[],
        news_docs=[],
        rag_result={"job_docs": [], "news_docs": [], "total_count": 0},
        chart_result=None,
        analysis_result=None,
        answer="",
        error_message=None,
    )
