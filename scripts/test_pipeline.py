# -*- coding: utf-8 -*-
"""
最小闭环测试脚本

作用：
1. 测试结构化查询(QueryService)
2. 测试向量检索(VectorService)
3. 测试 SQL + RAG 的最小闭环

说明：
- 这是开发阶段的总测试入口
- 不是正式接口文件
- 便于后续写测试报告、截图和排查问题

运行方式：
python scripts/test_pipeline.py
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List


# =========================
# 处理项目根路径
# 这样脚本可以正确导入 app 下的模块
# =========================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


# =========================
# 导入项目内部服务
# =========================
from app.services.query_service import QueryService
from app.services.vector_service import VectorService


def print_section(title: str) -> None:
    """
    打印清晰的测试分块标题
    便于终端查看，也便于后续截图写测试报告
    """
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_rows(rows: List[Dict], limit: int = 5) -> None:
    """
    打印结构化查询结果的前几条
    避免一次性输出过多内容
    """
    if not rows:
        print("无数据。")
        return

    for idx, row in enumerate(rows[:limit], start=1):
        print(f"[{idx}] {row}")

    if len(rows) > limit:
        print(f"... 共 {len(rows)} 条，仅展示前 {limit} 条")


def print_rag_docs(documents: List[str], metadatas: List[Dict], limit: int = 5) -> None:
    """
    打印 RAG 检索结果
    展示文本片段 + 元数据，便于人工核验检索质量
    """
    if not documents:
        print("无检索结果。")
        return

    display_count = min(len(documents), limit)

    for idx in range(display_count):
        print(f"[{idx + 1}] 文本片段：")
        print(documents[idx])
        print("元数据：")
        print(metadatas[idx] if idx < len(metadatas) else {})
        print("-" * 50)

    if len(documents) > limit:
        print(f"... 共 {len(documents)} 条，仅展示前 {limit} 条")


def test_sql_queries() -> None:
    """
    测试一组结构化查询
    包括：
    1. 企业岗位统计
    2. 城市分布统计
    """
    print_section("===== SQL TEST =====")

    qs = QueryService()

    # -------------------------
    # 测试1：企业岗位统计
    # 用于验证：
    # - company / job_post 表联查是否正常
    # - 数据是否已经正确入库
    # -------------------------
    print("\n[测试1] 企业岗位统计：get_company_job_count()")
    result = qs.get_company_job_count()
    print("summary:", result["summary"])
    print_rows(result["rows"], limit=10)

    # -------------------------
    # 测试2：城市分布统计
    # 用于验证：
    # - 城市字段是否正常
    # - 企业过滤是否生效
    # -------------------------
    print("\n[测试2] 城市分布统计：get_city_job_count(company_name='腾讯游戏')")
    result = qs.get_city_job_count(company_name="腾讯游戏")
    print("summary:", result["summary"])
    print_rows(result["rows"], limit=10)


def test_rag_search() -> None:
    """
    测试向量检索
    示例问题：
    - Unity 开发经验
    用于验证：
    - 向量库是否已建立
    - 检索结果是否确实命中相关岗位文本
    """
    print_section("===== RAG TEST =====")

    vs = VectorService()

    query = "Unity 开发经验"

    # -------------------------
    # 这里用 requirement 检索更符合“岗位要求”场景
    # 便于判断检索是否真的命中相关能力要求
    # -------------------------
    print(f"\n[测试3] 向量检索:query='{query}'")
    result = vs.search(
        query=query,
        top_k=5,
        text_type="requirement",
    )

    documents = result.get("documents", [[]])[0] if result.get("documents") else []
    metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []

    print_rag_docs(documents, metadatas, limit=5)


def test_mini_pipeline() -> None:
    """
    最小闭环测试：
    模拟一个问题，同时做 SQL + RAG

    示例问题：
    腾讯游戏哪些岗位要求 AI 能力？

    测试逻辑：
    1. SQL：先查腾讯游戏岗位列表
    2. RAG：再查 AI 相关文本
    3. 打印岗位名 + 文本证据
    """
    print_section("===== PIPELINE TEST =====")

    qs = QueryService()
    vs = VectorService()

    question = "腾讯游戏哪些岗位要求 AI 能力？"
    print(f"\n问题：{question}")

    # -------------------------
    # 第一步：SQL 查询
    # 先从结构化数据中筛出腾讯游戏岗位
    # 这里用 keyword='AI' 做第一层粗筛
    # 如果后续你想更稳，可以改成更灵活的规则路由
    # -------------------------
    print("\n[步骤1] SQL 查询腾讯游戏相关岗位")
    sql_result = qs.search_jobs(
        company_name="腾讯游戏",
        keyword="AI",
        location=None,
        limit=20,
    )

    print("summary:", sql_result["summary"])
    print_rows(sql_result["rows"], limit=10)

    # -------------------------
    # 第二步：RAG 检索
    # 在腾讯游戏范围内查“AI 能力”
    # 用 requirement 检索，优先看岗位要求里有没有提到 AI
    # -------------------------
    print("\n[步骤2] RAG 检索 AI 相关文本证据")
    rag_result = vs.search(
        query="AI 能力 大模型 算法 机器学习 深度学习",
        top_k=5,
        company_name="腾讯游戏",
        text_type="requirement",
    )

    documents = rag_result.get("documents", [[]])[0] if rag_result.get("documents") else []
    metadatas = rag_result.get("metadatas", [[]])[0] if rag_result.get("metadatas") else []

    print_rag_docs(documents, metadatas, limit=5)

    # -------------------------
    # 第三步：输出最小闭环结果
    # 这里不是正式分析，只是把 SQL 岗位信息和 RAG 证据并排展示
    # 便于人工判断这两部分能否协同工作
    # -------------------------
    print("\n[步骤3] 最小闭环结果汇总")

    if sql_result["rows"]:
        print("SQL 命中的岗位：")
        for row in sql_result["rows"][:10]:
            print(
                f"- job_post_id={row.get('job_post_id')} "
                f"| 公司={row.get('company_name')} "
                f"| 岗位={row.get('job_title')} "
                f"| 地点={row.get('job_location')} "
                f"| 产品线={row.get('product_line')}"
            )
    else:
        print("SQL 未命中岗位。")

    if metadatas:
        print("\nRAG 命中的文本来源：")
        for meta in metadatas[:5]:
            print(
                f"- job_post_id={meta.get('job_post_id')} "
                f"| 公司={meta.get('company_name')} "
                f"| 岗位={meta.get('job_title')} "
                f"| 文本类型={meta.get('text_type')}"
            )
    else:
        print("RAG 未命中文本证据。")

    print("\n结论：")
    print("请人工判断 SQL 命中的岗位列表与 RAG 返回的证据片段是否语义一致。")
    print("如果二者一致，说明当前最小闭环已经打通。")


def main() -> None:
    """
    总测试入口
    建议开发时每完成一个模块就跑一次
    """
    print_section("最小闭环测试开始")

    test_sql_queries()
    test_rag_search()
    test_mini_pipeline()

    print_section("最小闭环测试结束")


if __name__ == "__main__":
    main()