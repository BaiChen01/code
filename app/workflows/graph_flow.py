# -*- coding: utf-8 -*-
"""LangGraph workflow for the dual-RAG system."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from app.agents.analysis_agent import AnalysisAgent
from app.agents.chart_agent import ChartAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.rag_agent import RAGAgent
from app.agents.router_agent import RouterAgent
from app.agents.sql_agent import SQLAgent
from app.core.logger import get_logger
from app.core.state_schema import WorkflowState, build_initial_state
from app.services.memory_service import MemoryService


logger = get_logger(__name__)
FOLLOW_UP_HINTS = (
    "继续",
    "刚才",
    "上一个",
    "上一轮",
    "这家公司",
    "那个公司",
    "该公司",
    "这些岗位",
    "这些资讯",
    "进一步",
    "补充",
)


def _append_completed_step(state: WorkflowState, step_name: str) -> list[str]:
    completed_steps = list(state.get("completed_steps", []))
    if step_name not in completed_steps:
        completed_steps.append(step_name)
    return completed_steps


def _next_step(state: WorkflowState) -> str:
    for step in state.get("plan_steps", []):
        if step not in state.get("completed_steps", []):
            return step
    return "finalize"


def _should_resolve_with_memory(question: str, memory_context: str) -> bool:
    normalized_question = (question or "").strip()
    if not normalized_question or not memory_context.strip():
        return False
    if any(token in normalized_question for token in FOLLOW_UP_HINTS):
        return True
    return len(normalized_question) <= 18


def _resolve_question_with_memory(question: str, memory_context: str) -> str:
    if not _should_resolve_with_memory(question, memory_context):
        return question
    return (
        f"{question}\n\n"
        "Session memory for follow-up resolution:\n"
        f"{memory_context}"
    )


class WorkflowRunner:
    def __init__(self) -> None:
        self.router_agent = RouterAgent()
        self.planner_agent = PlannerAgent()
        self.sql_agent = SQLAgent()
        self.rag_agent = RAGAgent()
        self.chart_agent = ChartAgent()
        self.analysis_agent = AnalysisAgent()
        self.memory_service = MemoryService()
        self.graph = self._build_graph()

    def _is_sql_error_fatal(self, state: WorkflowState, sql_result: Dict[str, Any]) -> bool:
        route = state.get("route", {})
        intent_type = route.get("intent_type")

        if not sql_result.get("error"):
            return False

        if intent_type in {"mixed_query", "intelligence_analysis"}:
            # For analysis flows, SQL is supportive evidence. If RAG and
            # analysis can still proceed, keep the SQL failure as a local
            # module error instead of failing the whole workflow.
            return False

        return True

    def _build_graph(self):
        graph = StateGraph(WorkflowState)

        graph.add_node("load_memory", self.load_memory_node)
        graph.add_node("route", self.route_node)
        graph.add_node("plan", self.plan_node)
        graph.add_node("sql", self.sql_node)
        graph.add_node("rag_job", self.rag_job_node)
        graph.add_node("rag_news", self.rag_news_node)
        graph.add_node("chart", self.chart_node)
        graph.add_node("analysis", self.analysis_node)
        graph.add_node("finalize", self.finalize_node)
        graph.add_node("persist_memory", self.persist_memory_node)

        graph.add_edge(START, "load_memory")
        graph.add_edge("load_memory", "route")
        graph.add_edge("route", "plan")

        graph.add_conditional_edges(
            "plan",
            _next_step,
            {
                "sql": "sql",
                "rag_job": "rag_job",
                "rag_news": "rag_news",
                "chart": "chart",
                "analysis": "analysis",
                "finalize": "finalize",
            },
        )
        for node_name in ("sql", "rag_job", "rag_news", "chart", "analysis"):
            graph.add_conditional_edges(
                node_name,
                _next_step,
                {
                    "sql": "sql",
                    "rag_job": "rag_job",
                    "rag_news": "rag_news",
                    "chart": "chart",
                    "analysis": "analysis",
                    "finalize": "finalize",
                },
            )
        graph.add_edge("finalize", "persist_memory")
        graph.add_edge("persist_memory", END)
        return graph.compile()

    def load_memory_node(self, state: WorkflowState) -> Dict[str, Any]:
        memory_bundle = self.memory_service.load_session_memory(state["session_id"])
        memory_context = memory_bundle.get("memory_context", "")
        return {
            "recent_messages": memory_bundle.get("recent_messages", []),
            "session_summary": memory_bundle.get("session_summary", ""),
            "memory_context": memory_context,
            "resolved_question": _resolve_question_with_memory(
                state["user_question"],
                memory_context,
            ),
            "memory_error": memory_bundle.get("error"),
            "summary_updated_at": memory_bundle.get("summary_updated_at"),
            "summary_updated": False,
        }

    def route_node(self, state: WorkflowState) -> Dict[str, Any]:
        route = self.router_agent.run(
            state.get("resolved_question", state["user_question"]),
            need_chart_requested=state.get("need_chart_requested", False),
            memory_context=state.get("memory_context", ""),
        )
        return {"route": route}

    def plan_node(self, state: WorkflowState) -> Dict[str, Any]:
        plan_payload = self.planner_agent.run(state["route"])
        return {
            "plan_steps": plan_payload["plan_steps"],
            "completed_steps": [],
        }

    def sql_node(self, state: WorkflowState) -> Dict[str, Any]:
        route = state["route"]
        sql_result = self.sql_agent.run(
            question=state.get("resolved_question", state["user_question"]),
            filters=route.get("filters", {}),
            memory_context=state.get("memory_context", ""),
        )
        updates: Dict[str, Any] = {
            "sql_result": sql_result,
            "completed_steps": _append_completed_step(state, "sql"),
        }
        if self._is_sql_error_fatal(state, sql_result):
            updates["error_message"] = sql_result["error"]
        return updates

    def rag_job_node(self, state: WorkflowState) -> Dict[str, Any]:
        route = state["route"]
        rag_result = self.rag_agent.run(
            question=state.get("resolved_question", state["user_question"]),
            retrieval_scope="job",
            filters=route.get("filters", {}),
            memory_context=state.get("memory_context", ""),
            generate_answer=route.get("intent_type") == "semantic_retrieval"
            and route.get("retrieval_scope") == "job",
        )
        return {
            "job_docs": rag_result["job_docs"],
            "completed_steps": _append_completed_step(state, "rag_job"),
            "rag_result": {
                "job_docs": rag_result["job_docs"],
                "news_docs": state.get("news_docs", []),
                "total_count": len(rag_result["job_docs"]) + len(state.get("news_docs", [])),
                "answer": rag_result.get("answer"),
            },
        }

    def rag_news_node(self, state: WorkflowState) -> Dict[str, Any]:
        route = state["route"]
        rag_result = self.rag_agent.run(
            question=state.get("resolved_question", state["user_question"]),
            retrieval_scope="news",
            filters=route.get("filters", {}),
            memory_context=state.get("memory_context", ""),
            generate_answer=route.get("intent_type") == "semantic_retrieval"
            and route.get("retrieval_scope") == "news",
        )
        existing_job_docs = state.get("job_docs", [])
        return {
            "news_docs": rag_result["news_docs"],
            "completed_steps": _append_completed_step(state, "rag_news"),
            "rag_result": {
                "job_docs": existing_job_docs,
                "news_docs": rag_result["news_docs"],
                "total_count": len(existing_job_docs) + len(rag_result["news_docs"]),
                "answer": rag_result.get("answer"),
            },
        }

    def chart_node(self, state: WorkflowState) -> Dict[str, Any]:
        chart_result = self.chart_agent.run(
            question=state["user_question"],
            sql_result=state.get("sql_result"),
        )
        return {
            "chart_result": chart_result,
            "completed_steps": _append_completed_step(state, "chart"),
        }

    def analysis_node(self, state: WorkflowState) -> Dict[str, Any]:
        analysis_result = self.analysis_agent.run(
            question=state.get("resolved_question", state["user_question"]),
            route=state["route"],
            sql_result=state.get("sql_result"),
            job_docs=state.get("job_docs", []),
            news_docs=state.get("news_docs", []),
            chart_result=state.get("chart_result"),
            memory_context=state.get("memory_context", ""),
        )
        return {
            "analysis_result": analysis_result,
            "completed_steps": _append_completed_step(state, "analysis"),
        }

    def finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        answer = self._build_answer(state)
        rag_result = {
            "job_docs": state.get("job_docs", []),
            "news_docs": state.get("news_docs", []),
            "total_count": len(state.get("job_docs", [])) + len(state.get("news_docs", [])),
        }
        return {
            "answer": answer,
            "rag_result": rag_result,
        }

    def persist_memory_node(self, state: WorkflowState) -> Dict[str, Any]:
        assistant_payload = {
            "intent_type": state.get("route", {}).get("intent_type"),
            "trace": {
                "intent_type": state.get("route", {}).get("intent_type"),
                "plan_steps": state.get("plan_steps", []),
                "retrieval_scope": state.get("route", {}).get("retrieval_scope", "none"),
            },
            "sql_result": state.get("sql_result"),
            "retrieved_docs": {
                "total_count": len(state.get("job_docs", [])) + len(state.get("news_docs", [])),
            },
            "chart_result": state.get("chart_result"),
            "error_message": state.get("error_message"),
        }
        memory_bundle = self.memory_service.persist_turn(
            session_id=state["session_id"],
            user_question=state["user_question"],
            assistant_answer=state.get("answer") or "No result was produced.",
            assistant_payload=assistant_payload,
        )
        return {
            "recent_messages": memory_bundle.get("recent_messages", state.get("recent_messages", [])),
            "session_summary": memory_bundle.get("session_summary", state.get("session_summary", "")),
            "memory_context": memory_bundle.get("memory_context", state.get("memory_context", "")),
            "memory_error": memory_bundle.get("error") or state.get("memory_error"),
            "summary_updated_at": memory_bundle.get("summary_updated_at"),
            "summary_updated": bool(memory_bundle.get("summary_updated", False)),
        }

    def _build_answer(self, state: WorkflowState) -> str:
        analysis_result = state.get("analysis_result") or {}
        rag_result = state.get("rag_result") or {}
        sql_result = state.get("sql_result") or {}
        chart_result = state.get("chart_result") or {}
        route = state.get("route") or {}

        if analysis_result:
            findings = analysis_result.get("key_findings", [])
            findings_text = "\n".join(f"- {item}" for item in findings[:3])
            judgment = analysis_result.get("intelligence_judgment", "")
            return "\n".join(
                part
                for part in [
                    analysis_result.get("question_summary", ""),
                    findings_text,
                    judgment,
                ]
                if part
            ).strip()

        if rag_result.get("answer"):
            return rag_result["answer"]

        if route.get("intent_type") == "semantic_retrieval" and rag_result.get("total_count"):
            answer_parts = []
            if state.get("job_docs"):
                answer_parts.append(
                    "招聘证据命中岗位："
                    + "；".join(
                        doc.get("job_title", "")
                        for doc in state.get("job_docs", [])[:3]
                        if doc.get("job_title")
                    )
                )
            if state.get("news_docs"):
                answer_parts.append(
                    "资讯证据命中文章："
                    + "；".join(
                        doc.get("title", "")
                        for doc in state.get("news_docs", [])[:3]
                        if doc.get("title")
                    )
                )
            if answer_parts:
                return "\n".join(answer_parts)

        if sql_result.get("summary") and chart_result.get("chart_summary"):
            return f"{sql_result['summary']}\n{chart_result['chart_summary']}"

        if sql_result.get("summary"):
            return sql_result["summary"]

        if rag_result.get("total_count"):
            return f"Retrieved {rag_result['total_count']} evidence chunks."

        if state.get("error_message"):
            return f"Processing failed: {state['error_message']}"

        return "No result was produced."

    def run_query(
        self,
        question: str,
        *,
        session_id: str | None = None,
        need_chart: bool = False,
        refresh_mode: str = "none",
    ) -> Dict[str, Any]:
        state = build_initial_state(
            question,
            session_id=session_id,
            need_chart=need_chart,
            refresh_mode=refresh_mode,
        )
        final_state = self.graph.invoke(state)
        return build_response(final_state)


def build_response(state: WorkflowState) -> Dict[str, Any]:
    route = state.get("route", {})
    retrieved_docs = {
        "job_docs": state.get("job_docs", []),
        "news_docs": state.get("news_docs", []),
        "total_count": len(state.get("job_docs", [])) + len(state.get("news_docs", [])),
    }
    return {
        "success": not bool(state.get("error_message")),
        "answer": state.get("answer", ""),
        "session_id": state.get("session_id"),
        "intent_type": route.get("intent_type"),
        "trace": {
            "intent_type": route.get("intent_type"),
            "need_sql": route.get("need_sql", False),
            "need_rag": route.get("need_rag", False),
            "need_chart": route.get("need_chart", False),
            "analysis_mode": route.get("analysis_mode"),
            "retrieval_scope": route.get("retrieval_scope", "none"),
            "plan_steps": state.get("plan_steps", []),
            "recent_message_count": len(state.get("recent_messages", [])),
            "has_session_summary": bool(state.get("session_summary")),
        },
        "sql_result": state.get("sql_result"),
        "retrieved_docs": retrieved_docs,
        "chart_result": state.get("chart_result"),
        "analysis_result": state.get("analysis_result"),
        "memory": {
            "session_id": state.get("session_id"),
            "recent_message_count": len(state.get("recent_messages", [])),
            "session_summary": state.get("session_summary") or None,
            "summary_updated": bool(state.get("summary_updated", False)),
            "summary_updated_at": state.get("summary_updated_at"),
            "memory_error": state.get("memory_error"),
        },
        "error_message": state.get("error_message"),
    }


@lru_cache(maxsize=1)
def get_workflow_runner() -> WorkflowRunner:
    return WorkflowRunner()


def run_query(
    question: str,
    *,
    session_id: str | None = None,
    need_chart: bool = False,
    refresh_mode: str = "none",
) -> Dict[str, Any]:
    return get_workflow_runner().run_query(
        question,
        session_id=session_id,
        need_chart=need_chart,
        refresh_mode=refresh_mode,
    )
