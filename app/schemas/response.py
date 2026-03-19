# -*- coding: utf-8 -*-
"""API response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievedDocsResponse(BaseModel):
    job_docs: list[dict[str, Any]] = Field(default_factory=list)
    news_docs: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0


class ChatQueryResponse(BaseModel):
    success: bool
    answer: str
    intent_type: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)
    sql_result: dict[str, Any] | None = None
    retrieved_docs: RetrievedDocsResponse = Field(
        default_factory=RetrievedDocsResponse
    )
    chart_result: dict[str, Any] | None = None
    analysis_result: dict[str, Any] | None = None
    error_message: str | None = None
