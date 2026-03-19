# -*- coding: utf-8 -*-
"""
主控路由智能体（全 LLM 版）

职责：
1. 接收用户问题
2. 调用大模型判断问题意图
3. 输出标准化路由结果
4. 为 LangGraph 提供稳定输入

说明：
- 本版本不再使用规则分类
- intent_type / need_sql / need_rag / need_chart / analysis_mode
  全部由 LLM 判断
- filters 仍然保留轻量规则抽取，避免公司名、城市名、关键词漂移
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.core.llm_client import call_llm_json
from app.core.model_config import (
    ROUTER_MODEL,
    ROUTER_TEMPERATURE,
    ROUTER_MAX_TOKENS,
    ROUTER_TOP_P,
)
from app.prompts.router_prompt import build_router_prompt


# =========================
# 常量配置
# =========================

COMPANY_ALIASES = {
    "腾讯游戏": ["腾讯", "腾讯游戏", "Tencent Games"],
    "网易游戏": ["网易", "网易游戏"],
    "米哈游": ["米哈游", "miHoYo", "HoYoverse"],
}

CITY_KEYWORDS = ["上海", "北京", "广州", "深圳", "杭州", "成都"]

TECH_KEYWORDS = [
    "Unity", "UE", "UE4", "UE5", "AI", "AIGC",
    "大模型", "图形渲染", "工具链", "客户端", "服务端"
]

VALID_INTENT_TYPES = {
    "structured_query",
    "semantic_retrieval",
    "visualization_request",
    "intelligence_analysis",
    "mixed_query",
}


# =========================
# 基础工具函数
# =========================

def normalize_question(question: str) -> str:
    """
    对用户问题做轻量标准化：
    1. 去首尾空格
    2. 合并多余空白字符
    """
    if not question:
        return ""

    question = question.strip()
    question = re.sub(r"\s+", " ", question)
    return question


def extract_company(question: str) -> Optional[str]:
    """
    从问题中识别企业标准名
    """
    lower_q = question.lower()

    for standard_name, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lower_q:
                return standard_name

    return None


def extract_city(question: str) -> Optional[str]:
    """
    从问题中识别地点
    """
    for city in CITY_KEYWORDS:
        if city in question:
            return city
    return None


def extract_keyword(question: str) -> Optional[str]:
    """
    从问题中识别技术关键词
    第一版只取第一个明显命中的关键词
    """
    lower_q = question.lower()

    for kw in TECH_KEYWORDS:
        if kw.lower() in lower_q:
            return kw
    return None


def extract_filters(question: str) -> Dict[str, Optional[str]]:
    """
    从问题中抽取轻量过滤条件

    说明：
    - 虽然路由逻辑全交给 LLM
    - 但 filters 仍建议由规则抽取，便于后续 SQL / RAG 复用
    """
    return {
        "company_name": extract_company(question),
        "job_location": extract_city(question),
        "product_line": None,
        "keyword": extract_keyword(question),
    }


def validate_route_result(route_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    对 LLM 输出做兜底校验，确保字段稳定
    """
    intent_type = route_result.get("intent_type")
    if intent_type not in VALID_INTENT_TYPES:
        route_result["intent_type"] = "mixed_query"

    route_result["need_sql"] = bool(route_result.get("need_sql", False))
    route_result["need_rag"] = bool(route_result.get("need_rag", False))
    route_result["need_chart"] = bool(route_result.get("need_chart", False))

    if "analysis_mode" not in route_result:
        route_result["analysis_mode"] = None

    if "filters" not in route_result or not isinstance(route_result["filters"], dict):
        route_result["filters"] = {
            "company_name": None,
            "job_location": None,
            "product_line": None,
            "keyword": None,
        }

    if "raw_question" not in route_result:
        route_result["raw_question"] = ""

    if "normalized_question" not in route_result:
        route_result["normalized_question"] = ""

    return route_result


def merge_route_result(
    question: str,
    normalized_question: str,
    filters: Dict[str, Optional[str]],
    llm_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    合并 LLM 输出与系统标准字段

    说明：
    - 核心路由字段由 LLM 决定
    - filters 以规则抽取为主，避免实体漂移
    """
    result = {
        "intent_type": llm_result.get("intent_type"),
        "need_sql": llm_result.get("need_sql", False),
        "need_rag": llm_result.get("need_rag", False),
        "need_chart": llm_result.get("need_chart", False),
        "analysis_mode": llm_result.get("analysis_mode"),
        "filters": {
            "company_name": filters.get("company_name"),
            "job_location": filters.get("job_location"),
            "product_line": filters.get("product_line"),
            "keyword": filters.get("keyword"),
        },
        "raw_question": question,
        "normalized_question": normalized_question,
    }
    return validate_route_result(result)


# =========================
# Router Agent 主类
# =========================

class RouterAgent:
    """
    主控路由智能体（全 LLM）

    处理流程：
    1. 标准化问题
    2. 轻量抽取 filters
    3. 调用 LLM 输出结构化路由结果
    4. 合并系统字段并返回
    """

    def __init__(self) -> None:
        self.model_name = ROUTER_MODEL

    def _route_by_llm(self, question: str) -> Dict[str, Any]:
        """
        调用大模型完成路由判断
        """
        normalized_question = normalize_question(question)
        filters = extract_filters(normalized_question)

        prompt = build_router_prompt(normalized_question)

        llm_result = call_llm_json(
            prompt=prompt,
            system_prompt=None,
            model=self.model_name,
            temperature=ROUTER_TEMPERATURE,
            max_tokens=ROUTER_MAX_TOKENS,
            top_p=ROUTER_TOP_P,
        )

        if not isinstance(llm_result, dict):
            llm_result = {}

        return merge_route_result(
            question=question,
            normalized_question=normalized_question,
            filters=filters,
            llm_result=llm_result,
        )

    def route(self, question: str) -> Dict[str, Any]:
        """
        对外主入口

        说明：
        - 当前版本完全由 LLM 判断路由
        - 如果 LLM 调用失败，则返回一个稳定的默认结果
        """
        question = question or ""

        if not question.strip():
            return {
                "intent_type": "mixed_query",
                "need_sql": True,
                "need_rag": True,
                "need_chart": False,
                "analysis_mode": None,
                "filters": {
                    "company_name": None,
                    "job_location": None,
                    "product_line": None,
                    "keyword": None,
                },
                "raw_question": question,
                "normalized_question": "",
            }

        try:
            return self._route_by_llm(question)
        except Exception:
            # LLM 失败时返回稳定默认值，防止主流程崩掉
            normalized_question = normalize_question(question)
            filters = extract_filters(normalized_question)

            fallback_result = {
                "intent_type": "mixed_query",
                "need_sql": True,
                "need_rag": True,
                "need_chart": False,
                "analysis_mode": None,
                "filters": filters,
                "raw_question": question,
                "normalized_question": normalized_question,
            }
            return validate_route_result(fallback_result)

    # 给 graph_flow.py 统一调用入口
    def run(self, question: str) -> Dict[str, Any]:
        return self.route(question)


# =========================
# 便捷函数入口
# =========================

def route_question(question: str) -> Dict[str, Any]:
    """
    函数式便捷入口
    """
    agent = RouterAgent()
    return agent.route(question)


# =========================
# 本地测试入口
# =========================
if __name__ == "__main__":
    tests = [
        "哪些企业当前招聘岗位最多",
        "腾讯游戏在哪些城市招聘最多",
        "哪些岗位要求 Unity 经验",
        "哪些岗位职责中提到了 AI 或大模型",
        "画出各企业岗位数量对比图",
        "分析腾讯游戏近期研发重点",
        "结合岗位职责和招聘要求，分析米哈游当前重点能力投入",
        "做出地点柱状图"
    ]

    agent = RouterAgent()

    for i, q in enumerate(tests, start=1):
        print("=" * 80)
        print(f"[测试 {i}] {q}")
        result = agent.route(q)
        print(result)