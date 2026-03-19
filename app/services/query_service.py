# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "game_intel_system",
    "charset": "utf8mb4",
}


class QueryService:
    """
    结构化查询服务
    定位：
    1. 封装固定 SQL 查询能力
    2. 返回统一结构化结果
    3. 为后续 SQL Agent 提供下层工具
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.db_config = db_config or DB_CONFIG

    def _get_conn(self):
        return pymysql.connect(
            **self.db_config,
            cursorclass=DictCursor,
        )

    def _format_result(
        self,
        columns: List[str],
        rows: List[Dict[str, Any]],
        summary: str,
    ) -> Dict[str, Any]:
        return {
            "columns": columns,
            "rows": rows,
            "summary": summary,
        }

    def get_company_job_count(self) -> Dict[str, Any]:
        """
        统计各企业岗位数量
        适合问题：
        - 哪些企业招聘最活跃
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            sql = """
            SELECT
                c.company_name,
                COUNT(*) AS job_count
            FROM job_post jp
            JOIN company c ON jp.company_id = c.id
            WHERE jp.status = 'active'
            GROUP BY c.company_name
            ORDER BY job_count DESC, c.company_name ASC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()

            return self._format_result(
                columns=["company_name", "job_count"],
                rows=rows,
                summary=f"共统计 {len(rows)} 家企业的在招岗位数量。",
            )
        finally:
            cursor.close()
            conn.close()

    def get_city_job_count(self, company_name: Optional[str] = None) -> Dict[str, Any]:
        """
        统计各城市岗位数量
        可按企业过滤

        适合问题：
        - 上海地区哪些企业岗位最多
        - 腾讯游戏在哪些城市布局招聘
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            sql = """
            SELECT
                jp.job_location,
                COUNT(*) AS job_count
            FROM job_post jp
            JOIN company c ON jp.company_id = c.id
            WHERE jp.status = 'active'
            """
            params: List[Any] = []

            if company_name:
                sql += " AND c.company_name = %s"
                params.append(company_name)

            sql += """
            GROUP BY jp.job_location
            ORDER BY job_count DESC, jp.job_location ASC
            """

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            summary = (
                f"已统计企业【{company_name}】在各城市的岗位数量，共 {len(rows)} 个地点。"
                if company_name
                else f"已统计全部企业在各城市的岗位数量，共 {len(rows)} 个地点。"
            )

            return self._format_result(
                columns=["job_location", "job_count"],
                rows=rows,
                summary=summary,
            )
        finally:
            cursor.close()
            conn.close()

    def get_product_line_job_count(self, company_name: Optional[str] = None) -> Dict[str, Any]:
        """
        统计产品线岗位数量
        适合问题：
        - 某企业哪些产品线招聘更多
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            sql = """
            SELECT
                COALESCE(NULLIF(jp.product_line, ''), '未标注产品线') AS product_line,
                COUNT(*) AS job_count
            FROM job_post jp
            JOIN company c ON jp.company_id = c.id
            WHERE jp.status = 'active'
            """
            params: List[Any] = []

            if company_name:
                sql += " AND c.company_name = %s"
                params.append(company_name)

            sql += """
            GROUP BY COALESCE(NULLIF(jp.product_line, ''), '未标注产品线')
            ORDER BY job_count DESC, product_line ASC
            """

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            summary = (
                f"已统计企业【{company_name}】各产品线岗位数量，共 {len(rows)} 条。"
                if company_name
                else f"已统计全部企业各产品线岗位数量，共 {len(rows)} 条。"
            )

            return self._format_result(
                columns=["product_line", "job_count"],
                rows=rows,
                summary=summary,
            )
        finally:
            cursor.close()
            conn.close()

    def search_jobs(
        self,
        company_name: Optional[str] = None,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        查询岗位列表
        支持按企业、关键词、地点过滤

        适合问题：
        - 腾讯有哪些客户端岗位
        - 网易在上海有哪些岗位
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
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
            """
            params: List[Any] = []

            if company_name:
                sql += " AND c.company_name = %s"
                params.append(company_name)

            if keyword:
                sql += """
                AND (
                    jp.job_title LIKE %s
                    OR jp.product_line LIKE %s
                )
                """
                kw = f"%{keyword}%"
                params.extend([kw, kw])

            if location:
                sql += " AND jp.job_location LIKE %s"
                params.append(f"%{location}%")

            sql += """
            ORDER BY jp.crawl_time DESC, jp.id DESC
            LIMIT %s
            """
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            summary_parts = ["岗位列表查询完成"]
            if company_name:
                summary_parts.append(f"企业={company_name}")
            if keyword:
                summary_parts.append(f"关键词={keyword}")
            if location:
                summary_parts.append(f"地点={location}")
            summary_parts.append(f"返回 {len(rows)} 条记录")

            return self._format_result(
                columns=[
                    "job_post_id",
                    "company_name",
                    "job_title",
                    "product_line",
                    "job_location",
                    "source_url",
                    "crawl_time",
                ],
                rows=rows,
                summary="，".join(summary_parts) + "。",
            )
        finally:
            cursor.close()
            conn.close()

    def get_jobs_by_ids(self, job_ids: List[int]) -> Dict[str, Any]:
        """
        根据岗位 ID 获取详细岗位记录
        用于 SQL + RAG 联动
        """
        if not job_ids:
            return self._format_result(
                columns=[],
                rows=[],
                summary="未提供岗位 ID。",
            )

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
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
            """

            cursor.execute(sql, job_ids)
            rows = cursor.fetchall()

            return self._format_result(
                columns=[
                    "job_post_id",
                    "company_name",
                    "job_title",
                    "product_line",
                    "job_location",
                    "source_url",
                    "crawl_time",
                    "cleaned_requirement",
                    "cleaned_responsibility",
                ],
                rows=rows,
                summary=f"根据岗位 ID 查询完成，返回 {len(rows)} 条记录。",
            )
        finally:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    qs = QueryService()

    print("=== 1. 企业岗位统计 ===")
    result = qs.get_company_job_count()
    print(result["summary"])
    for row in result["rows"][:5]:
        print(row)

    print("\n=== 2. 城市岗位统计（腾讯游戏） ===")
    result = qs.get_city_job_count(company_name="腾讯游戏")
    print(result["summary"])
    for row in result["rows"][:5]:
        print(row)

    print("\n=== 3. 产品线岗位统计（网易游戏） ===")
    result = qs.get_product_line_job_count(company_name="网易游戏")
    print(result["summary"])
    for row in result["rows"][:5]:
        print(row)

    print("\n=== 4. 岗位搜索 ===")
    result = qs.search_jobs(company_name="腾讯游戏", keyword="客户端", location="上海", limit=10)
    print(result["summary"])
    for row in result["rows"][:5]:
        print(row)

    print("\n=== 5. 根据 ID 查询岗位详情 ===")
    result = qs.get_jobs_by_ids([1, 2, 3])
    print(result["summary"])
    for row in result["rows"][:3]:
        print(row)