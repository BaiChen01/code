# -*- coding: utf-8 -*-
"""SQL prompt builders."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate


SQL_SYSTEM_PROMPT = """
你是游戏企业招聘情报系统中的 SQL Agent。
你的任务是把用户问题中“能够由当前招聘数据库直接回答的结构化部分”转换成安全、保守、可执行的单条 MySQL SELECT 语句。

硬性约束：
1. 只能输出单条 SELECT SQL。
2. 不允许 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE、CREATE、REPLACE。
3. 只能使用 schema 中给出的表和字段。
4. 如果原问题包含资讯、报道、外部新闻、综合判断、推理结论等非 SQL 部分，必须忽略这些部分，只保留可由招聘数据库回答的子问题。
5. 优先围绕岗位数量、岗位分布、城市分布、产品线分布、岗位明细等招聘结构化事实生成 SQL。
6. 只有在当前 schema 中连合理的结构化子问题都无法抽取时，才返回 success=false 和 error。
7. 返回 JSON，不要输出解释文字。

返回字段：
- success: 布尔值
- sql: 生成的 SQL
- query_intent: 结构化查询意图
- reason: 生成原因
- error: 失败原因
""".strip()


def get_sql_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SQL_SYSTEM_PROMPT),
            (
                "human",
                """
数据库 schema：
{schema_info}

路由过滤条件：
{filters_json}

会话记忆（如无则 N/A）：
{memory_context}

用户问题：
{question}

SQL 任务聚焦：
{sql_task}

上一轮 SQL（如果有）：
{previous_sql}

上一轮错误（如果有）：
{previous_error}

请返回 JSON。
""".strip(),
            ),
        ]
    )


def build_sql_prompt(
    *,
    schema_info: str,
    question: str,
    filters: dict,
    sql_task: str,
    memory_context: str = "",
    previous_sql: str = "",
    previous_error: str = "",
) -> str:
    prompt = get_sql_prompt_template().invoke(
        {
            "schema_info": schema_info,
            "filters_json": json.dumps(filters, ensure_ascii=False, indent=2),
            "memory_context": memory_context or "N/A",
            "question": question,
            "sql_task": sql_task,
            "previous_sql": previous_sql or "N/A",
            "previous_error": previous_error or "N/A",
        }
    )
    return prompt.to_string()
