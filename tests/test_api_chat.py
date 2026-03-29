from __future__ import annotations

from app.api import chat as chat_module
from app.schemas.request import ChatQueryRequest


def test_query_chat_wraps_successful_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_query(
        question: str,
        *,
        session_id: str | None = None,
        need_chart: bool = False,
        refresh_mode: str = "none",
    ) -> dict:
        captured["question"] = question
        captured["session_id"] = session_id
        captured["need_chart"] = need_chart
        captured["refresh_mode"] = refresh_mode
        return {
            "success": True,
            "answer": f"answer:{question}",
            "session_id": session_id,
            "intent_type": "semantic_retrieval",
            "trace": {"retrieval_scope": "news"},
            "sql_result": None,
            "retrieved_docs": {"job_docs": [], "news_docs": [], "total_count": 0},
            "chart_result": None,
            "analysis_result": None,
            "memory": {
                "session_id": session_id,
                "recent_message_count": 0,
                "session_summary": None,
                "summary_updated": False,
                "summary_updated_at": None,
                "memory_error": None,
            },
            "error_message": None,
        }

    monkeypatch.setattr(chat_module, "run_query", _fake_run_query)

    response = chat_module.query_chat(
        ChatQueryRequest(
            question="最近腾讯游戏有哪些资讯动态",
            session_id="session-1",
        )
    )

    assert response.success is True
    assert response.intent_type == "semantic_retrieval"
    assert response.answer == "answer:最近腾讯游戏有哪些资讯动态"
    assert response.session_id == "session-1"
    assert captured["session_id"] == "session-1"


def test_query_chat_returns_structured_failure_on_exception(monkeypatch) -> None:
    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("boom")

    monkeypatch.setattr(chat_module, "run_query", _raise)

    response = chat_module.query_chat(
        ChatQueryRequest(question="test", session_id="session-2")
    )

    assert response.success is False
    assert response.answer == "Processing failed: boom"
    assert response.session_id == "session-2"
    assert response.error_message == "boom"
