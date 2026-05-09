"""
demo_app/real_human_tts.py
==========================
RealHumanProvider — CosyVoice TTS API 实现。

使用 OpenAI-compatible 端点（经实测可用，2026-05-10）：
  POST /v1/audio/speech   JSON body → 直接返回 WAV 音频字节（同步）

废弃的端点（zero_shot 模式要求上传 prompt_wav，不支持仅传 spk_id）：
  POST /api/tts/async     → 失败：Invalid file: None
  GET  /api/task/{id}     → 轮询（已废弃）
  GET  /api/download/{f}  → 下载（已废弃）

/v1/audio/speech 请求格式（JSON）：
  {
    "model":           "cosyvoice-v3",  // 可从 GET /v1/models 获取
    "input":           <text>,
    "voice":           <voice_id>,      // 注册音色的 ID（或名称）
    "response_format": "wav",
    "speed":           1.0
  }
响应：直接返回 WAV 音频字节（Content-Type: audio/wav 或 audio/x-wav）。

当前可用音色（GET /v1/voices/custom，2026-05-10 确认）：
  中文: maryzhang  voice_id=36d3429a3c98
  英文: willwu     voice_id=c3e9f75ae993

HTTP 调用通过 requests + asyncio.run_in_executor 在线程池执行，
避免阻塞 Tornado 事件循环，无需引入 aiohttp 额外依赖。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests as _requests

from demo_app.tts_provider import (
    ProviderCapabilities,
    SynthesisRequest,
    SynthesisResult,
    TTSProvider,
    VoiceSpec,
)

logger = logging.getLogger(__name__)

# ── CosyVoice 能力声明 ──────────────────────────────────────────────────────────
COSYVOICE_CAPABILITIES = ProviderCapabilities(
    tier="B",
    supports_ssml=False,
    supports_multi_speaker=False,
    supports_word_timestamps=False,
    supports_pause_control=True,      # speed 字段
    max_chars_per_request=500,
    output_formats=["wav"],
    async_mode=False,                 # /v1/audio/speech 是同步接口
)

_DEFAULT_TIMEOUT_SEC = 60
_DEFAULT_MODEL       = "cosyvoice-v3"


class RealHumanProvider(TTSProvider):
    """
    CosyVoice TTS Provider。
    使用 /v1/audio/speech（OpenAI-compatible 同步接口）。
    失败时由调用方（task_runner）负责降级至 edge_tts。
    """

    capabilities = COSYVOICE_CAPABILITIES

    def __init__(
        self,
        api_url: str,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
        max_retries: int = 2,
        model: str = _DEFAULT_MODEL,
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.model = model
        self._session = _requests.Session()
        self._session.headers.update({"Accept": "*/*"})

    def supports_multi_segment(self) -> bool:
        return False

    def available_voices(self, language: str) -> list[VoiceSpec]:
        from demo_app.voice_resolver import COSYVOICE_VOICE_CATALOG
        return [
            VoiceSpec(
                provider="real_human",
                voice_id=v["voice_id"],
                language=language,
                gender=v.get("gender", "female"),
            )
            for v in COSYVOICE_VOICE_CATALOG.get(language, [])
        ]

    # ── 底层 HTTP（同步，在 run_in_executor 线程中调用） ──────────────────────

    def _call_speech_v1(
        self,
        text: str,
        voice_id: str,
        speed: float,
        output_path: Path,
    ) -> None:
        """
        POST /v1/audio/speech → 直接写入 WAV 文件。
        抛出异常由调用方捕获并分类。
        """
        url = f"{self.api_url}/v1/audio/speech"
        payload = {
            "model":           self.model,
            "input":           text,
            "voice":           voice_id,
            "response_format": "wav",
            "speed":           speed,
        }
        resp = self._session.post(
            url,
            json=payload,
            timeout=self.timeout_sec,
        )
        resp.raise_for_status()

        # 校验是否为音频内容
        content_type = resp.headers.get("Content-Type", "")
        if resp.content and len(resp.content) < 100:
            raise RuntimeError(
                f"/v1/audio/speech 返回内容过小（{len(resp.content)} bytes），"
                f"Content-Type={content_type}，body={resp.content[:200]}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
        logger.debug(
            "[cosyvoice] /v1/audio/speech ✓ voice=%s text_len=%d size=%d bytes",
            voice_id, len(text), len(resp.content),
        )

    # ── 主合成接口 ────────────────────────────────────────────────────────────

    async def synthesize(
        self, request: SynthesisRequest, output_path: Path
    ) -> SynthesisResult:
        """
        异步合成一个 SynthesisRequest（段落级，单 speaker）。
        内部 HTTP 调用通过 run_in_executor 不阻塞事件循环。
        """
        t0 = time.monotonic()
        text = "".join(request.segments)
        voice_id = request.voice_spec.voice_id
        speed = request.voice_spec.speed
        request_chars = len(text)

        if not voice_id:
            return self._make_error_result(
                request, "param_error", "voice_id 为空，无法调用 CosyVoice",
                t0, request_chars,
            )

        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(
                None,
                lambda: self._call_speech_v1(text, voice_id, speed, output_path),
            )
        except Exception as exc:
            return self._classify_error(request, exc, t0, request_chars)

        total_ms = int((time.monotonic() - t0) * 1000)

        # 最终校验
        file_size = output_path.stat().st_size if output_path.exists() else 0
        if file_size < 100:
            return self._make_error_result(
                request, "empty_audio",
                f"音频文件过小（{file_size} bytes），可能合成失败",
                t0, request_chars,
            )

        logger.info(
            "[cosyvoice] ✅ speaker=%s chars=%d voice=%s total=%dms size=%d",
            request.speaker, request_chars, voice_id, total_ms, file_size,
        )

        return SynthesisResult(
            request=request,
            audio_path=output_path,
            provider_used="real_human",
            degraded=False,
            degraded_reason=None,
            latency_ms=total_ms,
            api_response_code=200,
            request_chars=request_chars,
            audio_duration_ms=0,
            timeline_source="estimated",
        )

    # ── 错误处理辅助 ──────────────────────────────────────────────────────────

    def _classify_error(
        self,
        request: SynthesisRequest,
        exc: Exception,
        t0: float,
        request_chars: int,
        **kwargs,
    ) -> SynthesisResult:
        """将 requests 异常分类，返回带诊断信息的失败结果。"""
        reason = f"provider_error:{type(exc).__name__}"
        if isinstance(exc, _requests.exceptions.Timeout):
            reason = "timeout"
        elif isinstance(exc, _requests.exceptions.HTTPError):
            code = getattr(exc.response, "status_code", 0) or 0
            if code == 429:
                reason = "rate_limit"
            elif code in (401, 403):
                reason = "auth_failure"
            elif code == 400:
                reason = f"param_error:{type(exc).__name__}"
            else:
                reason = f"http_{code}:{type(exc).__name__}"
        return self._make_error_result(
            request, reason, str(exc), t0, request_chars, **kwargs
        )

    def _make_error_result(
        self,
        request: SynthesisRequest,
        reason: str,
        msg: str,
        t0: float,
        request_chars: int,
        **kwargs,
    ) -> SynthesisResult:
        ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "[cosyvoice] ❌ speaker=%s reason=%s msg=%s",
            request.speaker, reason, msg,
        )
        short_msg = msg[:300] + "…" if len(msg) > 300 else msg
        return SynthesisResult(
            request=request,
            audio_path=None,
            provider_used="real_human",
            degraded=True,
            degraded_reason=reason,
            latency_ms=ms,
            api_response_code=None,
            request_chars=request_chars,
            audio_duration_ms=0,
            timeline_source="original",
            error_msg=short_msg,
        )


def load_real_human_provider(runtime_cfg: dict) -> Optional[RealHumanProvider]:
    """
    从 runtime.yaml 配置和环境变量加载 RealHumanProvider。
    优先使用环境变量 REAL_HUMAN_TTS_API_URL，其次 runtime.yaml。
    返回 None 表示未配置或不可用。
    """
    import os
    api_url = (
        os.environ.get("REAL_HUMAN_TTS_API_URL", "").strip()
        or (runtime_cfg.get("tts", {})
                       .get("real_human", {})
                       .get("api_url", "")
                       .strip())
    )
    if not api_url:
        logger.info("[cosyvoice] REAL_HUMAN_TTS_API_URL 未配置，真人 TTS 不可用")
        return None

    tts_cfg = runtime_cfg.get("tts", {}).get("real_human", {})
    provider = RealHumanProvider(
        api_url=api_url,
        timeout_sec=int(tts_cfg.get("timeout_sec", _DEFAULT_TIMEOUT_SEC)),
        max_retries=int(tts_cfg.get("max_retries", 2)),
    )
    logger.info("[cosyvoice] Provider 就绪（/v1/audio/speech），api_url=%s", api_url)
    return provider
