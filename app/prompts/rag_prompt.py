# -*- coding: utf-8 -*-
"""RAG prompt builders."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate


RAG_QUERY_SYSTEM_PROMPT = """
你是双知识库检索系统中的 Query Rewrite Agent。
你负责把用户问题改写成更适合向量检索的查询文本。

你会面对两类知识库：
- job: 招聘岗位要求与岗位职责
- news: 游戏行业资讯与报道

要求：
1. 不要回答问题，只做查询改写。
2. 如果问题更偏任职要求/岗位职责，text_type 优先输出 requirement 或 responsibility。
3. 如果无法确定 text_type，输出 null。
4. 只返回 JSON。

返回字段：
- query_text
- text_type
- retrieval_goal
""".strip()


RAG_ANSWER_SYSTEM_PROMPT = """
你是双知识库检索结果整理 Agent。
请基于提供的检索证据给出简洁回答，不允许编造证据中没有的结论。

返回字段：
- answer
- job_evidence
- news_evidence
""".strip()


def get_rag_query_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", RAG_QUERY_SYSTEM_PROMPT),
            (
                "human",
                """
检索范围：{source_scope}
路由过滤条件：
{filters_json}

用户问题：
{question}

请返回 JSON。
""".strip(),
            ),
        ]
    )


def get_rag_answer_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", RAG_ANSWER_SYSTEM_PROMPT),
            (
                "human",
                """
用户问题：
{question}

招聘证据：
{job_docs_json}

资讯证据：
{news_docs_json}

请返回 JSON。
""".strip(),
            ),
        ]
    )


def build_rag_query_prompt(question: str, source_scope: str, filters: dict) -> str:
    prompt = get_rag_query_prompt_template().invoke(
        {
            "question": question,
            "source_scope": source_scope,
            "filters_json": json.dumps(filters, ensure_ascii=False, indent=2),
        }
    )
    return prompt.to_string()


def build_rag_answer_prompt(
    *,
    question: str,
    job_docs: list[dict],
    news_docs: list[dict],
) -> str:
    prompt = get_rag_answer_prompt_template().invoke(
        {
            "question": question,
            "job_docs_json": json.dumps(job_docs, ensure_ascii=False, indent=2),
            "news_docs_json": json.dumps(news_docs, ensure_ascii=False, indent=2),
        }
    )
    return prompt.to_string()
