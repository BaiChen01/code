# -*- coding: utf-8 -*-
"""
主控路由智能体（Router Agent）

职责：
1. 识别用户问题意图
2. 判断是否需要 SQL / RAG / Chart / Analysis
3. 抽取基础过滤条件
4. 输出统一、稳定的路由结果，供 LangGraph 工作流使用

设计原则：
- 第一版：规则优先，稳定、可调试
- 第二版：LLM 兜底或细化
- filters 以规则抽取为主，不完全交给 LLM
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

# 这里假设你已经有 app/prompts/router_prompt.py
# 如果暂时还没有，可以先把 build_router_prompt 挪到本文件里
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
    "Unity", "UE", "UE4", "UE5", "AI", "AIGC", "大模型",
    "图形渲染", "工具链", "客户端", "服务端"
]

CHART_KEYWORDS = [
    "图出", "图表", "柱状图", "饼图", "折线图",
    "分布图", "可视化", "词云"
]

ANALYSIS_KEYWORDS = [
    "分析", "研判", "布局", "重点", "侧重点", "趋势", "投入", "对比"
]

RAG_HINT_KEYWORDS = [
    "要求", "职责", "能力", "技能", "经验", "提到", "强调", "关键词"
]

SQL_HINT_KEYWORDS = [
    "多少", "最多", "分布", "哪些企业", "哪些城市", "岗位数", "数量", "列表", "有哪些岗位"
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
    轻量标准化用户问题：
    1. 去首尾空格
    2. 合并多余空白字符
    3. 不改变原始语义
    """
    if not question:
        return ""

    question = question.strip()
    question = re.sub(r"\s+", " ", question)
    return question


def has_any_keyword(question: str, keywords: list[str]) -> bool:
    """
    判断问题中是否命中任意关键词
    """
    lower_q = question.lower()
    return any(k.lower() in lower_q for k in keywords)


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
    第一版只取第一个命中的关键词
    """
    lower_q = question.lower()

    for kw in TECH_KEYWORDS:
        if kw.lower() in lower_q:
            return kw
    return None


def extract_filters(question: str) -> Dict[str, Optional[str]]:
    """
    从问题中提取结构化过滤条件

    当前支持：
    - company_name
    - job_location
    - product_line（第一版暂不做复杂抽取）
    - keyword
    """
    return {
        "company_name": extract_company(question),
        "job_location": extract_city(question),
        "product_line": None,
        "keyword": extract_keyword(question),
    }


def infer_analysis_mode(question: str, filters: Dict[str, Optional[str]]) -> Optional[str]:
    """
    根据问题内容推断分析模式，供 Analysis Agent 使用
    """
    if "研发" in question and ("布局" in question or "重点" in question):
        return "company_rd_layout"

    if filters.get("job_location") is not None and ("布局" in question or "分布" in question):
        return "city_layout"

    if "产品线" in question or "项目方向" in question:
        return "product_line_focus"

    if has_any_keyword(question, ["能力", "技能", "要求", "职责", "经验"]):
        return "skill_focus"

    if has_any_keyword(question, ANALYSIS_KEYWORDS):
        return "general_intel_analysis"

    return None


def classify_by_rules(question: str, filters: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """
    使用规则进行第一层分类

    路由规则：
    - 图表请求优先
    - 分析 + 文本 + 结构化 => mixed_query
    - 分析类 => intelligence_analysis
    - 文本检索类 => semantic_retrieval
    - 结构化查询类 => structured_query
    - 否则兜底 mixed_query
    """
    has_chart = has_any_keyword(question, CHART_KEYWORDS)
    has_analysis = has_any_keyword(question, ANALYSIS_KEYWORDS)
    has_rag_hint = has_any_keyword(question, RAG_HINT_KEYWORDS)
    has_sql_hint = has_any_keyword(question, SQL_HINT_KEYWORDS)

    analysis_mode = infer_analysis_mode(question, filters)

    # 1. 图表请求优先
    if has_chart:
        return {
            "intent_type": "visualization_request",
            "need_sql": True,
            "need_rag": False,
            "need_chart": True,
            "analysis_mode": analysis_mode,
        }

    # 2. 明确综合分析，同时需要结构化和文本证据
    if has_analysis and has_rag_hint and (has_sql_hint or filters.get("company_name") or filters.get("job_location")):
        return {
            "intent_type": "mixed_query",
            "need_sql": True,
            "need_rag": True,
            "need_chart": False,
            "analysis_mode": analysis_mode or "general_intel_analysis",
        }

    # 3. 分析型问题
    if has_analysis:
        return {
            "intent_type": "intelligence_analysis",
            "need_sql": True,
            "need_rag": True,
            "need_chart": False,
            "analysis_mode": analysis_mode or "general_intel_analysis",
        }

    # 4. 纯语义检索问题
    if has_rag_hint and not has_sql_hint:
        return {
            "intent_type": "semantic_retrieval",
            "need_sql": False,
            "need_rag": True,
            "need_chart": False,
            "analysis_mode": None,
        }

    # 5. 结构化问题
    if has_sql_hint or filters.get("company_name") or filters.get("job_location"):
        return {
            "intent_type": "structured_query",
            "need_sql": True,
            "need_rag": False,
            "need_chart": False,
            "analysis_mode": None,
        }

    # 6. 兜底
    return {
        "intent_type": "mixed_query",
        "need_sql": True,
        "need_rag": True,
        "need_chart": False,
        "analysis_mode": analysis_mode,
    }


def validate_route_result(route_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    对规则或 LLM 输出做字段校验和兜底
    确保 graph_flow.py 读取时结构稳定
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

    return route_result


def merge_route_result(
    question: str,
    normalized_question: str,
    filters: Dict[str, Optional[str]],
    base_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    合并标准字段，构造成统一输出结构
    """
    result = {
        "intent_type": base_result.get("intent_type"),
        "need_sql": base_result.get("need_sql", False),
        "need_rag": base_result.get("need_rag", False),
        "need_chart": base_result.get("need_chart", False),
        "analysis_mode": base_result.get("analysis_mode"),
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
    主控路由智能体

    处理流程：
    1. 标准化问题
    2. 规则抽取 filters
    3. 规则路由
    4. 可选调用 LLM 做兜底或细化
    """

    def __init__(self, use_llm: bool = True, use_rule_first: bool = True) -> None:
        self.use_llm = use_llm
        self.use_rule_first = use_rule_first
        self.model_name = ROUTER_MODEL

    def _route_by_rules(self, question: str) -> Dict[str, Any]:
        """
        规则路由
        """
        normalized_question = normalize_question(question)
        filters = extract_filters(normalized_question)
        rule_result = classify_by_rules(normalized_question, filters)
        return merge_route_result(question, normalized_question, filters, rule_result)

    def _route_by_llm(self, question: str) -> Dict[str, Any]:
        """
        LLM 路由

        注意：
        - filters 仍然以规则抽取为主
        - LLM 主要负责 intent_type / need_sql / need_rag / need_chart / analysis_mode
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

        return merge_route_result(question, normalized_question, filters, llm_result)

    def route(self, question: str) -> Dict[str, Any]:
        """
        对外主入口

        第一版推荐策略：
        - 先规则判断
        - 再用 LLM 细化或兜底
        - 如果 LLM 失败，则安全回退到规则结果
        """
        question = question or ""

        # 空问题兜底
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

        # 规则结果始终先生成
        rule_result = self._route_by_rules(question)

        # 如果不启用 LLM，直接返回规则结果
        if not self.use_llm:
            return rule_result

        try:
            llm_result = self._route_by_llm(question)

            # 合并策略：
            # - filters 仍以规则抽取为准
            # - 核心路由字段允许 LLM 覆盖
            final_result = {
                **rule_result,
                "intent_type": llm_result.get("intent_type", rule_result["intent_type"]),
                "need_sql": llm_result.get("need_sql", rule_result["need_sql"]),
                "need_rag": llm_result.get("need_rag", rule_result["need_rag"]),
                "need_chart": llm_result.get("need_chart", rule_result["need_chart"]),
                "analysis_mode": llm_result.get("analysis_mode", rule_result["analysis_mode"]),
                "filters": rule_result["filters"],
            }

            return validate_route_result(final_result)

        except Exception:
            # LLM 失败时，回退到规则结果
            return rule_result

    # 给 graph_flow.py 一个统一调用入口
    def run(self, question: str) -> Dict[str, Any]:
        return self.route(question)


# =========================
# 便捷函数入口
# =========================

def route_question(question: str, use_llm: bool = True) -> Dict[str, Any]:
    """
    函数式便捷入口
    """
    agent = RouterAgent(use_llm=use_llm, use_rule_first=True)
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
        "做出招聘柱状"
    ]

    agent = RouterAgent(use_llm=False)

    for i, q in enumerate(tests, start=1):
        print("=" * 80)
        print(f"[测试 {i}] {q}")
        result = agent.route(q)
        print(result)