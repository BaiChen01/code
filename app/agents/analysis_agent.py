# -*- coding: utf-8 -*-
"""Analysis agent for final structured reasoning."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.llm_factory import get_llm
from app.core.model_config import (
    ANALYSIS_MAX_TOKENS,
    ANALYSIS_MODEL,
    ANALYSIS_TEMPERATURE,
    ANALYSIS_TOP_P,
)
from app.prompts.analysis_prompt import get_analysis_prompt_template


def _stringify_job_doc(doc: Dict[str, Any]) -> str:
    company_name = doc.get("company_name") or "未知企业"
    job_title = doc.get("job_title") or "未知岗位"
    text_type = doc.get("text_type") or "unknown"
    return f"{company_name} / {job_title} / {text_type}: {doc.get('snippet', '')[:120]}"


def _stringify_news_doc(doc: Dict[str, Any]) -> str:
    company_name = doc.get("company_name") or "未知企业"
    title = doc.get("title") or "未知文章"
    publish_time = doc.get("publish_time") or "未知时间"
    return f"{company_name} / {title} / {publish_time}: {doc.get('snippet', '')[:120]}"


class AnalysisAgent:
    def __init__(self) -> None:
        self.llm = get_llm(
            model=ANALYSIS_MODEL,
            temperature=ANALYSIS_TEMPERATURE,
            max_tokens=ANALYSIS_MAX_TOKENS,
            top_p=ANALYSIS_TOP_P,
        )
        self.prompt_template = get_analysis_prompt_template()

    def _fallback_analysis(
        self,
        *,
        question: str,
        route: Dict[str, Any],
        sql_result: Optional[Dict[str, Any]],
        job_docs: List[Dict[str, Any]],
        news_docs: List[Dict[str, Any]],
        chart_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        data_basis = []
        if sql_result and sql_result.get("rows") is not None:
            data_basis.append(sql_result.get("summary", "SQL result available."))
        if job_docs:
            data_basis.append(f"招聘知识库命中 {len(job_docs)} 条证据。")
        if news_docs:
            data_basis.append(f"资讯知识库命中 {len(news_docs)} 条证据。")

        key_findings = []
        if sql_result and sql_result.get("rows"):
            key_findings.append(f"SQL 返回 {len(sql_result['rows'])} 条结构化记录。")
        if job_docs:
            key_findings.append("招聘证据显示相关岗位要求或职责存在明确文本线索。")
        if news_docs:
            key_findings.append("资讯证据显示外部报道中存在与问题相关的动态信息。")

        return {
            "question_summary": question,
            "data_basis": data_basis or ["当前可用证据较少。"],
            "job_evidence": [_stringify_job_doc(doc) for doc in job_docs[:3]],
            "news_evidence": [_stringify_news_doc(doc) for doc in news_docs[:3]],
            "key_findings": key_findings or ["当前证据不足以支持强结论。"],
            "chart_explanation": (
                chart_result.get("chart_summary")
                if chart_result
                else "本次未生成图表。"
            ),
            "intelligence_judgment": (
                "基于当前结构化结果、招聘证据与资讯证据，可以形成初步判断，但仍需结合更多样本。"
            ),
            "limitations": [
                "当前回退结果来自规则化汇总，不是完整模型分析。",
                "如果缺少 SQL 或 RAG 证据，结论会明显受限。",
            ],
        }

    def run(
        self,
        *,
        question: str,
        route: Dict[str, Any],
        sql_result: Optional[Dict[str, Any]],
        job_docs: List[Dict[str, Any]],
        news_docs: List[Dict[str, Any]],
        chart_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            return self.llm.invoke_json(
                self.prompt_template,
                {
                    "question": question,
                    "route_json": json.dumps(route, ensure_ascii=False, indent=2),
                    "sql_result_json": json.dumps(
                        sql_result or {}, ensure_ascii=False, indent=2
                    ),
                    "job_docs_json": json.dumps(job_docs[:5], ensure_ascii=False, indent=2),
                    "news_docs_json": json.dumps(
                        news_docs[:5], ensure_ascii=False, indent=2
                    ),
                    "chart_result_json": json.dumps(
                        chart_result or {}, ensure_ascii=False, indent=2
                    ),
                },
            )
        except Exception:
            return self._fallback_analysis(
                question=question,
                route=route,
                sql_result=sql_result,
                job_docs=job_docs,
                news_docs=news_docs,
                chart_result=chart_result,
            )
