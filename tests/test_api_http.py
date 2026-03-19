from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import chart as chart_module
from app.api import chat as chat_module
from app.api import data as data_module
from app.api import rag as rag_module
from app.api import sql as sql_module
from app.app import create_app


def _make_client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint_returns_ok() -> None:
    client = _make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_returns_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_module,
        "query_chat",
        lambda request: {
            "success": True,
            "answer": "analysis answer",
            "intent_type": "mixed_query",
            "trace": {"retrieval_scope": "both"},
            "sql_result": None,
            "retrieved_docs": {"job_docs": [], "news_docs": [], "total_count": 0},
            "chart_result": None,
            "analysis_result": None,
            "error_message": None,
        },
    )
    client = _make_client()

    response = client.post(
        "/api/chat/query",
        json={"question": "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["intent_type"] == "mixed_query"


def test_chat_endpoint_rejects_empty_question() -> None:
    client = _make_client()

    response = client.post("/api/chat/query", json={"question": ""})

    assert response.status_code == 422


def test_sql_endpoint_returns_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        sql_module,
        "query_sql",
        lambda request: {
            "sql": "SELECT 1",
            "columns": ["value"],
            "rows": [{"value": 1}],
            "summary": "Query returned 1 rows.",
            "error": None,
        },
    )
    client = _make_client()

    response = client.post("/api/sql/query", json={"nl_query": "统计岗位数量"})

    assert response.status_code == 200
    assert response.json()["rows"] == [{"value": 1}]


def test_rag_endpoint_returns_dual_docs(monkeypatch) -> None:
    monkeypatch.setattr(
        rag_module,
        "search_rag",
        lambda request: {
            "job_docs": [{"source_type": "job"}],
            "news_docs": [{"source_type": "news"}],
            "total_count": 2,
            "answer": "rag answer",
            "error": None,
        },
    )
    client = _make_client()

    response = client.post(
        "/api/rag/search",
        json={"query": "腾讯游戏 动态", "source_scope": "both"},
    )

    assert response.status_code == 200
    assert response.json()["total_count"] == 2
    assert response.json()["answer"] == "rag answer"


def test_chart_endpoint_returns_chart_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        chart_module,
        "generate_chart",
        lambda request: {
            "chart_needed": True,
            "chart_type": "bar",
            "title": request.title,
            "x_field": "company_name",
            "y_field": "job_count",
            "series_name": "job_count",
            "chart_option": {"series": [{"type": "bar", "data": [10, 8]}]},
            "chart_summary": "bar chart",
        },
    )
    client = _make_client()

    response = client.post(
        "/api/chart/generate",
        json={
            "title": "岗位数量对比",
            "dataset": [
                {"company_name": "腾讯游戏", "job_count": 10},
                {"company_name": "网易游戏", "job_count": 8},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["chart_type"] == "bar"
    assert response.json()["chart_option"]["series"][0]["data"] == [10, 8]


def test_data_refresh_endpoint_returns_placeholder_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        data_module,
        "refresh_data",
        lambda request: {
            "task_status": "not_implemented",
            "insert_count": 0,
            "update_count": 0,
            "inactive_count": 0,
            "error_count": 0,
            "message": "placeholder",
            "company_name": request.company_name,
            "mode": request.mode,
        },
    )
    client = _make_client()

    response = client.post(
        "/api/data/refresh",
        json={"company_name": "腾讯游戏", "mode": "incremental"},
    )

    assert response.status_code == 200
    assert response.json()["task_status"] == "not_implemented"
    assert response.json()["company_name"] == "腾讯游戏"
