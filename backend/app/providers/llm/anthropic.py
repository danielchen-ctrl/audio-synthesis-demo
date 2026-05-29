"""Anthropic Claude Provider 实现。"""
from __future__ import annotations

from anthropic import Anthropic

from app.providers.llm.base import LLMMessage, LLMProvider, LLMResult


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        default_max_tokens: int = 4096,
        default_timeout: int = 60,
    ) -> None:
        kwargs = {"api_key": api_key, "timeout": default_timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = Anthropic(**kwargs)
        self._model = model
        self._default_max_tokens = default_max_tokens

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        timeout: int | None = None,
    ) -> LLMResult:
        # Anthropic 的 system 单独传，不在 messages 数组里
        system_prompt = "\n".join(m.content for m in messages if m.role == "system")
        user_assistant = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        resp = self._client.messages.create(
            model=self._model,
            system=system_prompt or None,
            messages=user_assistant,
            max_tokens=max_tokens or self._default_max_tokens,
            temperature=temperature,
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return LLMResult(
            text=text,
            model=resp.model,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
            total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            raw={"stop_reason": resp.stop_reason},
        )
