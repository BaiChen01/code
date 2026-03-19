# -*- coding: utf-8 -*-
"""Layered smoke tests for router, vector stores, and workflow."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


from app.agents.router_agent import RouterAgent
from app.core.config import get_env_source, get_settings
from app.services.vector_service import VectorService
from app.workflows.graph_flow import WorkflowRunner


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_check(result: CheckResult) -> None:
    print(f"[{result.status}] {result.name}: {result.detail}")


def has_llm_env() -> bool:
    # Clear cached config so environment changes in the current shell are visible.
    get_settings.cache_clear()
    settings = get_settings()
    return bool(settings.llm_api_key and settings.llm_base_url)


def router_tests() -> list[CheckResult]:
    router = RouterAgent(use_llm=False)
    cases = [
        (
            "哪些岗位要求 Unity 经验",
            {
                "intent_type": "semantic_retrieval",
                "retrieval_scope": "job",
                "need_sql": False,
            },
        ),
        (
            "最近腾讯游戏有哪些资讯动态",
            {
                "intent_type": "semantic_retrieval",
                "retrieval_scope": "news",
                "need_sql": False,
            },
        ),
        (
            "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断",
            {
                "intent_type": "mixed_query",
                "retrieval_scope": "both",
                "need_sql": True,
            },
        ),
        (
            "画出各企业岗位数量对比图",
            {
                "intent_type": "visualization_request",
                "retrieval_scope": "none",
                "need_sql": True,
            },
        ),
    ]

    results: list[CheckResult] = []
    for question, expected in cases:
        route = router.run(question)
        ok = (
            route["intent_type"] == expected["intent_type"]
            and route["retrieval_scope"] == expected["retrieval_scope"]
            and route["need_sql"] == expected["need_sql"]
        )
        results.append(
            CheckResult(
                name=f"Router: {question}",
                status="PASS" if ok else "FAIL",
                detail=(
                    f"intent={route['intent_type']}, scope={route['retrieval_scope']}, "
                    f"need_sql={route['need_sql']}"
                ),
            )
        )
    return results


def vector_tests() -> list[CheckResult]:
    vector_service = VectorService()
    results: list[CheckResult] = []

    job_docs = vector_service.search_job_docs(query="Unity 游戏 开发 经验", top_k=3)
    news_docs = vector_service.search_news_docs(query="腾讯 游戏 资讯 动态", top_k=3)

    results.append(
        CheckResult(
            name="Job vector search",
            status="PASS" if len(job_docs) >= 1 else "FAIL",
            detail=f"job_docs={len(job_docs)}",
        )
    )
    results.append(
        CheckResult(
            name="News vector search",
            status="PASS" if len(news_docs) >= 1 else "FAIL",
            detail=f"news_docs={len(news_docs)}",
        )
    )
    return results


def workflow_tests() -> list[CheckResult]:
    llm_ready = has_llm_env()
    runner = WorkflowRunner()
    # Make workflow routing deterministic for tests while still exercising
    # the real SQL/RAG/analysis nodes.
    runner.router_agent.use_llm = False
    cases = [
        {
            "question": "最近腾讯游戏有哪些资讯动态",
            "need_chart": False,
            "expect": lambda result: (
                result["intent_type"] == "semantic_retrieval"
                and result["trace"]["retrieval_scope"] == "news"
                and len(result["retrieved_docs"]["news_docs"]) >= 1
            ),
            "name": "Workflow news retrieval",
        },
        {
            "question": "分析腾讯游戏近期研发布局，并结合招聘和资讯给出判断",
            "need_chart": False,
            "expect": lambda result: (
                result["intent_type"] in {"mixed_query", "intelligence_analysis"}
                and result["trace"]["retrieval_scope"] == "both"
                and result["trace"]["need_sql"] is True
                and len(result["retrieved_docs"]["job_docs"]) >= 1
                and len(result["retrieved_docs"]["news_docs"]) >= 1
                and isinstance(result.get("analysis_result"), dict)
                and bool((result.get("analysis_result") or {}).get("key_findings"))
            ),
            "name": "Workflow mixed analysis",
        },
        {
            "question": "画出各企业岗位数量对比图",
            "need_chart": True,
            "expect": lambda result: (
                result["intent_type"] == "visualization_request"
                and result["trace"]["retrieval_scope"] == "none"
                and result["trace"]["need_chart"] is True
                and result["trace"]["need_rag"] is False
            ),
            "name": "Workflow chart routing",
        },
    ]

    results: list[CheckResult] = []
    for case in cases:
        result = runner.run_query(case["question"], need_chart=case["need_chart"])
        ok = case["expect"](result)
        detail = (
            f"success={result['success']}, intent={result['intent_type']}, "
            f"scope={result['trace']['retrieval_scope']}, "
            f"job_docs={len(result['retrieved_docs']['job_docs'])}, "
            f"news_docs={len(result['retrieved_docs']['news_docs'])}, "
            f"error={result['error_message']}"
        )

        if not llm_ready and result["trace"]["need_sql"]:
            status = "SKIP" if ok else "FAIL"
            detail += " | SQL-dependent case skipped because LLM env is missing"
        else:
            status = "PASS" if ok and (result["error_message"] is None) else "FAIL"

        results.append(CheckResult(name=case["name"], status=status, detail=detail))
    return results


def main() -> None:
    print_section("Environment")
    print(f"LLM ready: {has_llm_env()}")
    print(
        "LLM config sources: "
        f"api_key={get_env_source('LLM_API_KEY')}, "
        f"base_url={get_env_source('LLM_BASE_URL')}"
    )

    print_section("Router Tests")
    for result in router_tests():
        print_check(result)

    print_section("Vector Store Tests")
    for result in vector_tests():
        print_check(result)

    print_section("Workflow Tests")
    for result in workflow_tests():
        print_check(result)

    print_section("Testing Notes")
    print("1. Router tests use rule-only mode, so they are deterministic.")
    print("2. Vector tests verify the two Chroma stores independently.")
    print("3. Workflow tests pin routing to rule mode but still execute real workflow nodes.")
    print("4. If LLM env is missing, SQL-dependent cases are marked SKIP instead of pretending they passed.")


if __name__ == "__main__":
    main()
