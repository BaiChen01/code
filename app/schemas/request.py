# -*- coding: utf-8 -*-
"""API request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    need_chart: bool = False
    refresh_mode: str = "none"


class SQLQueryRequest(BaseModel):
    nl_query: str = Field(..., min_length=1)


class RAGSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    source_scope: str = "job"
    company_filter: str | None = None
    product_line_filter: str | None = None
    job_location_filter: str | None = None
    text_type: str | None = None
    top_k: int = 5


class ChartGenerateRequest(BaseModel):
    chart_type: str | None = None
    dataset: list[dict] = Field(default_factory=list)
    title: str | None = None


class DataRefreshRequest(BaseModel):
    company_name: str | None = None
    mode: str = "incremental"
