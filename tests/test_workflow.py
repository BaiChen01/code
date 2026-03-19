from __future__ import annotations

from app.workflows import graph_flow as graph_module


class FakeRouterAgent:
    def run(self, question: str, *, need_chart_requested: bool = False) -> dict:
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
    def run(self, *, question: str, filters: dict) -> dict:
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
            "error": "资讯与综合判断部分不适合直接用 SQL 回答。",
        }


class FakeRAGAgent:
    def run(
        self,
        *,
        question: str,
        retrieval_scope: str,
        filters: dict,
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
    ) -> dict:
        return {
            "question_summary": question,
            "data_basis": ["招聘结构化事实", "资讯语义证据"],
            "job_evidence": ["job-evidence"],
            "news_evidence": ["news-evidence"],
            "key_findings": ["招聘与资讯均提供了相关线索。"],
            "chart_explanation": "No chart.",
            "intelligence_judgment": "可以给出初步判断。",
            "limitations": ["SQL 只作为辅助证据。"],
        }


def test_mixed_workflow_degrades_sql_failure_without_failing_flow(monkeypatch) -> None:
    monkeypatch.setattr(graph_module, "RouterAgent", FakeRouterAgent)
    monkeypatch.setattr(graph_module, "SQLAgent", FakeSQLAgent)
    monkeypatch.setattr(graph_module, "RAGAgent", FakeRAGAgent)
    monkeypatch.setattr(graph_module, "ChartAgent", FakeChartAgent)
    monkeypatch.setattr(graph_module, "AnalysisAgent", FakeAnalysisAgent)

    runner = graph_module.WorkflowRunner()
    result = runner.run_query("分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断")

    assert result["success"] is True
    assert result["error_message"] is None
    assert result["trace"]["retrieval_scope"] == "both"
    assert result["sql_result"]["error"] == "资讯与综合判断部分不适合直接用 SQL 回答。"
    assert len(result["retrieved_docs"]["job_docs"]) == 1
    assert len(result["retrieved_docs"]["news_docs"]) == 1
    assert result["analysis_result"]["key_findings"]


def test_chart_workflow_returns_chart_payload(monkeypatch) -> None:
    monkeypatch.setattr(graph_module, "RouterAgent", FakeRouterAgent)
    monkeypatch.setattr(graph_module, "SQLAgent", FakeSQLAgent)
    monkeypatch.setattr(graph_module, "RAGAgent", FakeRAGAgent)
    monkeypatch.setattr(graph_module, "ChartAgent", FakeChartAgent)
    monkeypatch.setattr(graph_module, "AnalysisAgent", FakeAnalysisAgent)

    runner = graph_module.WorkflowRunner()
    result = runner.run_query("画出各企业岗位数量对比图", need_chart=True)

    assert result["success"] is True
    assert result["trace"]["need_chart"] is True
    assert result["trace"]["need_rag"] is False
    assert result["chart_result"]["chart_type"] == "bar"
    assert result["retrieved_docs"]["total_count"] == 0
