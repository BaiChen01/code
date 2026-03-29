# -*- coding: utf-8 -*-
"""Prompt builders for session memory summarization."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


MEMORY_SUMMARY_SYSTEM_PROMPT = """
You are a session memory summarization assistant for a game intelligence agent.
Your task is to compress the existing session summary and the latest conversation
turns into a concise, factual memory block that can be reused in future rounds.

Rules:
1. Preserve only durable context that helps future follow-up questions.
2. Keep company names, products, cities, analysis goals, and explicit user preferences.
3. Do not invent facts that are not present in the input.
4. Prefer short bullet-like statements merged into one concise paragraph.
5. Return valid JSON only.

Return fields:
- summary: concise reusable session summary
""".strip()


def get_memory_summary_prompt_template() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", MEMORY_SUMMARY_SYSTEM_PROMPT),
            (
                "human",
                """
Existing session summary:
{existing_summary}

Latest conversation turns:
{recent_messages}

Return JSON.
""".strip(),
            ),
        ]
    )
