# -*- coding: utf-8 -*-
"""Dual-RAG agent."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.core.llm_factory import get_llm
from app.core.model_config import (
    RAG_QUERY_MAX_TOKENS,
    RAG_QUERY_MODEL,
    RAG_QUERY_TEMPERATURE,
    RAG_QUERY_TOP_P,
    RAG_SUMMARY_MAX_TOKENS,
    RAG_SUMMARY_MODEL,
    RAG_SUMMARY_TEMPERATURE,
    RAG_SUMMARY_TOP_P,
)
from app.prompts.rag_prompt import (
    get_rag_answer_prompt_template,
    get_rag_query_prompt_template,
)
from app.services.vector_service import VectorService


def infer_job_text_type(question: str) -> Optional[str]:
    lowered = question.lower()
    if "职责" in question or "负责" in question:
        return "responsibility"
    if "要求" in question or "技能" in question or "经验" in question:
        return "requirement"
    if "requirement" in lowered:
        return "requirement"
    if "responsibility" in lowered:
        return "responsibility"
    return None


class RAGAgent:
    def __init__(self) -> None:
        self.vector_service = VectorService()
        self.query_llm = get_llm(
            model=RAG_QUERY_MODEL,
            temperature=RAG_QUERY_TEMPERATURE,
            max_tokens=RAG_QUERY_MAX_TOKENS,
            top_p=RAG_QUERY_TOP_P,
        )
        self.summary_llm = get_llm(
            model=RAG_SUMMARY_MODEL,
            temperature=RAG_SUMMARY_TEMPERATURE,
            max_tokens=RAG_SUMMARY_MAX_TOKENS,
            top_p=RAG_SUMMARY_TOP_P,
        )
        self.query_prompt_template = get_rag_query_prompt_template()
        self.answer_prompt_template = get_rag_answer_prompt_template()

    def rewrite_query(
        self,
        *,
        question: str,
        source_scope: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            result = self.query_llm.invoke_json(
                self.query_prompt_template,
                {
                    "question": question,
                    "source_scope": source_scope,
                    "filters_json": json.dumps(filters, ensure_ascii=False, indent=2),
                },
            )
        except Exception:
            result = {}

        return {
            "query_text": result.get("query_text") or question,
            "text_type": result.get("text_type") or infer_job_text_type(question),
            "retrieval_goal": result.get("retrieval_goal") or "Retrieve relevant evidence.",
        }

    def build_answer(
        self,
        *,
        question: str,
        job_docs: list[dict],
        news_docs: list[dict],
    ) -> Optional[Dict[str, Any]]:
        try:
            return self.summary_llm.invoke_json(
                self.answer_prompt_template,
                {
                    "question": question,
                    "job_docs_json": json.dumps(job_docs[:5], ensure_ascii=False, indent=2),
                    "news_docs_json": json.dumps(news_docs[:5], ensure_ascii=False, indent=2),
                },
            )
        except Exception:
            if not job_docs and not news_docs:
                return None

            answer_parts = []
            if job_docs:
                answer_parts.append(
                    f"招聘知识库命中 {len(job_docs)} 条证据，重点岗位包括："
                    + "；".join(doc.get("job_title", "") for doc in job_docs[:3] if doc.get("job_title"))
                )
            if news_docs:
                answer_parts.append(
                    f"资讯知识库命中 {len(news_docs)} 条证据，重点文章包括："
                    + "；".join(doc.get("title", "") for doc in news_docs[:3] if doc.get("title"))
                )
            return {
                "answer": "\n".join(answer_parts),
                "job_evidence": job_docs[:3],
                "news_evidence": news_docs[:3],
            }

    def run(
        self,
        *,
        question: str,
        retrieval_scope: str,
        filters: Dict[str, Any],
        top_k: int = 5,
        generate_answer: bool = False,
    ) -> Dict[str, Any]:
        query_plan = self.rewrite_query(
            question=question,
            source_scope=retrieval_scope,
            filters=filters,
        )

        rag_result = self.vector_service.search_sources(
            query=query_plan["query_text"],
            source_scope=retrieval_scope,
            top_k=top_k,
            company_name=filters.get("company_name"),
            product_line=filters.get("product_line"),
            job_location=filters.get("job_location"),
            text_type=query_plan.get("text_type"),
        )

        answer_payload = None
        if generate_answer:
            answer_payload = self.build_answer(
                question=question,
                job_docs=rag_result["job_docs"],
                news_docs=rag_result["news_docs"],
            )

        return {
            **rag_result,
            "query_text": query_plan["query_text"],
            "text_type": query_plan.get("text_type"),
            "retrieval_goal": query_plan["retrieval_goal"],
            "answer": answer_payload["answer"] if answer_payload else None,
            "job_evidence": answer_payload["job_evidence"] if answer_payload else [],
            "news_evidence": answer_payload["news_evidence"] if answer_payload else [],
            "error": None,
        }
