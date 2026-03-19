# -*- coding: utf-8 -*-
"""
统一大模型调用封装

作用：
1. 统一调用大模型
2. 统一处理模型参数
3. 统一处理异常
4. 提供文本输出接口
5. 提供 JSON 输出接口

说明：
- 当前按 OpenAI 兼容接口方式封装
- 你后续只需要在这里改 base_url / api_key / client 初始化逻辑
- 上层 Agent 不需要关心底层 SDK 细节
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from openai import OpenAI

from app.core.model_config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
)


class LLMClient:
    """
    大模型统一客户端

    环境变量要求：
    - LLM_API_KEY
    - LLM_BASE_URL

    示例：
    set LLM_API_KEY=你的key
    set LLM_BASE_URL=你的兼容接口地址
    """

    def __init__(self):
        api_key = os.getenv("LLM_API_KEY", "").strip()
        base_url = os.getenv("LLM_BASE_URL", "").strip()

        if not api_key:
            raise ValueError("环境变量 LLM_API_KEY 未配置。")

        if not base_url:
            raise ValueError("环境变量 LLM_BASE_URL 未配置。")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        top_p: float = DEFAULT_TOP_P,
    ) -> str:
        """
        基础文本调用接口

        参数：
        - prompt: 用户提示词
        - system_prompt: 系统提示词
        - model: 模型名称
        - temperature: 采样温度
        - max_tokens: 最大输出 token
        - top_p: nucleus sampling 参数

        返回：
        - 模型文本输出
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

            content = response.choices[0].message.content
            return (content or "").strip()

        except Exception as e:
            raise RuntimeError(f"LLM 文本调用失败: {e}") from e

    def call_llm_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.0,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        top_p: float = DEFAULT_TOP_P,
    ) -> Dict[str, Any]:
        """
        JSON 输出接口

        适合场景：
        - Router Agent
        - SQL Agent
        - 其他需要结构化输出的 Agent

        返回：
        - dict
        """
        json_system_prompt = (
            (system_prompt or "")
            + "\n\n请严格只输出合法 JSON，不要输出解释、注释、Markdown 代码块。"
        ).strip()

        raw_text = self.call_llm(
            prompt=prompt,
            system_prompt=json_system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"LLM JSON 解析失败: {e}\n原始输出: {raw_text}"
            ) from e


# =========================
# 模块级快捷函数
# 便于上层直接导入使用
# =========================

def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    top_p: float = DEFAULT_TOP_P,
) -> str:
    """
    模块级文本调用快捷函数
    """
    client = LLMClient()
    return client.call_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )


def call_llm_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    top_p: float = DEFAULT_TOP_P,
) -> Dict[str, Any]:
    """
    模块级 JSON 调用快捷函数
    """
    client = LLMClient()
    return client.call_llm_json(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )


# =========================
# 本地测试入口
# =========================
if __name__ == "__main__":
    test_prompt = "请用一句话介绍什么是智能体。"

    try:
        result = call_llm(test_prompt)
        print("=== 文本输出 ===")
        print(result)
    except Exception as e:
        print("测试失败：", e)