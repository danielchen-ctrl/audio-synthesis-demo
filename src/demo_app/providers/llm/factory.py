"""LLM Provider 工厂。

从 runtime.yaml 的 llm 节读取配置，返回对应 Provider 实例；
llm.provider 为空时返回 None（表示使用 bundle）。

api_key 优先读环境变量 LLM_API_KEY，其次读 yaml 中的 api_key 字段。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import LLMProvider

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[4]


def get_llm_provider(cfg: dict | None = None) -> LLMProvider | None:
    """工厂函数。

    Args:
        cfg: 已加载的 runtime.yaml 字典。None 时自动加载。

    Returns:
        LLMProvider 实例，或 None（未配置 / provider 为空）。
    """
    if cfg is None:
        try:
            import yaml
            cfg_path = _ROOT / "config" / "runtime.yaml"
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("[llm.factory] 无法加载 runtime.yaml: %s", exc)
            return None

    llm_cfg = cfg.get("llm") or {}
    provider_name = (llm_cfg.get("provider") or "").strip().lower()
    if not provider_name:
        return None   # 未配置，使用 bundle

    # api_key：环境变量优先
    api_key = os.environ.get("LLM_API_KEY") or str(llm_cfg.get("api_key") or "")
    if not api_key:
        logger.warning("[llm.factory] llm.provider=%s 但 api_key 未设置，跳过云 LLM", provider_name)
        return None

    model = str(llm_cfg.get("model") or "")
    timeout_sec = int(llm_cfg.get("timeout_sec") or 60)
    max_tokens = int(llm_cfg.get("max_tokens") or 4096)
    base_url = str(llm_cfg.get("base_url") or "")

    if provider_name == "anthropic":
        from .anthropic_llm import AnthropicProvider
        if not model:
            model = "claude-sonnet-4-5"
        logger.info("[llm.factory] 使用 Anthropic Provider, model=%s", model)
        return AnthropicProvider(
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
        )

    # deepseek / openai / 其他兼容网关 — 统一走 OpenAI-compat
    from .openai_compat import OpenAICompatProvider

    if provider_name == "deepseek":
        if not base_url:
            base_url = "https://api.deepseek.com/v1"
        if not model:
            model = "deepseek-chat"
    elif provider_name == "openai":
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not model:
            model = "gpt-4o"
    else:
        # 自定义网关：base_url 和 model 由用户填写
        if not base_url:
            logger.warning("[llm.factory] provider=%s 但 base_url 未设置", provider_name)
            return None
        if not model:
            logger.warning("[llm.factory] provider=%s 但 model 未设置", provider_name)
            return None

    logger.info("[llm.factory] 使用 OpenAI-compat Provider, provider=%s model=%s base_url=%s",
                provider_name, model, base_url)
    return OpenAICompatProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
    )
