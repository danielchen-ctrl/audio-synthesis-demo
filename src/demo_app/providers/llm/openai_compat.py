"""OpenAI 兼容接口 Provider（DeepSeek / OpenAI / 其他兼容网关）。

统一用一个类实现：base_url 不同即可切换服务商。
  - DeepSeek:  base_url=https://api.deepseek.com/v1  model=deepseek-chat
  - OpenAI:    base_url=https://api.openai.com/v1    model=gpt-4o
  - 内部网关:  base_url=https://llm-gw.company.com/v1
"""
from __future__ import annotations

import logging

import httpx

from .base import LLMMessage, LLMProvider, LLMResult

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: int = 60,
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_sec
        self._max_tokens = max_tokens

    def complete(self, messages: list[LLMMessage]) -> LLMResult:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._max_tokens,
            "temperature": 0.7,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            model=data.get("model", self._model),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )
