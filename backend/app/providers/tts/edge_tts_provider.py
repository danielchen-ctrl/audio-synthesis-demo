"""Edge TTS Provider — 作为 CosyVoice 合成失败时的透明降级后备。

设计原则：
- 对外接口与 CosyVoice Provider 完全一致（TTSProvider ABC）
- Celery worker 是同步线程上下文，没有运行中的事件循环，
  必须用 asyncio.new_event_loop() 显式创建，不能用 get_running_loop()
- 通过 default_voice_for() 暴露语言→音色映射，调用方不直接访问内部 dict
"""
from __future__ import annotations

import asyncio
import io
import logging

from app.providers.tts.base import SynthesisRequest, SynthesisResult, TTSProvider, VoiceSpec

logger = logging.getLogger(__name__)

# 12 种语言的默认 Edge TTS 音色（对应 meta.py list_languages）
_EDGE_VOICE_MAP: dict[str, str] = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "it": "it-IT-ElsaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ar": "ar-SA-ZariyahNeural",
    "id": "id-ID-GadisNeural",
}


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS Provider。仅用于降级，不在生成弹窗中对用户展示。"""

    def default_voice_for(self, language: str) -> str:
        """供调用方查询默认音色，避免外部直接引用 _EDGE_VOICE_MAP。"""
        return _EDGE_VOICE_MAP.get(language, "zh-CN-XiaoxiaoNeural")

    def synthesize(self, req: SynthesisRequest) -> SynthesisResult:
        """同步合成接口。内部创建独立事件循环运行异步代码。"""
        # Celery worker 无事件循环，必须显式新建；不能用 get_running_loop()
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_synthesize(req))
        finally:
            loop.close()

    async def _async_synthesize(self, req: SynthesisRequest) -> SynthesisResult:
        import edge_tts  # 懒导入，避免未安装时影响其他模块
        voice = req.voice_id or self.default_voice_for(req.language)
        communicate = edge_tts.Communicate(req.text, voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        audio = buf.getvalue()
        if not audio:
            return SynthesisResult(
                success=False,
                error_code="empty_audio",
                error_message="edge_tts 返回空音频",
            )
        return SynthesisResult(success=True, audio_bytes=audio, audio_format="mp3")

    def list_voices(self, language: str | None = None) -> list[VoiceSpec]:
        """edge_tts 不需要预注册，返回空列表。"""
        return []
