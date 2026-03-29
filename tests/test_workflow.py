from __future__ import annotations

from app.workflows import graph_flow as graph_module


class FakeMemoryService:
    last_instance: "FakeMemoryService | None" = None

    def __init__(self) -> None:
        self.load_calls: list[str] = []
        self.persist_calls: list[dict] = []
        FakeMemoryService.last_instance = self

    def load_session_memory(self, session_id: str) -> dict:
        self.load_calls.append(session_id)
        return {
            "session_id": session_id,
            "recent_messages": [
                {"id": 1, "role": "user", "content": "先分析腾讯游戏招聘布局"},
                {"id": 2, "role": "assistant", "content": "已经给出腾讯游戏招聘布局摘要"},
            ],
            "session_summary": "The session focuses on Tencent Games hiring and news analysis.",
            "memory_context": (
                "Session summary:\nThe session focuses on Tencent Games hiring and news analysis.\n\n"
                "Recent conversation:\nUser: 先分析腾讯游戏招聘布局\n"
                "Assistant: 已经给出腾讯游戏招聘布局摘要"
            ),
            "summary_updated_at": "2026-03-29T12:00:00",
            "message_count": 2,
            "error": None,
        }

    def persist_turn(
        self,
        *,
        session_id: str,
        user_question: str,
        assistant_answer: str,
        assistant_payload: dict | None = None,
    ) -> dict:
        self.persist_calls.append(
            {
                "session_id": session_id,
                "user_question": user_question,
                "assistant_answer": assistant_answer,
                "assistant_payload": assistant_payload,
            }
        )
        return {
            "session_id": session_id,
            "recent_messages": [
                {"id": 3, "role": "user", "content": user_question},
                {"id": 4, "role": "assistant", "content": assistant_answer},
            ],
            "session_summary": "Tencent Games remains the focus across hiring and news signals.",
            "memory_context": "Updated memory context",
            "summary_updated_at": "2026-03-29T12:05:00",
            "message_count": 4,
            "summary_updated": True,
            "error": None,
        }


class FakeRouterAgent:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(
        self,
        question: str,
        *,
        need_chart_requested: bool = False,
        memory_context: str = "",
    ) -> dict:
        self.calls.append(
            {
                "question": question,
                "need_chart_requested": need_chart_requested,
                "memory_context": memory_context,
            }
        )
        if "画出" in question:
            return {
                "intent_type": "visualization_request",
                "need_sql": True,
                "need_rag": False,
                "need_chart": True or need_chart_requested,
                "analysis_mode": "comparative_analysis",
                "retrieval_scope": "none",
                "filters": {},
            }
        return {
            "intent_type": "mixed_query",
            "need_sql": True,
            "need_rag": True,
            "need_chart": False,
            "analysis_mode": "company_rd_layout",
            "retrieval_scope": "both",
            "filters": {"company_name": "腾讯游戏"},
        }


class FakeSQLAgent:
    def run(self, *, question: str, filters: dict, memory_context: str = "") -> dict:
        if "画出" in question:
            return {
                "sql": "SELECT company_name, 10 AS job_count",
                "columns": ["company_name", "job_count"],
                "rows": [{"company_name": "腾讯游戏", "job_count": 10}],
                "summary": "Query returned 1 rows.",
                "error": None,
            }
        return {
            "sql": "",
            "columns": [],
            "rows": [],
            "summary": "SQL generation returned an error.",
            "error": "The question contains non-SQL reasoning parts and only RAG evidence should continue.",
        }


class FakeRAGAgent:
    def run(
        self,
        *,
        question: str,
        retrieval_scope: str,
        filters: dict,
        memory_context: str = "",
        top_k: int = 5,
        generate_answer: bool = False,
    ) -> dict:
        if retrieval_scope == "job":
            return {
                "job_docs": [{"source_type": "job", "job_title": "客户端开发"}],
                "news_docs": [],
                "total_count": 1,
                "answer": None,
                "error": None,
            }
        return {
            "job_docs": [],
            "news_docs": [{"source_type": "news", "title": "研发动态"}],
            "total_count": 1,
            "answer": None,
            "error": None,
        }


class FakeChartAgent:
    def run(self, *, question: str, sql_result: dict | None) -> dict:
        return {
            "chart_needed": True,
            "chart_type": "bar",
            "title": question,
            "x_field": "company_name",
            "y_field": "job_count",
            "series_name": "job_count",
            "chart_option": {"series": [{"type": "bar", "data": [10]}]},
            "chart_summary": "Use a bar chart to compare company job counts.",
        }


class FakeAnalysisAgent:
    def run(
        self,
        *,
        question: str,
        route: dict,
        sql_result: dict | None,
        job_docs: list[dict],
        news_docs: list[dict],
        chart_result: dict | None,
        memory_context: str = "",
    ) -> dict:
        return {
            "question_summary": question,
            "data_basis": ["structured hiring facts", "news evidence"],
            "job_evidence": ["job-evidence"],
            "news_evidence": ["news-evidence"],
            "key_findings": ["Both hiring and news evidence are available."],
            "chart_explanation": "No chart.",
            "intelligence_judgment": "A preliminary judgment can be formed.",
            "limitations": ["SQL is only supportive evidence here."],
        }


def _build_runner(monkeypatch) -> graph_module.WorkflowRunner:
    monkeypatch.setattr(graph_module, "MemoryService", FakeMemoryService)
    monkeypatch.setattr(graph_module, "RouterAgent", FakeRouterAgent)
    monkeypatch.setattr(graph_module, "SQLAgent", FakeSQLAgent)
    monkeypatch.setattr(graph_module, "RAGAgent", FakeRAGAgent)
    monkeypatch.setattr(graph_module, "ChartAgent", FakeChartAgent)
    monkeypatch.setattr(graph_module, "AnalysisAgent", FakeAnalysisAgent)
    return graph_module.WorkflowRunner()


def test_mixed_workflow_degrades_sql_failure_without_failing_flow(monkeypatch) -> None:
    runner = _build_runner(monkeypatch)

    result = runner.run_query(
        "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断",
        session_id="session-mixed",
    )

    assert result["success"] is True
    assert result["session_id"] == "session-mixed"
    assert result["error_message"] is None
    assert result["trace"]["retrieval_scope"] == "both"
    assert result["sql_result"]["error"] == (
        "The question contains non-SQL reasoning parts and only RAG evidence should continue."
    )
    assert len(result["retrieved_docs"]["job_docs"]) == 1
    assert len(result["retrieved_docs"]["news_docs"]) == 1
    assert result["analysis_result"]["key_findings"]
    assert result["memory"]["summary_updated"] is True


def test_chart_workflow_returns_chart_payload(monkeypatch) -> None:
    runner = _build_runner(monkeypatch)

    result = runner.run_query(
        "画出各企业岗位数量对比图",
        session_id="session-chart",
        need_chart=True,
    )

    assert result["success"] is True
    assert result["trace"]["need_chart"] is True
    assert result["trace"]["need_rag"] is False
    assert result["chart_result"]["chart_type"] == "bar"
    assert result["retrieved_docs"]["total_count"] == 0


def test_workflow_loads_and_persists_session_memory(monkeypatch) -> None:
    runner = _build_runner(monkeypatch)

    result = runner.run_query(
        "继续结合资讯说一下",
        session_id="session-memory",
    )

    memory_service = FakeMemoryService.last_instance
    assert memory_service is not None
    assert memory_service.load_calls == ["session-memory"]
    assert memory_service.persist_calls[0]["session_id"] == "session-memory"
    assert result["memory"]["session_summary"] == (
        "Tencent Games remains the focus across hiring and news signals."
    )
    assert result["trace"]["recent_message_count"] == 2
