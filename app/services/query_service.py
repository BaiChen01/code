# -*- coding: utf-8 -*-
"""Structured query service backed by MySQL."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db_factory import get_engine


SCHEMA_DESCRIPTION = """
Database: game_intel_system

Table company
- id
- company_name
- company_alias
- created_at
- updated_at

Table job_post
- id
- company_id
- source_url
- job_title
- product_line
- job_location
- crawl_time
- status
- raw_doc_id
- raw_text_hash
- created_at
- updated_at

Table job_text
- id
- job_post_id
- job_requirement
- job_responsibility
- cleaned_requirement
- cleaned_responsibility
- created_at
- updated_at

Table vector_mapping
- id
- job_post_id
- vector_doc_id
- text_type
- chunk_count
- created_at

Relationship notes
- company.id = job_post.company_id
- job_post.id = job_text.job_post_id
- job_post.id = vector_mapping.job_post_id
- active job rows should use job_post.status = 'active'
""".strip()


class QueryService:
    """Provides SQL execution and a few compatibility helpers."""

    def __init__(self) -> None:
        self.engine = get_engine()
        self.default_limit = get_settings().default_sql_limit

    def get_schema_description(self) -> str:
        return SCHEMA_DESCRIPTION

    def _format_result(
        self,
        *,
        sql: str,
        columns: List[str],
        rows: List[Dict[str, Any]],
        summary: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "summary": summary,
            "error": error,
        }

    def execute_select_sql(
        self,
        sql: str,
        parameters: Optional[Iterable[Any] | Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            with self.engine.connect() as connection:
                if isinstance(parameters, list):
                    parameters = tuple(parameters)
                if parameters is None:
                    result = connection.exec_driver_sql(sql)
                else:
                    result = connection.exec_driver_sql(sql, parameters)
                rows = [dict(row._mapping) for row in result.fetchall()]
                columns = list(result.keys())
        except SQLAlchemyError as exc:
            return self._format_result(
                sql=sql,
                columns=[],
                rows=[],
                summary="SQL execution failed.",
                error=str(exc),
            )

        summary = f"Query returned {len(rows)} rows."
        return self._format_result(
            sql=sql,
            columns=columns,
            rows=rows,
            summary=summary,
            error=None,
        )

    def get_company_job_count(self) -> Dict[str, Any]:
        sql = """
        SELECT
            c.company_name,
            COUNT(*) AS job_count
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        WHERE jp.status = 'active'
        GROUP BY c.company_name
        ORDER BY job_count DESC, c.company_name ASC
        LIMIT 100
        """.strip()
        result = self.execute_select_sql(sql)
        result["summary"] = f"Found {len(result['rows'])} companies with active jobs."
        return result

    def get_city_job_count(self, company_name: Optional[str] = None) -> Dict[str, Any]:
        base_sql = """
        SELECT
            jp.job_location,
            COUNT(*) AS job_count
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        WHERE jp.status = 'active'
        """.strip()
        params: list[Any] = []
        if company_name:
            base_sql += " AND c.company_name = %s"
            params.append(company_name)
        base_sql += """
        GROUP BY jp.job_location
        ORDER BY job_count DESC, jp.job_location ASC
        LIMIT 100
        """.strip()
        result = self.execute_select_sql(base_sql, params)
        if company_name:
            result["summary"] = (
                f"Found {len(result['rows'])} locations for company {company_name}."
            )
        else:
            result["summary"] = f"Found {len(result['rows'])} city rows."
        return result

    def get_product_line_job_count(
        self, company_name: Optional[str] = None
    ) -> Dict[str, Any]:
        base_sql = """
        SELECT
            COALESCE(NULLIF(jp.product_line, ''), '未标注产品线') AS product_line,
            COUNT(*) AS job_count
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        WHERE jp.status = 'active'
        """.strip()
        params: list[Any] = []
        if company_name:
            base_sql += " AND c.company_name = %s"
            params.append(company_name)
        base_sql += """
        GROUP BY COALESCE(NULLIF(jp.product_line, ''), '未标注产品线')
        ORDER BY job_count DESC, product_line ASC
        LIMIT 100
        """.strip()
        result = self.execute_select_sql(base_sql, params)
        result["summary"] = (
            f"Found {len(result['rows'])} product lines."
            if not company_name
            else f"Found {len(result['rows'])} product lines for {company_name}."
        )
        return result

    def search_jobs(
        self,
        company_name: Optional[str] = None,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        sql = """
        SELECT
            jp.id AS job_post_id,
            c.company_name,
            jp.job_title,
            jp.product_line,
            jp.job_location,
            jp.source_url,
            jp.crawl_time
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        WHERE jp.status = 'active'
        """.strip()
        params: list[Any] = []

        if company_name:
            sql += " AND c.company_name = %s"
            params.append(company_name)

        if keyword:
            sql += """
            AND (
                jp.job_title LIKE %s
                OR jp.product_line LIKE %s
            )
            """.strip()
            like_value = f"%{keyword}%"
            params.extend([like_value, like_value])

        if location:
            sql += " AND jp.job_location LIKE %s"
            params.append(f"%{location}%")

        sql += " ORDER BY jp.crawl_time DESC, jp.id DESC LIMIT %s"
        params.append(limit)

        result = self.execute_select_sql(sql, params)
        result["summary"] = f"Returned {len(result['rows'])} jobs."
        return result

    def get_jobs_by_ids(self, job_ids: List[int]) -> Dict[str, Any]:
        if not job_ids:
            return self._format_result(
                sql="",
                columns=[],
                rows=[],
                summary="No job ids provided.",
                error=None,
            )

        placeholders = ",".join(["%s"] * len(job_ids))
        sql = f"""
        SELECT
            jp.id AS job_post_id,
            c.company_name,
            jp.job_title,
            jp.product_line,
            jp.job_location,
            jp.source_url,
            jp.crawl_time,
            jt.cleaned_requirement,
            jt.cleaned_responsibility
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        JOIN job_text jt ON jp.id = jt.job_post_id
        WHERE jp.id IN ({placeholders})
        ORDER BY jp.id ASC
        """.strip()
        result = self.execute_select_sql(sql, job_ids)
        result["summary"] = f"Returned {len(result['rows'])} job detail rows."
        return result
