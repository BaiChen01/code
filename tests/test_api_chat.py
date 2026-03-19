from __future__ import annotations

from app.api import chat as chat_module
from app.schemas.request import ChatQueryRequest


def test_query_chat_wraps_successful_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_module,
        "run_query",
        lambda question, need_chart, refresh_mode: {
            "success": True,
            "answer": f"answer:{question}",
            "intent_type": "semantic_retrieval",
            "trace": {"retrieval_scope": "news"},
            "sql_result": None,
            "retrieved_docs": {"job_docs": [], "news_docs": [], "total_count": 0},
            "chart_result": None,
            "analysis_result": None,
            "error_message": None,
        },
    )

    response = chat_module.query_chat(
        ChatQueryRequest(question="最近腾讯游戏有哪些资讯动态")
    )

    assert response.success is True
    assert response.intent_type == "semantic_retrieval"
    assert response.answer == "answer:最近腾讯游戏有哪些资讯动态"


def test_query_chat_returns_structured_failure_on_exception(monkeypatch) -> None:
    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("boom")

    monkeypatch.setattr(chat_module, "run_query", _raise)

    response = chat_module.query_chat(ChatQueryRequest(question="test"))

    assert response.success is False
    assert response.answer == "Processing failed. Check model, database, and vector store settings."
    assert response.error_message == "boom"
