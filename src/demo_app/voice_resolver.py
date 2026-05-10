"""
demo_app/voice_resolver.py
==========================
统一音色解析入口，兼容新格式（voice_assignments）和旧格式（voice_map）。

调用方一览：
  - task_runner.py：从 DB 读取 voice_assignments / voice_map，按 speaker_id 解析
  - embedded_server_main.py（Phase 2 后接入）：legacy modal payload 解析
"""
from __future__ import annotations

import logging
from typing import Optional

from demo_app.tts_provider import VoiceSpec

logger = logging.getLogger(__name__)


# ── CosyVoice 已注册克隆音色目录 ─────────────────────────────────────────────
# 来源：GET http://10.0.20.10:8188/v1/voices（2026-05-10 确认）
# 扩充时直接在此添加条目，无需改其他代码。

COSYVOICE_VOICE_CATALOG: dict[str, list[dict]] = {
    "Chinese": [
        {"voice_id": "36d3429a3c98", "name": "maryzhang", "gender": "female"},
    ],
    "English": [
        {"voice_id": "c3e9f75ae993", "name": "willwu", "gender": "male"},
    ],
    # 待扩充：Japanese / Korean / ...
}

# edge_tts 各语言默认音色（语言无真人音色时回退）
EDGE_DEFAULT_VOICES: dict[str, str] = {
    "Chinese":    "zh-CN-XiaoxiaoNeural",
    "English":    "en-US-JennyNeural",
    "Japanese":   "ja-JP-NanamiNeural",
    "Korean":     "ko-KR-SunHiNeural",
    "Spanish":    "es-ES-ElviraNeural",
    "French":     "fr-FR-DeniseNeural",
    "German":     "de-DE-KatjaNeural",
    "Portuguese": "pt-BR-FranciscaNeural",
    "Russian":    "ru-RU-SvetlanaNeural",
    "Cantonese":  "zh-HK-HiuGaaiNeural",
    "Italian":    "it-IT-ElsaNeural",
    "Arabic":     "ar-SA-ZariyahNeural",
    "Indonesian": "id-ID-GadisNeural",
}


# ── 公共函数 ──────────────────────────────────────────────────────────────────

def default_voice_spec(
    language: str,
    speaker_id: str,
    effective_provider: str = "edge_tts",
) -> VoiceSpec:
    """
    按语言自动分配默认音色。
    - real_human：从 COSYVOICE_VOICE_CATALOG 按 speaker 序号轮转
    - 无真人音色时自动回退 edge_tts
    """
    if effective_provider == "real_human":
        voices = COSYVOICE_VOICE_CATALOG.get(language, [])
        if voices:
            try:
                idx = (int(speaker_id) - 1) % len(voices)
            except (ValueError, TypeError):
                idx = 0
            v = voices[idx]
            return VoiceSpec(
                provider="real_human",
                voice_id=v["voice_id"],
                language=language,
                gender=v.get("gender", "female"),
            )
        # 该语言没有真人音色 → 自动回退 edge_tts，记录 warning
        logger.warning(
            "[voice_resolver] 语言 '%s' 无真人克隆音色，speaker=%s 回退 edge_tts",
            language, speaker_id,
        )
        effective_provider = "edge_tts"

    voice_id = EDGE_DEFAULT_VOICES.get(language, "zh-CN-XiaoxiaoNeural")
    return VoiceSpec(
        provider="edge_tts",
        voice_id=voice_id,
        language=language,
    )


def resolve_voice_spec(
    speaker_id: str,
    language: str,
    voice_assignments: Optional[dict] = None,
    voice_map: Optional[dict] = None,
    effective_provider: str = "edge_tts",
) -> VoiceSpec:
    """
    统一音色解析。优先级：
      1. voice_assignments（新格式，精确指定 provider + voice_id）
      2. voice_map（旧格式，仅 edge_tts，只读不写）
      3. default_voice_spec（按语言自动分配）
    """
    # 1. 新格式 voice_assignments
    if voice_assignments and speaker_id in voice_assignments:
        spec = VoiceSpec.from_dict(
            voice_assignments[speaker_id],
            language=language,
            fallback_provider=effective_provider,
        )
        # 安全校验：real_human voice_id 必须在全局已注册音色中。
        # CosyVoice zero_shot 支持跨语言合成，允许用英文克隆音色合成中文（反之亦然），
        # 因此只检查 voice_id 是否在全局目录中注册，不限制必须属于当前语言。
        if spec.provider == "real_human":
            all_valid_ids = {
                v["voice_id"]
                for lang_voices in COSYVOICE_VOICE_CATALOG.values()
                for v in lang_voices
            }
            if all_valid_ids and spec.voice_id not in all_valid_ids:
                logger.warning(
                    "[voice_resolver] voice_id=%s 未在全局音色目录中注册，自动替换为默认音色",
                    spec.voice_id,
                )
                return default_voice_spec(language, speaker_id, effective_provider)
        return spec
    # 2. 旧格式 voice_map（只读）
    if voice_map and speaker_id in voice_map:
        return VoiceSpec(
            provider="edge_tts",
            voice_id=voice_map[speaker_id],
            language=language,
        )
    # 3. 自动分配
    return default_voice_spec(language, speaker_id, effective_provider)


def build_synthesis_requests(
    line_tuples: list[tuple[str, str]],
    language: str,
    voice_assignments: Optional[dict],
    voice_map: Optional[dict],
    effective_provider: str,
    max_chars: int = 500,
) -> list:
    """
    将对话行列表转换为 SynthesisRequest 列表。
    相同 speaker 的连续行合并为一个 SynthesisRequest（段落级合并）。
    单个 Request 超过 max_chars 时在换行处切段。

    返回 list[SynthesisRequest]（避免循环导入，动态导入）。
    """
    from demo_app.tts_provider import SynthesisRequest

    if not line_tuples:
        return []

    requests = []
    cur_speaker, cur_segments, cur_indices = "", [], []

    def _flush():
        if not cur_speaker or not cur_segments:
            return
        spec = resolve_voice_spec(
            # speaker_id 取纯数字部分，兼容 "Speaker 1" 格式
            speaker_id=_extract_speaker_num(cur_speaker),
            language=language,
            voice_assignments=voice_assignments,
            voice_map=voice_map,
            effective_provider=effective_provider,
        )
        requests.append(SynthesisRequest(
            speaker=cur_speaker,
            segments=list(cur_segments),
            voice_spec=spec,
            line_indices=list(cur_indices),
        ))

    for i, (speaker, text) in enumerate(line_tuples):
        if speaker != cur_speaker:
            _flush()
            cur_speaker = speaker
            cur_segments = []
            cur_indices = []

        # 超过 max_chars 切段
        if cur_segments and sum(len(s) for s in cur_segments) + len(text) > max_chars:
            _flush()
            cur_speaker = speaker
            cur_segments = []
            cur_indices = []

        cur_segments.append(text)
        cur_indices.append(i)

    _flush()
    return requests


def _extract_speaker_num(speaker: str) -> str:
    """从 'Speaker 1' 提取 '1'，兼容其他格式。"""
    import re
    m = re.search(r"\d+", speaker)
    return m.group() if m else speaker
