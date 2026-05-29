"""音频合成 + 拼接。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from loguru import logger

from app.providers.tts import SynthesisRequest, TTSProvider


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("系统未安装 ffmpeg，无法拼接音频")


def synthesize_lines(
    tts: TTSProvider,
    lines: list[tuple[str, str]],
    voice_assignments: dict[str, dict],
    language: str,
    output_format: str = "mp3",
    fallback_tts: TTSProvider | None = None,
) -> tuple[bytes, float, list[dict], bool]:
    """按 (speaker_id, text) 顺序合成所有段，拼成最终音频。

    返回 (audio_bytes, total_duration_sec, segments, degraded)
      segments = [{speaker_id, text, start_time, end_time}, ...]
      degraded  = True 表示至少一段触发了 edge_tts 降级
    """
    _check_ffmpeg()

    if not lines:
        raise ValueError("无对话内容可合成")

    # 合并同 speaker 连续行（避免段太短 / 调用次数过多）
    merged: list[tuple[str, str]] = []
    for sid, text in lines:
        if merged and merged[-1][0] == sid and len(merged[-1][1]) + len(text) <= 500:
            merged[-1] = (sid, merged[-1][1] + " " + text)
        else:
            merged.append((sid, text))

    work = Path(tempfile.mkdtemp(prefix="audio_synth_"))
    degraded = False
    try:
        segment_files: list[Path] = []
        segment_durations: list[float] = []
        for idx, (sid, text) in enumerate(merged):
            assignment = voice_assignments.get(sid)
            if not assignment:
                raise ValueError(f"Speaker {sid} 未配置音色")
            voice_id = assignment["voice_id"]

            req = SynthesisRequest(
                text=text,
                voice_id=voice_id,
                language=language,
                response_format="wav",
            )
            result = tts.synthesize(req)
            if not result.success or not result.audio_bytes:
                if fallback_tts:
                    logger.warning(
                        f"CosyVoice 失败，降级 edge_tts (speaker={sid}): {result.error_code}"
                    )
                    fallback_req = SynthesisRequest(
                        text=text,
                        # 通过方法调用，不直接引用 provider 内部 dict
                        voice_id=fallback_tts.default_voice_for(language),
                        language=language,
                        response_format="wav",
                    )
                    result = fallback_tts.synthesize(fallback_req)
                    if not result.success:
                        raise RuntimeError(f"降级合成也失败: {result.error_message}")
                    degraded = True
                else:
                    raise RuntimeError(
                        f"第 {idx + 1} 段合成失败 (speaker={sid}): "
                        f"{result.error_code} / {result.error_message}"
                    )

            # CosyVoice 直接返回 wav；先落盘
            wav_path = work / f"seg_{idx:04d}.wav"
            wav_path.write_bytes(result.audio_bytes)
            # 统一转码到 44100Hz / mono / mp3
            mp3_path = work / f"seg_{idx:04d}.mp3"
            _ffmpeg_normalize(wav_path, mp3_path)
            segment_files.append(mp3_path)

            # 记录本段实测时长（拿 mp3 测，因为最终拼接的是 mp3）
            seg_dur = _ffmpeg_duration(mp3_path)
            segment_durations.append(seg_dur)
            logger.debug(f"Segment {idx + 1}/{len(merged)} ok ({len(text)} chars, {seg_dur:.2f}s)")

        # 拼接
        final_path = work / f"final.{output_format}"
        _ffmpeg_concat(segment_files, final_path)
        total_duration = _ffmpeg_duration(final_path)

        # 累加得到每段 start/end（毫秒精度即可）
        segments: list[dict] = []
        cursor = 0.0
        for (sid, text), seg_dur in zip(merged, segment_durations, strict=True):
            start_t = round(cursor, 3)
            end_t = round(cursor + seg_dur, 3)
            segments.append({
                "speaker_id": sid,
                "text": text,
                "start_time": start_t,
                "end_time": end_t,
            })
            cursor += seg_dur

        return final_path.read_bytes(), total_duration, segments, degraded
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _ffmpeg_normalize(src: Path, dst: Path) -> None:
    """统一格式 44.1kHz mono mp3 + 裁剪 CosyVoice 数字静音（-65dB 保守阈值）。"""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        # silenceremove：仅裁 ~-90dB 数字静音，不影响正常语音（>-40dB）
        "-af", (
            "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-65dB"
            ":stop_periods=1:stop_duration=0.15:stop_threshold=-65dB"
        ),
        "-ar", "44100", "-ac", "1",
        "-codec:a", "libmp3lame", "-b:a", "128k",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def _ffmpeg_concat(segments: list[Path], dst: Path) -> None:
    """用 filter_complex concat 拼接（完全兼容输入差异，消除拼接爆音）。"""
    if len(segments) == 1:
        shutil.copy(segments[0], dst)
        return

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in segments:
        cmd += ["-i", str(s)]
    filter_str = "".join(f"[{i}:a]" for i in range(len(segments)))
    filter_str += f"concat=n={len(segments)}:v=0:a=1[aout]"
    cmd += [
        "-filter_complex", filter_str,
        "-map", "[aout]",
        "-ar", "44100", "-ac", "1",
        "-codec:a", "libmp3lame", "-b:a", "128k",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def _ffmpeg_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def parse_manual_dialogue(text: str) -> list[tuple[str, str]]:
    """解析用户直接输入的对话文本，复用 dialogue 模块的正则。"""
    from app.services.dialogue import _SPEAKER_LINE_RE  # type: ignore

    lines: list[tuple[str, str]] = []
    for raw in text.splitlines():
        m = _SPEAKER_LINE_RE.match(raw)
        if m:
            lines.append((m.group(1), m.group(2).strip()))
    if not lines:
        raise ValueError("文本格式不符: 需要 'Speaker N: 内容' 每行")
    return lines


def build_file_name(topic: str, fmt: str) -> str:
    """文件名格式: {topic}_{yyyymmddhhmmss}.{fmt}。"""
    from datetime import datetime

    safe_topic = "".join(c if c.isalnum() or c in "-_" else "_" for c in topic)[:80]
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{safe_topic}_{ts}.{fmt}"


__all__ = [
    "build_file_name",
    "parse_manual_dialogue",
    "synthesize_lines",
]
