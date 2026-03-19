# -*- coding: utf-8 -*-
"""Planner agent for deterministic step sequencing."""

from __future__ import annotations

from typing import Any, Dict, List


class PlannerAgent:
    STEP_ORDER = ["sql", "rag_job", "rag_news", "chart", "analysis"]

    def plan(self, route: Dict[str, Any]) -> Dict[str, Any]:
        steps: List[str] = []
        retrieval_scope = route.get("retrieval_scope", "none")

        if route.get("need_sql"):
            steps.append("sql")

        if route.get("need_rag") and retrieval_scope in {"job", "both"}:
            steps.append("rag_job")

        if route.get("need_rag") and retrieval_scope in {"news", "both"}:
            steps.append("rag_news")

        if route.get("need_chart"):
            steps.append("chart")

        if route.get("intent_type") in {"intelligence_analysis", "mixed_query"}:
            steps.append("analysis")

        return {
            "plan_steps": steps,
            "retrieval_scope": retrieval_scope,
        }

    def run(self, route: Dict[str, Any]) -> Dict[str, Any]:
        return self.plan(route)
