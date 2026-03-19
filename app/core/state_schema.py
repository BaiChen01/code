# -*- coding: utf-8 -*-
"""LangGraph workflow state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class WorkflowState(TypedDict, total=False):
    user_question: str
    need_chart_requested: bool
    refresh_mode: str
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
    need_chart: bool = False,
    refresh_mode: str = "none",
) -> WorkflowState:
    return WorkflowState(
        user_question=question,
        need_chart_requested=need_chart,
        refresh_mode=refresh_mode,
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
