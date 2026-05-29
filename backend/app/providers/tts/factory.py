"""TTS Provider 工厂。"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.providers.tts.base import TTSProvider, VoiceSpec
from app.providers.tts.cosyvoice import CosyVoiceProvider


# 启动时如果 CosyVoice 不通，至少先有一份默认目录可用
_FALLBACK_VOICES: list[VoiceSpec] = [
    VoiceSpec(voice_id="36d3429a3c98", name="maryzhang", language="zh", gender="female"),
    VoiceSpec(voice_id="c3e9f75ae993", name="willwu", language="en", gender="male"),
]


@lru_cache
def get_tts_provider() -> TTSProvider:
    settings = get_settings()
    return CosyVoiceProvider(
        base_url=settings.COSYVOICE_BASE_URL,
        model=settings.COSYVOICE_MODEL,
        timeout_sec=settings.COSYVOICE_TIMEOUT_SEC,
        max_retries=settings.COSYVOICE_MAX_RETRIES,
    )


def get_fallback_voices() -> list[VoiceSpec]:
    return list(_FALLBACK_VOICES)
