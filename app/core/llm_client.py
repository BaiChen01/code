# -*- coding: utf-8 -*-
"""Low-level OpenAI-compatible client wrappers."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from openai import OpenAI

from app.core.config import get_settings
from app.core.model_config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
)


class LLMClient:
    """Thin wrapper around an OpenAI-compatible chat completion API."""

    def __init__(self) -> None:
        # Read LLM secrets directly from the current process environment first.
        # This avoids stale values when config caching was built before env vars
        # were updated in the same shell session.
        env_api_key = os.getenv("LLM_API_KEY", "").strip()
        env_base_url = os.getenv("LLM_BASE_URL", "").strip()
        settings = get_settings()

        api_key = env_api_key or settings.llm_api_key
        base_url = env_base_url or settings.llm_base_url

        if not api_key:
            raise ValueError("Environment variable LLM_API_KEY is not configured.")
        if not base_url:
            raise ValueError("Environment variable LLM_BASE_URL is not configured.")

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
        except Exception as exc:  # pragma: no cover - network/runtime dependency
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content or ""
        return content.strip()

    def call_llm_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = DEFAULT_CHAT_MODEL,
        temperature: float = 0.0,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        top_p: float = DEFAULT_TOP_P,
    ) -> Dict[str, Any]:
        json_system_prompt = (
            ((system_prompt or "").strip() + "\n\n" if system_prompt else "")
            + "Return valid JSON only. Do not wrap the output in markdown."
        )
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
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse LLM JSON output: {raw_text}") from exc


def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    top_p: float = DEFAULT_TOP_P,
) -> str:
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
    client = LLMClient()
    return client.call_llm_json(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
