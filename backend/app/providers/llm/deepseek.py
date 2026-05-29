"""DeepSeek Provider 实现。

DeepSeek API 兼容 OpenAI 协议，复用 openai SDK 即可。
切换到其他兼容 OpenAI 协议的服务（如公司内部 LLM 网关）同样适用：
只需改 LLM_BASE_URL 和 LLM_MODEL 环境变量。
"""
from __future__ import annotations

from openai import OpenAI

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResult


class DeepSeekProvider(LLMProvider):
    """通过 OpenAI 兼容协议调用 DeepSeek。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        default_max_tokens: int = 4096,
        default_timeout: int = 60,
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=default_timeout)
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._default_timeout = default_timeout

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        timeout: int | None = None,
    ) -> LLMResult:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature,
            timeout=timeout or self._default_timeout,
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResult(
            text=choice.message.content or "",
            model=resp.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            raw={"finish_reason": choice.finish_reason},
        )


# OpenAI 也走同一个实现（API 完全兼容）
class OpenAIProvider(DeepSeekProvider):
    """OpenAI / 任何兼容 OpenAI 协议的服务都走这个。"""
