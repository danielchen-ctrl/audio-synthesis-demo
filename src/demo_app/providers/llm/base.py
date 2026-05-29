"""LLM Provider 抽象层。

数据模型和 ABC，与 v2 保持兼容，使 factory / 调用方代码不依赖具体实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str      # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[LLMMessage]) -> LLMResult:
        """同步调用，返回 LLMResult。调用方在线程池里执行（run_in_executor）。"""
        raise NotImplementedError
