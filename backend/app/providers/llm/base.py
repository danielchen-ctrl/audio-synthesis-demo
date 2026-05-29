"""LLM Provider 抽象接口。

切换不同 LLM（DeepSeek / OpenAI / Claude / 公司网关）时，只要实现这个 ABC 即可。
业务代码只依赖 LLMProvider，不依赖具体厂商。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """所有 LLM 厂商都实现这个接口。"""

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        timeout: int | None = None,
    ) -> LLMResult:
        """同步调用，返回完整回复。Celery worker 用同步即可。"""
        raise NotImplementedError
