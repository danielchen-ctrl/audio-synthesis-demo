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
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import src.webapp.db as db

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


def _guess_scene(template: str, topic: str = "") -> str:
    """从模板标签和/或主题文本推断场景分类。
    两个来源都会检查，任意匹配即返回，覆盖全部 25 个预置主题。"""
    # 合并 template 和 topic，同时检查
    t = ((template or "") + " " + (topic or "")).lower()
    # 医疗健康 — 慢病随访、化疗、手术、护理……
    if any(k in t for k in ["医疗", "健康", "随访", "慢病", "问诊", "化疗", "癌症",
                             "手术", "护理", "诊断", "病历", "患者", "medical", "health"]):
        return "medical"
    # 会议/战略/周会
    if any(k in t for k in ["会议", "周会", "战略", "复盘", "meeting"]):
        return "meeting"
    # 访谈/招聘/人力
    if any(k in t for k in ["访谈", "招聘", "面试", "人力", "补岗", "hr", "interview"]):
        return "interview"
    # 法律/合规
    if any(k in t for k in ["法律", "合规", "法顾", "广告合规", "合同", "审查", "legal"]):
        return "legal"
    # 金融/投资/保险/质检/洞察
    if any(k in t for k in ["金融", "投资", "资产", "保险", "质检", "洞察",
                             "理财", "基金", "证券", "finance"]):
        return "finance"
    # 科技/测试/支付/AI — 测试开发全部 5 个预置主题
    if any(k in t for k in ["科技", "测试", "支付", "人工智能", "付费", "对账",
                             "退款", "稳定性", "准入", "社交", "朋友圈", "隐私",
                             "权限", "分发", "接入", "交易", "tech", "ai"]):
        return "tech"
    # 零售/销售/复购
    if any(k in t for k in ["零售", "会员", "销售", "复购", "retail"]):
        return "sales"
    # 建筑/房地产/工程
    if any(k in t for k in ["房地产", "建筑", "工程", "项目交付", "项目去化",
                             "施工", "楼盘", "去化", "construction"]):
        return "construction"
    # 咨询/专业服务/客户拓展
    if any(k in t for k in ["咨询", "客户拓展", "拓展", "专业服务", "consulting"]):
        return "consulting"
    # 媒体/娱乐/艺人
    if any(k in t for k in ["媒体", "娱乐", "艺人", "商业化", "内容平台", "media"]):
        return "media"
    # 制造业/产线
    if any(k in t for k in ["制造", "产线", "产能", "设备", "生产线", "manufacturing"]):
        return "manufacturing"
    # 汽车/车型投放
    if any(k in t for k in ["汽车", "车型", "投放", "经销商", "试驾", "auto"]):
        return "auto"
    return "other"


def _safe_basename(topic: str) -> str:
    """生成文件名基础部分：主题slug + 当前时间戳（精确到秒）。"""
    slug = re.sub(r"[^\w一-龥\-]", "_", (topic or "")[:40]).strip("_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{slug}_{ts}" if slug else ts


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

    # ── Step 1.5: 仅文本模式 — 跳过音频合成，直接保存 txt 文件 ──────────────
    if generation_mode == "text_only":
        save_dir = ROOT / "storage" / "generated" / task_id
        save_dir.mkdir(parents=True, exist_ok=True)
        basename = _safe_basename(topic)
        txt_path = save_dir / f"{basename}.txt"
        text_content = "\n".join(f"{spk}: {txt}" for spk, txt in line_tuples)
        txt_path.write_text(text_content, encoding="utf-8")
        file_size = txt_path.stat().st_size

        tx_json: str | None = json.dumps(
            [{"speaker": spk, "text": txt, "start_time": None, "end_time": None}
             for spk, txt in line_tuples],
            ensure_ascii=False,
        ) if line_tuples else None

        file_record = db.create_audio_file({
            "task_id": task_id,
            "file_name": txt_path.name,
            "file_path": str(txt_path),
            "source": "generated",
            "duration": 0.0,
            "format": "txt",
            "file_size": file_size,
            "language": language,
            "speaker_count": people_count,
            "scene": _guess_scene(task.get("template") or "", topic),
            "topic": topic,
            "transcript_json": tx_json,
        })
        db.update_task_status(
            task_id,
            "completed",
            file_id=file_record["file_id"],
            dialogue_id=dialogue_id or "",
        )
        logger.info("Task %s (text_only) completed → file_id=%s", task_id, file_record["file_id"])
        return

    # ── Step 2: 合成音频 ───────────────────────────────────────────────────
    db.update_task_status(task_id, "synthesizing")
    logger.info("Task %s: synthesizing audio (%d lines)", task_id, len(line_tuples))

    save_dir = ROOT / "storage" / "generated" / task_id
    save_dir.mkdir(parents=True, exist_ok=True)
    basename = _safe_basename(topic)

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

    # 从 segments JSON 读取时长（仅当 include_scripts=True 时有值）
    duration = 0.0
    segs_path = audio_result.get("segments_json_path") or ""
    if segs_path and Path(segs_path).exists():
        try:
            segs = json.loads(Path(segs_path).read_text(encoding="utf-8"))
            if segs and isinstance(segs, list):
                duration = float(segs[-1].get("end_time", 0))
        except Exception:
            pass

    # 若 segments 不可用，直接读取音频文件时长（pydub 探针）
    if duration == 0.0 and audio_path.exists():
        try:
            from pydub import AudioSegment as _AS
            _seg = _AS.from_file(str(audio_path))
            duration = len(_seg) / 1000.0
            del _seg
        except Exception:
            pass

    # ── transcript_json ──────────────────────────────────────────────────
    # 优先使用带时间戳的 segments JSON（include_scripts=True 时产生）
    # 否则用对话行列表构造无时间戳的基础台本，保证详情页始终能显示文本
    transcript_json: str | None = None
    if segs_path and Path(segs_path).exists():
        transcript_json = Path(segs_path).read_text(encoding="utf-8")
    if not transcript_json and line_tuples:
        transcript_json = json.dumps(
            [{"speaker": spk, "text": txt, "start_time": None, "end_time": None}
             for spk, txt in line_tuples],
            ensure_ascii=False,
        )

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
            "scene": _guess_scene(task.get("template") or "", topic),
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
    """将 task_id 加入处理队列（从 Tornado handler 同步调用安全）。"""
    loop = asyncio.get_running_loop()
    loop.call_soon_threadsafe(_task_queue.put_nowait, task_id)


_MAX_WORKERS = 3  # 与 handlers.py 中的并发限制（count_active_tasks >= 3）保持一致


def backfill_scenes() -> int:
    """回填存量 audio_files 中 scene='other' 的记录，使用 topic 重新推断分类。
    在 start_worker() 时调用一次，幂等。返回更新条数。"""
    try:
        import sqlite3
        from pathlib import Path as _P
        _db_path = _P(__file__).resolve().parents[2] / "runtime" / "platform.db"
        if not _db_path.exists():
            return 0
        conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT file_id, topic, task_id FROM audio_files WHERE deleted=0 AND scene='other'"
        ).fetchall()
        updated = 0
        for row in rows:
            file_topic = row["topic"] or ""
            task_template = ""
            if row["task_id"]:
                t = conn.execute(
                    "SELECT template, topic FROM tasks WHERE task_id=?", (row["task_id"],)
                ).fetchone()
                if t:
                    task_template = t["template"] or ""
                    if not file_topic:
                        file_topic = t["topic"] or ""
            new_scene = _guess_scene(task_template, file_topic)
            if new_scene != "other":
                conn.execute(
                    "UPDATE audio_files SET scene=? WHERE file_id=?",
                    (new_scene, row["file_id"]),
                )
                updated += 1
        conn.commit()
        conn.close()
        if updated:
            logger.info("[scene-backfill] Updated %d file(s) from 'other' to inferred scenes", updated)
        return updated
    except Exception as exc:
        logger.warning("[scene-backfill] Failed: %s", exc)
        return 0


def start_worker() -> None:
    """在 Tornado IOLoop 启动后调用一次，启动后台 worker 协程（并发数 = _MAX_WORKERS）。"""
    backfill_scenes()          # 一次性回填存量 scene='other' 的文件
    for _ in range(_MAX_WORKERS):
        asyncio.ensure_future(_worker())
