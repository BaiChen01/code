# -*- coding: utf-8 -*-
"""API response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrievedDocsResponse(BaseModel):
    job_docs: list[dict[str, Any]] = Field(default_factory=list)
    news_docs: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0


class ChatMemoryResponse(BaseModel):
    session_id: str | None = None
    recent_message_count: int = 0
    session_summary: str | None = None
    summary_updated: bool = False
    summary_updated_at: str | None = None
    memory_error: str | None = None


class ChatQueryResponse(BaseModel):
    success: bool
    answer: str
    session_id: str | None = None
    intent_type: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)
    sql_result: dict[str, Any] | None = None
    retrieved_docs: RetrievedDocsResponse = Field(
        default_factory=RetrievedDocsResponse
    )
    chart_result: dict[str, Any] | None = None
    analysis_result: dict[str, Any] | None = None
    memory: ChatMemoryResponse = Field(default_factory=ChatMemoryResponse)
    error_message: str | None = None
