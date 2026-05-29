"""TTS Provider 抽象。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VoiceSpec:
    voice_id: str
    name: str
    language: str
    gender: str | None = None
    provider: str = "cosyvoice"


@dataclass
class SynthesisRequest:
    text: str
    voice_id: str
    language: str
    speed: float = 1.0
    response_format: str = "wav"


@dataclass
class SynthesisResult:
    success: bool
    audio_bytes: bytes | None = None
    audio_format: str = "wav"
    sample_rate: int = 44100
    duration_sec: float | None = None
    latency_ms: int = 0
    error_message: str | None = None
    error_code: str | None = None
    raw: dict = field(default_factory=dict)


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, req: SynthesisRequest) -> SynthesisResult:
        raise NotImplementedError

    @abstractmethod
    def list_voices(self, language: str | None = None) -> list[VoiceSpec]:
        raise NotImplementedError
