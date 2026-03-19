from __future__ import annotations

import pytest

from app.agents.router_agent import RouterAgent


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "哪些岗位要求 Unity 经验",
            {
                "intent_type": "semantic_retrieval",
                "retrieval_scope": "job",
                "need_sql": False,
                "need_rag": True,
            },
        ),
        (
            "最近腾讯游戏有哪些资讯动态",
            {
                "intent_type": "semantic_retrieval",
                "retrieval_scope": "news",
                "need_sql": False,
                "need_rag": True,
            },
        ),
        (
            "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断",
            {
                "intent_type": "mixed_query",
                "retrieval_scope": "both",
                "need_sql": True,
                "need_rag": True,
            },
        ),
        (
            "画出各企业岗位数量对比图",
            {
                "intent_type": "visualization_request",
                "retrieval_scope": "none",
                "need_sql": True,
                "need_rag": False,
            },
        ),
    ],
)
def test_router_rule_mode(question: str, expected: dict[str, object]) -> None:
    agent = RouterAgent(use_llm=False)

    route = agent.run(question)

    for key, value in expected.items():
        assert route[key] == value
