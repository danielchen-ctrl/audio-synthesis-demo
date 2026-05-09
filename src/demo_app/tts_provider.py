"""
demo_app/tts_provider.py
========================
TTS Provider 抽象层。
包含数据模型（VoiceSpec / SynthesisRequest / SynthesisResult / ProviderCapabilities）
和 Provider 接口（TTSProvider ABC）。

EdgeTTSProvider / BundleProvider 在 Phase 1 通过外部函数调用现有逻辑，
不在此文件迁移内部实现，降低重构风险。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────────────────────

@dataclass
class VoiceSpec:
    """统一音色参数对象，跨 provider 使用。"""

    provider: str           # "edge_tts" | "real_human" | "bundle"
    voice_id: str           # provider 内部 ID
    language: str           # "Chinese" / "English" / ...
    gender: str = "female"
    style: Optional[str] = None
    emotion: Optional[str] = None
    speed: float = 1.0
    sample_rate: int = 24000

    VALID_PROVIDERS = {"edge_tts", "real_human", "bundle"}

    @classmethod
    def from_dict(
        cls,
        data: dict,
        language: str = "Chinese",
        fallback_provider: str = "edge_tts",
    ) -> "VoiceSpec":
        """带校验和默认值补齐的构造方法，防止前端少传字段导致异常。"""
        provider = data.get("provider") or fallback_provider
        if provider not in cls.VALID_PROVIDERS:
            logger.warning("[VoiceSpec] 未知 provider=%s，回退 %s", provider, fallback_provider)
            provider = fallback_provider
        return cls(
            provider=provider,
            voice_id=data.get("voice_id") or "",
            language=data.get("language") or language,
            gender=data.get("gender") or "female",
            style=data.get("style"),
            emotion=data.get("emotion"),
            speed=float(data.get("speed") or 1.0),
            sample_rate=int(data.get("sample_rate") or 24000),
        )


@dataclass
class SynthesisRequest:
    """合成请求单元（段落级）：同一 speaker 连续行合并后的单元。"""

    speaker: str
    segments: list[str]       # 该 speaker 连续多句文本
    voice_spec: VoiceSpec
    line_indices: list[int]   # 对应原始行号，用于时间轴回填


@dataclass
class SynthesisResult:
    """合成结果，记录实际执行路径与可观测数据。"""

    request: SynthesisRequest
    audio_path: Optional[Path]
    provider_used: str          # 实际执行的 provider（可能降级）
    degraded: bool
    degraded_reason: Optional[str]   # 见失败分类：timeout/rate_limit/auth_failure/...
    latency_ms: int
    api_response_code: Optional[int]
    request_chars: int
    audio_duration_ms: int
    timeline_source: str        # "api_word_timestamp" | "estimated" | "original"
    # 异步 API 专用（同步模式为 None）
    job_id: Optional[str] = None
    submit_latency_ms: Optional[int] = None
    poll_count: Optional[int] = None
    download_latency_ms: Optional[int] = None
    # 失败时的原始错误消息（截断到 300 字符，方便 tts_meta 诊断）
    error_msg: Optional[str] = None


@dataclass
class ProviderCapabilities:
    """
    结构化能力声明。
    路由决策依赖各字段而非 tier 字符串，tier 仅作辅助标签。
    """

    tier: str                        # "A" | "B" | "C"（辅助，不做路由依据）
    supports_ssml: bool
    supports_multi_speaker: bool
    supports_word_timestamps: bool
    supports_pause_control: bool
    max_chars_per_request: int
    output_formats: list[str]
    async_mode: bool


# ── Provider 抽象接口 ─────────────────────────────────────────────────────────

class TTSProvider(ABC):

    @abstractmethod
    async def synthesize(
        self, request: SynthesisRequest, output_path: Path
    ) -> SynthesisResult: ...

    @abstractmethod
    def supports_multi_segment(self) -> bool: ...

    @abstractmethod
    def available_voices(self, language: str) -> list[VoiceSpec]: ...
