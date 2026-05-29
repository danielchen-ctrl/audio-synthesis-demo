"""脚本生成：PRD §12 JSON + SRT。"""
from __future__ import annotations

import json


def build_json_transcript(
    audio_id: str,
    duration_sec: float,
    language: str,
    speaker_count: int,
    segments: list[dict],
) -> str:
    """生成 PRD §12.1 格式的 JSON 字符串。"""
    payload = {
        "audio_id": audio_id,
        "duration": round(duration_sec, 2),
        "language": language,
        "speaker_count": speaker_count,
        "segments": [
            {
                "segment_id": i + 1,
                "speaker_id": f"S{s['speaker_id']}",
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "text": s["text"],
            }
            for i, s in enumerate(segments)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _fmt_srt_time(t: float) -> str:
    """秒 → SRT 时间戳: 00:00:00,000"""
    if t < 0:
        t = 0
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_transcript(segments: list[dict]) -> str:
    """生成 SRT 字符串。"""
    lines: list[str] = []
    for i, s in enumerate(segments):
        idx = i + 1
        start = _fmt_srt_time(s["start_time"])
        end = _fmt_srt_time(s["end_time"])
        text = s["text"].strip()
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(f"S{s['speaker_id']}: {text}")
        lines.append("")  # 段间空行
    return "\n".join(lines)
