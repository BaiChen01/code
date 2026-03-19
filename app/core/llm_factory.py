# -*- coding: utf-8 -*-
"""LangChain-style prompt rendering over the existing LLM client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.llm_client import LLMClient
from app.core.model_config import (
    DEFAULT_CHAT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
)


def _render_chat_prompt(
    template: ChatPromptTemplate,
    variables: Mapping[str, Any],
) -> tuple[Optional[str], str]:
    prompt_value = template.invoke(dict(variables))
    system_chunks = []
    user_chunks = []

    for message in prompt_value.to_messages():
        content = str(message.content).strip()
        if not content:
            continue
        if message.type == "system":
            system_chunks.append(content)
        else:
            user_chunks.append(content)

    system_prompt = "\n\n".join(system_chunks) or None
    prompt = "\n\n".join(user_chunks).strip()
    return system_prompt, prompt


@dataclass
class LangChainLLM:
    model: str = DEFAULT_CHAT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    top_p: float = DEFAULT_TOP_P

    def __post_init__(self) -> None:
        self.client = None

    def invoke_text(
        self,
        template: ChatPromptTemplate,
        variables: Mapping[str, Any],
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        rendered_system, prompt = _render_chat_prompt(template, variables)
        merged_system = "\n\n".join(
            chunk for chunk in [system_prompt, rendered_system] if chunk
        ) or None
        if self.client is None:
            self.client = LLMClient()
        return self.client.call_llm(
            prompt=prompt,
            system_prompt=merged_system,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
        )

    def invoke_json(
        self,
        template: ChatPromptTemplate,
        variables: Mapping[str, Any],
        *,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        rendered_system, prompt = _render_chat_prompt(template, variables)
        merged_system = "\n\n".join(
            chunk for chunk in [system_prompt, rendered_system] if chunk
        ) or None
        if self.client is None:
            self.client = LLMClient()
        return self.client.call_llm_json(
            prompt=prompt,
            system_prompt=merged_system,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
        )


def get_llm(
    *,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    top_p: float = DEFAULT_TOP_P,
) -> LangChainLLM:
    return LangChainLLM(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
