# -*- coding: utf-8 -*-
"""Chart prompt helpers."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


CHART_SYSTEM_PROMPT = """
你是图表配置建议助手。
如果输入数据适合图表展示，请给出适合的图表类型和简短说明。
只返回 JSON。
""".strip()


def get_chart_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", CHART_SYSTEM_PROMPT),
            (
                "human",
                """
用户问题：
{question}

请根据字段和数据分布建议图表类型。
""".strip(),
            ),
        ]
    )
