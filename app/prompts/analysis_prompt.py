# -*- coding: utf-8 -*-
"""Analysis prompt builders."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate


ANALYSIS_SYSTEM_PROMPT = """
你是游戏企业情报分析系统中的 Analysis Agent。
你必须基于结构化结果、招聘证据、资讯证据和图表摘要，输出可解释、保守的结构化分析。

要求：
1. 招聘证据与资讯证据必须分开描述。
2. 不允许将资讯报道直接等同于招聘事实。
3. 不允许编造任何没有出现在输入中的事实。
4. 如果证据不足，要在 limitations 中明确说明。
5. 只返回 JSON。

返回字段：
- question_summary
- data_basis
- job_evidence
- news_evidence
- key_findings
- chart_explanation
- intelligence_judgment
- limitations
""".strip()


def get_analysis_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", ANALYSIS_SYSTEM_PROMPT),
            (
                "human",
                """
用户问题：
{question}

会话记忆（如无则 N/A）：
{memory_context}

路由结果：
{route_json}

SQL 结果：
{sql_result_json}

招聘证据：
{job_docs_json}

资讯证据：
{news_docs_json}

图表结果：
{chart_result_json}

请返回 JSON。
""".strip(),
            ),
        ]
    )


def build_analysis_prompt(
    *,
    question: str,
    route: dict,
    sql_result: dict | None,
    job_docs: list[dict],
    news_docs: list[dict],
    chart_result: dict | None,
    memory_context: str = "",
) -> str:
    prompt = get_analysis_prompt_template().invoke(
        {
            "question": question,
            "memory_context": memory_context or "N/A",
            "route_json": json.dumps(route, ensure_ascii=False, indent=2),
            "sql_result_json": json.dumps(sql_result or {}, ensure_ascii=False, indent=2),
            "job_docs_json": json.dumps(job_docs, ensure_ascii=False, indent=2),
            "news_docs_json": json.dumps(news_docs, ensure_ascii=False, indent=2),
            "chart_result_json": json.dumps(
                chart_result or {}, ensure_ascii=False, indent=2
            ),
        }
    )
    return prompt.to_string()
