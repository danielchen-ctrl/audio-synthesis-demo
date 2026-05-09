"""
demo_app/real_human_tts.py
==========================
RealHumanProvider — CosyVoice TTS API 实现（zero_shot 克隆模式）。

API 端点（http://10.0.20.10:8188）：
  POST /api/tts/async              提交异步合成任务，返回 task_id
  GET  /api/task/{task_id}         轮询任务状态 → {status, filename}
  GET  /api/download/{filename}    下载生成的 WAV 音频

当前可用音色（GET /v1/voices，2026-05-10 确认）：
  中文: maryzhang  voice_id=36d3429a3c98
  英文: willwu     voice_id=c3e9f75ae993

HTTP 调用通过 requests + asyncio.run_in_executor 在线程池执行，
避免阻塞 Tornado 事件循环，无需引入 aiohttp 额外依赖。
"""
from __future__ import annotations

import asyncio
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

# ── CosyVoice 能力声明（基于 openapi.json + Swagger UI 截图核对） ──────────────
COSYVOICE_CAPABILITIES = ProviderCapabilities(
    tier="B",
    supports_ssml=False,
    supports_multi_speaker=False,
    supports_word_timestamps=False,
    supports_pause_control=True,      # speed 字段
    max_chars_per_request=500,
    output_formats=["wav"],
    async_mode=True,                  # /api/tts/async → poll → download
)

# 轮询间隔（秒）和最大超时
_DEFAULT_POLL_INTERVAL = 2.0
_DEFAULT_TIMEOUT_SEC   = 60


class RealHumanProvider(TTSProvider):
    """
    CosyVoice TTS Provider。
    合成模式：zero_shot（使用 /v1/voices/create 注册的 spk_id）。
    失败时由调用方（task_runner）负责降级至 EdgeTTSProvider。
    """

    capabilities = COSYVOICE_CAPABILITIES

    def __init__(
        self,
        api_url: str,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
        max_retries: int = 2,
    ):
        self.api_url = api_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self._session = _requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def supports_multi_segment(self) -> bool:
        return False  # 每次请求合成单一 speaker 的一段文本

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

    def _post_tts_async(self, text: str, spk_id: str, speed: float = 1.0) -> str:
        """
        POST /api/tts/async 提交合成任务。
        返回 task_id 字符串。
        """
        url = f"{self.api_url}/api/tts/async"
        data = {
            "text":   text,
            "mode":   "zero_shot",
            "spk_id": spk_id,
            "speed":  str(speed),
        }
        resp = self._session.post(url, data=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        # 兼容多种可能的 key 名
        task_id = (
            result.get("task_id")
            or result.get("job_id")
            or result.get("id")
            or result.get("taskId")
        )
        if not task_id:
            raise RuntimeError(f"CosyVoice 未返回 task_id，响应: {result}")
        logger.debug("[cosyvoice] 提交 ✓ task_id=%s text_len=%d", task_id, len(text))
        return str(task_id)

    def _get_task_status(self, task_id: str) -> dict:
        """GET /api/task/{task_id} 查询任务状态。"""
        url = f"{self.api_url}/api/task/{task_id}"
        resp = self._session.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _download_audio(self, filename: str, output_path: Path) -> None:
        """GET /api/download/{filename} 下载音频到本地路径。"""
        url = f"{self.api_url}/api/download/{filename}"
        resp = self._session.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        size = output_path.stat().st_size if output_path.exists() else 0
        logger.debug("[cosyvoice] 下载 ✓ %s → %s (%d bytes)", filename, output_path.name, size)

    def _poll_until_done(self, task_id: str) -> tuple[str, int]:
        """
        同步轮询直到任务完成或超时。
        返回 (filename, poll_count)。
        """
        elapsed = 0.0
        poll_count = 0
        while elapsed < self.timeout_sec:
            status_resp = self._get_task_status(task_id)
            poll_count += 1
            status = str(status_resp.get("status", "")).lower()

            if status in ("completed", "done", "success", "finished"):
                filename = (
                    status_resp.get("filename")
                    or status_resp.get("file")
                    or status_resp.get("result_file")
                    or status_resp.get("output_file")
                    or status_resp.get("output")
                )
                if not filename:
                    raise RuntimeError(
                        f"CosyVoice task={task_id} 完成但无 filename，响应: {status_resp}"
                    )
                logger.debug(
                    "[cosyvoice] 轮询 ✓ task_id=%s poll=%d filename=%s",
                    task_id, poll_count, filename,
                )
                return str(filename), poll_count

            if status in ("failed", "error"):
                raise RuntimeError(
                    f"CosyVoice task={task_id} 失败: "
                    f"{status_resp.get('error') or status_resp.get('message') or status_resp}"
                )

            time.sleep(_DEFAULT_POLL_INTERVAL)
            elapsed += _DEFAULT_POLL_INTERVAL

        raise TimeoutError(
            f"CosyVoice task={task_id} 超时 {self.timeout_sec}s（已 poll {poll_count} 次）"
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
        spk_id = request.voice_spec.voice_id
        request_chars = len(text)

        if not spk_id:
            return self._make_error_result(
                request, "param_error", "voice_id 为空，无法调用 CosyVoice",
                t0, request_chars,
            )

        loop = asyncio.get_event_loop()
        task_id: Optional[str] = None

        # ── Phase 1: 提交 ─────────────────────────────────────────────────────
        try:
            task_id = await loop.run_in_executor(
                None,
                lambda: self._post_tts_async(text, spk_id, request.voice_spec.speed),
            )
        except Exception as exc:
            return self._classify_error(request, exc, t0, request_chars)

        submit_ms = int((time.monotonic() - t0) * 1000)
        t1 = time.monotonic()

        # ── Phase 2: 轮询 ─────────────────────────────────────────────────────
        filename: Optional[str] = None
        poll_count = 0
        try:
            filename, poll_count = await loop.run_in_executor(
                None, lambda: self._poll_until_done(task_id)
            )
        except TimeoutError as exc:
            return self._make_error_result(
                request, "timeout", str(exc), t0, request_chars,
                job_id=task_id, submit_ms=submit_ms,
            )
        except Exception as exc:
            return self._classify_error(
                request, exc, t0, request_chars,
                job_id=task_id, submit_ms=submit_ms,
            )

        t2 = time.monotonic()

        # ── Phase 3: 下载 ─────────────────────────────────────────────────────
        try:
            await loop.run_in_executor(
                None, lambda: self._download_audio(filename, output_path)
            )
        except Exception as exc:
            return self._make_error_result(
                request, "provider_error", f"下载失败: {exc}", t0, request_chars,
                job_id=task_id, submit_ms=submit_ms, poll_count=poll_count,
            )

        download_ms = int((time.monotonic() - t2) * 1000)
        total_ms = int((time.monotonic() - t0) * 1000)

        # ── 验证文件非空 ──────────────────────────────────────────────────────
        file_size = output_path.stat().st_size if output_path.exists() else 0
        if file_size < 100:
            return self._make_error_result(
                request, "empty_audio",
                f"音频文件过小（{file_size} bytes），可能合成失败",
                t0, request_chars,
                job_id=task_id, submit_ms=submit_ms, poll_count=poll_count,
            )

        logger.info(
            "[cosyvoice] ✅ speaker=%s chars=%d task_id=%s "
            "submit=%dms poll=%d download=%dms total=%dms",
            request.speaker, request_chars, task_id,
            submit_ms, poll_count, download_ms, total_ms,
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
            audio_duration_ms=0,      # 由调用方 ffprobe 探针填写
            timeline_source="estimated",
            job_id=task_id,
            submit_latency_ms=submit_ms,
            poll_count=poll_count,
            download_latency_ms=download_ms,
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
        """将 requests 异常分类为六类之一。"""
        reason = "provider_error"
        if isinstance(exc, _requests.exceptions.Timeout):
            reason = "timeout"
        elif isinstance(exc, _requests.exceptions.HTTPError):
            code = getattr(exc.response, "status_code", 0) or 0
            if code == 429:
                reason = "rate_limit"
            elif code in (401, 403):
                reason = "auth_failure"
            elif code == 400:
                reason = "param_error"
            elif 500 <= code < 600:
                reason = "provider_error"
        return self._make_error_result(request, reason, str(exc), t0, request_chars, **kwargs)

    def _make_error_result(
        self,
        request: SynthesisRequest,
        reason: str,
        msg: str,
        t0: float,
        request_chars: int,
        job_id: Optional[str] = None,
        submit_ms: Optional[int] = None,
        poll_count: Optional[int] = None,
    ) -> SynthesisResult:
        ms = int((time.monotonic() - t0) * 1000)
        logger.warning(
            "[cosyvoice] ❌ speaker=%s reason=%s msg=%s",
            request.speaker, reason, msg,
        )
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
            job_id=job_id,
            submit_latency_ms=submit_ms,
            poll_count=poll_count,
            download_latency_ms=None,
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
    logger.info("[cosyvoice] Provider 就绪，api_url=%s", api_url)
    return provider
