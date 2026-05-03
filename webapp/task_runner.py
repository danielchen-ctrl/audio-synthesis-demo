"""
webapp/task_runner.py
=====================
异步任务队列。
- 提交任务后立即返回 task_id，后台协程处理生成 + 合成。
- 状态流转：queued → generating_text → synthesizing → completed / failed
- 调用现有 embedded_server_main 函数，不复制任何生成逻辑。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import webapp.db as db

logger = logging.getLogger(__name__)

_task_queue: asyncio.Queue = asyncio.Queue()


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def _parse_lines(dialogue_text: str) -> list[tuple[str, str]]:
    """把 'Speaker N: text' 格式文本解析为 (speaker, text) 列表。"""
    lines = []
    for raw in dialogue_text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if ": " in raw:
            speaker, text = raw.split(": ", 1)
            lines.append((speaker.strip(), text.strip()))
    return lines


def _guess_scene(template: str) -> str:
    t = (template or "").lower()
    if "会议" in t or "meeting" in t:
        return "meeting"
    if "访谈" in t or "interview" in t:
        return "interview"
    if "问诊" in t or "medical" in t:
        return "medical"
    return "other"


def _safe_basename(topic: str, task_id: str) -> str:
    slug = re.sub(r"[^\w一-龥\-]", "_", (topic or "")[:40]).strip("_")
    return f"{slug}_{task_id[:8]}" if slug else task_id[:8]


# ── 核心处理逻辑 ──────────────────────────────────────────────────────────────

async def _process_task(task_id: str) -> None:
    task = db.get_task(task_id)
    if not task:
        logger.warning("Task %s not found in DB", task_id)
        return

    # 导入生成函数（懒加载，避免启动时加载 bundle）
    try:
        from demo_app.embedded_server_main import (
            _generate_text_payload,
            _synthesize_audio_from_lines,
            load_bundle_server,
        )
    except ImportError as exc:
        logger.error("Failed to import generation modules: %s", exc)
        db.update_task_status(task_id, "failed", error_msg=f"模块加载失败: {exc}")
        return

    generation_mode = task.get("generation_mode", "llm")
    language = task.get("language", "中文")
    topic = task.get("topic") or ""
    people_count = int(task.get("people_count") or 2)
    word_count = int(task.get("word_count") or 1000)
    output_format = task.get("output_format") or "mp3"
    include_scripts = bool(task.get("include_scripts", 0))
    voice_map: dict[str, str] = json.loads(task.get("voice_map") or "{}")
    dialogue_id: str | None = None

    # ── Step 1: 生成文本 ───────────────────────────────────────────────────
    db.update_task_status(task_id, "generating_text")
    logger.info("Task %s: generating text (mode=%s)", task_id, generation_mode)

    try:
        if generation_mode == "direct":
            input_text = task.get("input_text") or ""
            line_tuples = _parse_lines(input_text)
            if not line_tuples:
                raise ValueError("直接输入文本格式错误，无法解析对话行")
        else:
            payload: dict[str, Any] = {
                "title": topic,
                "scenario": topic,
                "core_content": task.get("custom_prompt") or topic,
                "people_count": people_count,
                "word_count": word_count,
                "language": language,
                "audio_language": language,
                "template_label": task.get("template") or "",
                "keyword_terms": json.loads(task.get("keywords") or "[]"),
            }
            bundle_server = load_bundle_server()
            loop = asyncio.get_event_loop()
            result: dict = await loop.run_in_executor(
                None, lambda: _generate_text_payload(bundle_server, payload)
            )
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "文本生成失败（未知错误）")
            dialogue_id = result["dialogue_id"]
            line_tuples = _parse_lines(result["dialogue_text"])
            if not line_tuples:
                raise RuntimeError("LLM 返回文本为空或格式错误")

    except Exception as exc:
        logger.exception("Task %s text generation failed", task_id)
        db.update_task_status(task_id, "failed", error_msg=str(exc))
        return

    # ── Step 2: 合成音频 ───────────────────────────────────────────────────
    db.update_task_status(task_id, "synthesizing")
    logger.info("Task %s: synthesizing audio (%d lines)", task_id, len(line_tuples))

    save_dir = ROOT / "storage" / "generated" / task_id
    save_dir.mkdir(parents=True, exist_ok=True)
    basename = _safe_basename(topic, task_id)

    try:
        bundle_server = load_bundle_server()
        audio_result: dict = await _synthesize_audio_from_lines(
            line_tuples,
            language,
            save_dir,
            basename,
            bundle_server,
            selected_voice_map=voice_map or None,
            output_format=output_format,
            include_scripts=include_scripts,
        )
    except Exception as exc:
        logger.exception("Task %s synthesis failed", task_id)
        db.update_task_status(task_id, "failed", error_msg=str(exc))
        return

    # ── Step 3: 落库 ──────────────────────────────────────────────────────
    audio_path = Path(audio_result["audio_file_path"])
    file_size = audio_path.stat().st_size if audio_path.exists() else 0

    # 从 segments JSON 读取时长
    duration = 0.0
    segs_path = audio_result.get("segments_json_path") or ""
    if segs_path and Path(segs_path).exists():
        try:
            segs = json.loads(Path(segs_path).read_text(encoding="utf-8"))
            if segs and isinstance(segs, list):
                duration = float(segs[-1].get("end_time", 0))
        except Exception:
            pass

    transcript_json: str | None = None
    if segs_path and Path(segs_path).exists():
        transcript_json = Path(segs_path).read_text(encoding="utf-8")

    transcript_srt: str | None = None
    srt_path = audio_result.get("transcript_srt_path") or ""
    if srt_path and Path(srt_path).exists():
        transcript_srt = Path(srt_path).read_text(encoding="utf-8")

    file_record = db.create_audio_file(
        {
            "task_id": task_id,
            "file_name": audio_path.name,
            "file_path": str(audio_path),
            "source": "generated",
            "duration": duration,
            "format": audio_result.get("output_format", output_format),
            "file_size": file_size,
            "language": language,
            "speaker_count": people_count,
            "scene": _guess_scene(task.get("template") or ""),
            "topic": topic,
            "transcript_json": transcript_json,
            "transcript_srt": transcript_srt,
        }
    )

    db.update_task_status(
        task_id,
        "completed",
        file_id=file_record["file_id"],
        dialogue_id=dialogue_id or "",
    )
    logger.info("Task %s completed → file_id=%s", task_id, file_record["file_id"])


# ── 后台 worker ───────────────────────────────────────────────────────────────

async def _worker() -> None:
    logger.info("[platform] Task worker started")
    while True:
        task_id: str = await _task_queue.get()
        try:
            await _process_task(task_id)
        except Exception:
            logger.exception("Unhandled error in task worker for task %s", task_id)
        finally:
            _task_queue.task_done()


def enqueue(task_id: str) -> None:
    """将 task_id 加入处理队列（线程安全）。"""
    loop = asyncio.get_event_loop()
    loop.call_soon_threadsafe(_task_queue.put_nowait, task_id)


def start_worker() -> None:
    """在 Tornado IOLoop 启动后调用一次，启动后台 worker 协程。"""
    asyncio.ensure_future(_worker())
