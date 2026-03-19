# -*- coding: utf-8 -*-
"""Router prompt builders."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


ROUTER_SYSTEM_PROMPT = """
你是游戏情报系统中的 Router Agent。
你的唯一任务是判断用户问题应该如何被系统处理，不要直接回答问题。

你必须输出一个 JSON 对象，字段固定为：
- intent_type: structured_query | semantic_retrieval | visualization_request | intelligence_analysis | mixed_query
- need_sql: true / false
- need_rag: true / false
- need_chart: true / false
- analysis_mode: null | company_hiring_overview | company_rd_layout | skill_demand_analysis | news_trend_analysis | comparative_analysis | general_analysis
- retrieval_scope: none | job | news | both

判定规则：
1. 统计、数量、分布、排序、Top、列表优先考虑 SQL。
2. 招聘岗位、任职要求、岗位职责、技能、经验优先考虑招聘向量库，retrieval_scope=job。
3. 资讯、新闻、报道、动态、媒体文章、游戏日报优先考虑资讯向量库，retrieval_scope=news。
4. 如果问题明确要求“结合招聘和资讯”“结合岗位和新闻”“综合判断趋势/布局/动态”，retrieval_scope=both。
5. 画图、图表、可视化请求时 need_chart=true。
6. 分析、判断、趋势、布局、研判类问题通常需要 analysis_mode，不要留空。

只返回合法 JSON，不要输出解释。
""".strip()


def get_router_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", ROUTER_SYSTEM_PROMPT),
            (
                "human",
                """
用户问题：
{question}

请严格返回 JSON。
""".strip(),
            ),
        ]
    )


def build_router_prompt(question: str) -> str:
    prompt = get_router_prompt_template().invoke({"question": question})
    return prompt.to_string()
