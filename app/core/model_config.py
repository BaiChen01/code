# -*- coding: utf-8 -*-
"""
模型配置文件

作用：
1. 统一声明当前项目使用的模型
2. 统一维护默认推理参数
3. 为不同 Agent 提供独立配置入口

说明：
- 当前阶段全部使用 qwen3-max
- 后续如果要改成：
    Router 用轻量模型
    Analysis 用强模型
  只需要改这里
"""

from __future__ import annotations


# =========================
# 默认模型配置
# =========================

DEFAULT_CHAT_MODEL = "qwen3-max"


# =========================
# 各 Agent 模型配置
# 当前先统一使用 qwen3-max
# 后续可单独调整
# =========================

ROUTER_MODEL = "qwen3-max"
SQL_MODEL = "qwen3-max"
ANALYSIS_MODEL = "qwen3-max"
RAG_SUMMARY_MODEL = "qwen3-max"


# =========================
# 默认推理参数
# 这些参数作为全局默认值
# =========================

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TOP_P = 0.9


# =========================
# 各 Agent 默认参数
# 可以按需细分
# =========================

ROUTER_TEMPERATURE = 0.0
ROUTER_MAX_TOKENS = 500
ROUTER_TOP_P = 0.9

SQL_TEMPERATURE = 0.0
SQL_MAX_TOKENS = 800
SQL_TOP_P = 0.9

ANALYSIS_TEMPERATURE = 0.3
ANALYSIS_MAX_TOKENS = 2500
ANALYSIS_TOP_P = 0.9

RAG_SUMMARY_TEMPERATURE = 0.2
RAG_SUMMARY_MAX_TOKENS = 1500
RAG_SUMMARY_TOP_P = 0.9