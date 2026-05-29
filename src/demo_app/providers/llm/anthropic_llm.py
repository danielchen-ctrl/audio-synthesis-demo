"""Anthropic Messages API Provider（Claude 系列）。

使用 httpx 直接调用，不依赖 anthropic SDK，减少依赖。
  model 示例：claude-opus-4-5, claude-sonnet-4-5, claude-haiku-3-5
"""
from __future__ import annotations

import logging

import httpx

from .base import LLMMessage, LLMProvider, LLMResult

logger = logging.getLogger(__name__)

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        timeout_sec: int = 60,
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_sec
        self._max_tokens = max_tokens

    def complete(self, messages: list[LLMMessage]) -> LLMResult:
        # Anthropic API 将 system 消息单独提取
        system_content = ""
        user_messages = []
        for m in messages:
            if m.role == "system":
                system_content = m.content
            else:
                user_messages.append({"role": m.role, "content": m.content})

        body: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": user_messages,
        }
        if system_content:
            body["system"] = system_content

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(_ANTHROPIC_API_URL, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            model=data.get("model", self._model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=data,
        )
