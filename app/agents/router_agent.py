# -*- coding: utf-8 -*-
"""Router agent for intent routing and retrieval scope selection."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from app.core.llm_factory import get_llm
from app.core.model_config import (
    ROUTER_MAX_TOKENS,
    ROUTER_MODEL,
    ROUTER_TEMPERATURE,
    ROUTER_TOP_P,
)
from app.prompts.router_prompt import get_router_prompt_template


COMPANY_ALIASES = {
    "腾讯游戏": ["腾讯游戏", "腾讯", "Tencent Games"],
    "网易游戏": ["网易游戏", "网易"],
    "米哈游": ["米哈游", "miHoYo", "HoYoverse"],
}

CITY_KEYWORDS = ["上海", "北京", "广州", "深圳", "杭州", "成都", "苏州", "武汉"]
JOB_HINT_KEYWORDS = [
    "岗位",
    "职位",
    "招聘",
    "任职要求",
    "岗位职责",
    "技能",
    "经验",
    "jd",
    "要求",
    "职责",
]
NEWS_HINT_KEYWORDS = [
    "资讯",
    "新闻",
    "报道",
    "动态",
    "消息",
    "媒体",
    "游戏日报",
    "文章",
]
SQL_HINT_KEYWORDS = [
    "多少",
    "数量",
    "分布",
    "统计",
    "排行",
    "排名",
    "列表",
    "top",
    "对比",
    "比较",
]
CHART_HINT_KEYWORDS = ["图", "图表", "柱状图", "饼图", "折线图", "可视化", "词云"]
ANALYSIS_HINT_KEYWORDS = ["分析", "布局", "趋势", "研判", "判断", "总结", "洞察"]
SKILL_HINT_KEYWORDS = ["技能", "能力", "经验", "要求", "职责", "unity", "ue", "ai"]

VALID_INTENT_TYPES = {
    "structured_query",
    "semantic_retrieval",
    "visualization_request",
    "intelligence_analysis",
    "mixed_query",
}
VALID_RETRIEVAL_SCOPES = {"none", "job", "news", "both"}
DUAL_RAG_HINTS = [
    "结合招聘和资讯",
    "结合岗位和资讯",
    "结合招聘和新闻",
    "结合岗位和新闻",
]


def normalize_question(question: str) -> str:
    question = (question or "").strip()
    return re.sub(r"\s+", " ", question)


def has_any_keyword(question: str, keywords: list[str]) -> bool:
    lowered = question.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def extract_company(question: str) -> Optional[str]:
    lowered = question.lower()
    for standard_name, aliases in COMPANY_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            return standard_name
    return None


def extract_city(question: str) -> Optional[str]:
    for city in CITY_KEYWORDS:
        if city in question:
            return city
    return None


def extract_keyword(question: str) -> Optional[str]:
    lowered = question.lower()
    for keyword in SKILL_HINT_KEYWORDS:
        if keyword in lowered:
            return keyword.upper() if keyword in {"ai", "ue"} else keyword
    return None


def extract_filters(question: str) -> Dict[str, Optional[str]]:
    return {
        "company_name": extract_company(question),
        "job_location": extract_city(question),
        "product_line": None,
        "keyword": extract_keyword(question),
    }


def infer_analysis_mode(question: str, has_news: bool, has_job: bool) -> Optional[str]:
    if "研发" in question or "布局" in question:
        return "company_rd_layout"
    if has_news and ("趋势" in question or "动态" in question):
        return "news_trend_analysis"
    if "对比" in question or "比较" in question:
        return "comparative_analysis"
    if has_job and has_any_keyword(question, SKILL_HINT_KEYWORDS):
        return "skill_demand_analysis"
    if has_any_keyword(question, ANALYSIS_HINT_KEYWORDS):
        return "general_analysis"
    return None


def classify_by_rules(
    question: str,
    filters: Dict[str, Optional[str]],
    need_chart_requested: bool,
) -> Dict[str, Any]:
    has_job = has_any_keyword(question, JOB_HINT_KEYWORDS)
    has_news = has_any_keyword(question, NEWS_HINT_KEYWORDS)
    has_chart = need_chart_requested or has_any_keyword(question, CHART_HINT_KEYWORDS)
    has_analysis = has_any_keyword(question, ANALYSIS_HINT_KEYWORDS)
    has_sql = has_any_keyword(question, SQL_HINT_KEYWORDS)
    explicit_dual_rag = any(phrase in question for phrase in DUAL_RAG_HINTS)

    if explicit_dual_rag:
        retrieval_scope = "both"
    elif has_job and has_news:
        retrieval_scope = "both"
    elif has_news:
        retrieval_scope = "news"
    elif has_job or filters.get("keyword"):
        retrieval_scope = "job"
    else:
        retrieval_scope = "none"

    analysis_mode = infer_analysis_mode(question, has_news=has_news, has_job=has_job)

    if has_chart:
        intent_type = "visualization_request"
        need_sql = True
        need_rag = explicit_dual_rag or has_analysis
        if not need_rag:
            retrieval_scope = "none"
    elif has_analysis and retrieval_scope != "none":
        intent_type = "mixed_query" if (
            has_sql or retrieval_scope in {"both", "job"}
        ) else "intelligence_analysis"
        need_sql = has_sql or retrieval_scope in {"job", "both"} or bool(
            filters.get("company_name") or filters.get("job_location")
        )
        need_rag = True
    elif has_analysis:
        intent_type = "intelligence_analysis"
        need_sql = True
        need_rag = retrieval_scope != "none"
    elif retrieval_scope != "none":
        intent_type = "semantic_retrieval"
        need_sql = False
        need_rag = True
    else:
        intent_type = "structured_query"
        need_sql = True
        need_rag = False

    return {
        "intent_type": intent_type,
        "need_sql": need_sql,
        "need_rag": need_rag,
        "need_chart": has_chart,
        "analysis_mode": analysis_mode,
        "retrieval_scope": retrieval_scope if need_rag else "none",
    }


def validate_route_result(route_result: Dict[str, Any]) -> Dict[str, Any]:
    route_result["intent_type"] = (
        route_result.get("intent_type")
        if route_result.get("intent_type") in VALID_INTENT_TYPES
        else "mixed_query"
    )
    route_result["retrieval_scope"] = (
        route_result.get("retrieval_scope")
        if route_result.get("retrieval_scope") in VALID_RETRIEVAL_SCOPES
        else "none"
    )
    route_result["need_sql"] = bool(route_result.get("need_sql", False))
    route_result["need_rag"] = bool(route_result.get("need_rag", False))
    route_result["need_chart"] = bool(route_result.get("need_chart", False))
    route_result["analysis_mode"] = route_result.get("analysis_mode")
    return route_result


class RouterAgent:
    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.llm = get_llm(
            model=ROUTER_MODEL,
            temperature=ROUTER_TEMPERATURE,
            max_tokens=ROUTER_MAX_TOKENS,
            top_p=ROUTER_TOP_P,
        )
        self.prompt_template = get_router_prompt_template()

    def _route_by_llm(self, *, question: str) -> Dict[str, Any]:
        return self.llm.invoke_json(self.prompt_template, {"question": question})

    def route(self, question: str, *, need_chart_requested: bool = False) -> Dict[str, Any]:
        normalized_question = normalize_question(question)
        if not normalized_question:
            return {
                "intent_type": "structured_query",
                "need_sql": False,
                "need_rag": False,
                "need_chart": False,
                "analysis_mode": None,
                "retrieval_scope": "none",
                "raw_question": question,
                "normalized_question": normalized_question,
                "filters": {
                    "company_name": None,
                    "job_location": None,
                    "product_line": None,
                    "keyword": None,
                },
            }

        filters = extract_filters(normalized_question)
        rule_result = classify_by_rules(
            normalized_question,
            filters,
            need_chart_requested=need_chart_requested,
        )
        result = {
            **rule_result,
            "raw_question": question,
            "normalized_question": normalized_question,
            "filters": filters,
        }

        if not self.use_llm:
            return validate_route_result(result)

        try:
            llm_result = self._route_by_llm(question=normalized_question)
        except Exception:
            return validate_route_result(result)

        merged = {
            **result,
            "intent_type": llm_result.get("intent_type", result["intent_type"]),
            "need_sql": llm_result.get("need_sql", result["need_sql"]),
            "need_rag": llm_result.get("need_rag", result["need_rag"]),
            "need_chart": need_chart_requested or llm_result.get(
                "need_chart", result["need_chart"]
            ),
            "analysis_mode": llm_result.get("analysis_mode", result["analysis_mode"]),
            "retrieval_scope": llm_result.get(
                "retrieval_scope", result["retrieval_scope"]
            ),
        }
        if not merged["need_rag"]:
            merged["retrieval_scope"] = "none"
        return validate_route_result(merged)

    def run(self, question: str, *, need_chart_requested: bool = False) -> Dict[str, Any]:
        return self.route(question, need_chart_requested=need_chart_requested)


def route_question(question: str, *, need_chart_requested: bool = False) -> Dict[str, Any]:
    return RouterAgent().run(question, need_chart_requested=need_chart_requested)
