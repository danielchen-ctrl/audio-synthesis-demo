"""CosyVoice Provider 实现。

调用 OpenAI 兼容的 /v1/audio/speech 端点：
  POST {COSYVOICE_BASE_URL}/v1/audio/speech
  Body: {"model": "cosyvoice-v3", "input": "...", "voice": "<voice_id>",
         "response_format": "wav", "speed": 1.0}
  Response: WAV bytes

并发约束: 经验上 max_concurrency=1 最稳，更高会出现响应串扰。
通过 Celery audio_synth 队列的 concurrency=1 配置保证。
"""
from __future__ import annotations

import time

import httpx
from loguru import logger

from app.providers.tts.base import (
    SynthesisRequest,
    SynthesisResult,
    TTSProvider,
    VoiceSpec,
)


class CosyVoiceProvider(TTSProvider):
    def __init__(
        self,
        base_url: str,
        model: str = "cosyvoice-v3",
        timeout_sec: int = 120,
        max_retries: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_sec
        self._max_retries = max_retries

    def synthesize(self, req: SynthesisRequest) -> SynthesisResult:
        url = f"{self._base_url}/v1/audio/speech"
        payload = {
            "model": self._model,
            "input": req.text,
            "voice": req.voice_id,
            "response_format": req.response_format,
            "speed": req.speed,
        }
        last_err: str | None = None
        for attempt in range(self._max_retries + 1):
            t0 = time.monotonic()
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post(url, json=payload)
                resp.raise_for_status()
                latency_ms = int((time.monotonic() - t0) * 1000)
                content_type = resp.headers.get("content-type", "")
                if "json" in content_type:
                    # 错误以 JSON 形式返回
                    return SynthesisResult(
                        success=False,
                        error_message=f"Unexpected JSON: {resp.text[:300]}",
                        error_code="unexpected_response",
                        latency_ms=latency_ms,
                    )
                return SynthesisResult(
                    success=True,
                    audio_bytes=resp.content,
                    audio_format=req.response_format,
                    latency_ms=latency_ms,
                )
            except httpx.TimeoutException as e:
                last_err = f"timeout: {e}"
                logger.warning(f"CosyVoice timeout attempt={attempt + 1}: {e}")
            except httpx.HTTPStatusError as e:
                last_err = f"http_{e.response.status_code}: {e.response.text[:200]}"
                logger.warning(f"CosyVoice http error attempt={attempt + 1}: {last_err}")
                if 400 <= e.response.status_code < 500:
                    # 客户端错误不重试
                    break
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                logger.exception(f"CosyVoice unexpected error attempt={attempt + 1}")

        return SynthesisResult(
            success=False,
            error_message=last_err,
            error_code="synthesis_failed",
        )

    def list_voices(self, language: str | None = None) -> list[VoiceSpec]:
        """从 CosyVoice /v1/voices/custom 拉音色列表。"""
        url = f"{self._base_url}/v1/voices/custom"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            voices = []
            # 兼容多种返回结构
            items = data.get("voices") if isinstance(data, dict) else data
            for item in items or []:
                spec = VoiceSpec(
                    voice_id=item.get("voice_id") or item.get("id"),
                    name=item.get("name", "unknown"),
                    language=item.get("language", "zh"),
                    gender=item.get("gender"),
                )
                if language is None or spec.language == language:
                    voices.append(spec)
            return voices
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to fetch CosyVoice voices: {e}")
            return []
