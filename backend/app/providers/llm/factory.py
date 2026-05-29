"""LLM Provider 工厂：根据配置返回对应实现。"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.providers.llm.base import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    """全局单例。配置变更需重启服务。"""
    settings = get_settings()
    if settings.LLM_PROVIDER == "anthropic":
        from app.providers.llm.anthropic import AnthropicProvider
        return AnthropicProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL if "anthropic" in settings.LLM_BASE_URL else None,
            default_max_tokens=settings.LLM_MAX_TOKENS,
            default_timeout=settings.LLM_TIMEOUT_SEC,
        )
    # deepseek / openai / 任何兼容 OpenAI 协议的服务
    from app.providers.llm.deepseek import DeepSeekProvider
    return DeepSeekProvider(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        default_max_tokens=settings.LLM_MAX_TOKENS,
        default_timeout=settings.LLM_TIMEOUT_SEC,
    )
