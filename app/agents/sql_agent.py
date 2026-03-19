# -*- coding: utf-8 -*-
"""SQL generation and execution agent."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.core.config import get_settings
from app.core.llm_factory import get_llm
from app.core.model_config import SQL_MAX_TOKENS, SQL_MODEL, SQL_TEMPERATURE, SQL_TOP_P
from app.prompts.sql_prompt import get_sql_prompt_template
from app.services.query_service import QueryService
from app.utils.sql_guard import SQLGuardError, validate_select_sql


class SQLAgent:
    def __init__(self) -> None:
        self.query_service = QueryService()
        self.llm = get_llm(
            model=SQL_MODEL,
            temperature=SQL_TEMPERATURE,
            max_tokens=SQL_MAX_TOKENS,
            top_p=SQL_TOP_P,
        )
        self.prompt_template = get_sql_prompt_template()
        self.default_sql_limit = get_settings().default_sql_limit

    def _build_sql_task(self, *, question: str, filters: Dict[str, Any]) -> str:
        company_name = filters.get("company_name")
        job_location = filters.get("job_location")
        keyword = filters.get("keyword")

        if "岗位数量" in question and ("对比" in question or "比较" in question):
            return "仅基于招聘数据库，统计各企业 active 岗位数量，用于后续对比或绘图。"

        if company_name and ("研发" in question or "布局" in question):
            return (
                f"仅基于招聘数据库，提取 {company_name} 的招聘结构化事实，用于支撑研发布局分析。"
                "优先统计岗位在城市、产品线、岗位名称上的分布或数量。"
            )

        if company_name and job_location:
            return (
                f"仅基于招聘数据库，查询 {company_name} 在 {job_location} 的 active 岗位数量、"
                "岗位分布或岗位明细。"
            )

        if company_name:
            return (
                f"仅基于招聘数据库，查询 {company_name} 的 active 招聘岗位数量、城市分布、"
                "产品线分布或岗位明细。"
            )

        if keyword:
            return (
                f"仅基于招聘数据库，查询与 {keyword} 相关的岗位数量、岗位分布或岗位明细。"
            )

        return (
            "如果原问题包含资讯、新闻、报道、趋势判断或综合分析，只抽取其中可由招聘数据库"
            "直接回答的结构化子问题，并生成单条 SELECT SQL。"
        )

    def _generate_sql(
        self,
        *,
        question: str,
        filters: Dict[str, Any],
        previous_sql: str = "",
        previous_error: str = "",
    ) -> Dict[str, Any]:
        return self.llm.invoke_json(
            self.prompt_template,
            {
                "schema_info": self.query_service.get_schema_description(),
                "filters_json": json.dumps(filters, ensure_ascii=False, indent=2),
                "question": question,
                "sql_task": self._build_sql_task(question=question, filters=filters),
                "previous_sql": previous_sql or "N/A",
                "previous_error": previous_error or "N/A",
            },
        )

    def run(self, *, question: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        previous_sql = ""
        previous_error = ""
        last_error = "SQL generation did not run."

        for _ in range(2):
            try:
                payload = self._generate_sql(
                    question=question,
                    filters=filters,
                    previous_sql=previous_sql,
                    previous_error=previous_error,
                )
            except Exception as exc:
                return {
                    "sql": previous_sql,
                    "columns": [],
                    "rows": [],
                    "summary": "Failed to call SQL generation model.",
                    "error": str(exc),
                }

            if not payload.get("success", True):
                return {
                    "sql": "",
                    "columns": [],
                    "rows": [],
                    "summary": "SQL generation returned an error.",
                    "error": payload.get("error") or "Unknown SQL generation error.",
                }

            generated_sql = payload.get("sql", "")
            try:
                guarded_sql = validate_select_sql(
                    generated_sql,
                    default_limit=self.default_sql_limit,
                )
            except SQLGuardError as exc:
                previous_sql = generated_sql
                previous_error = str(exc)
                last_error = str(exc)
                continue

            result = self.query_service.execute_select_sql(guarded_sql)
            result["sql"] = guarded_sql
            result["query_intent"] = payload.get("query_intent")
            result["reason"] = payload.get("reason")

            if not result.get("error"):
                return result

            previous_sql = guarded_sql
            previous_error = result["error"]
            last_error = result["error"]

        return {
            "sql": previous_sql,
            "columns": [],
            "rows": [],
            "summary": "SQL execution failed after retries.",
            "error": last_error,
        }
