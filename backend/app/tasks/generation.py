"""Celery 任务：文本生成 → 音频合成 → 入库。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.celery_app import celery_app
from app.core.db import SessionLocal
from app.models import AudioFile, Task, TaskStatus, Transcript
from app.models import Folder
from app.providers.llm import get_llm_provider
from app.providers.storage.minio_client import build_audio_key, upload_bytes
from app.providers.tts import get_tts_provider
from app.services.audio import build_file_name, parse_manual_dialogue, synthesize_lines
from app.services.dialogue import generate_dialogue
from app.services.scripts import build_json_transcript, build_srt_transcript
from app.services.tags import upsert_tags_by_names


@celery_app.task(bind=True, name="app.tasks.generation.run_generation_task")
def run_generation_task(self, task_id: str) -> dict:
    """端到端：拉任务 → 生成文本 → 合成音频 → 存 MinIO → 入库。"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == uuid.UUID(task_id)).first()
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"ok": False, "error": "task_not_found"}

        if task.status == TaskStatus.CANCELLED.value:
            logger.info(f"Task {task_id} already cancelled, skip")
            return {"ok": False, "error": "cancelled"}

        params = task.params or {}
        mode = task.generation_mode
        language = params["language"]
        speaker_count = params["speaker_count"]
        voice_assignments = params["voice_assignments"]
        topic = params["topic"]
        audio_format = params.get("audio_format", "mp3")

        task.started_at = datetime.now(timezone.utc)

        # ===== 1. 文本生成 / 解析 =====
        if mode == "llm":
            task.status = TaskStatus.TEXT_GENERATING.value
            task.progress = 10
            db.commit()
            logger.info(f"Task {task_id}: generating text via LLM")

            try:
                llm = get_llm_provider()
                raw_text, lines = generate_dialogue(
                    llm=llm,
                    template=params["template"],
                    custom_prompt=params.get("custom_prompt"),
                    topic=topic,
                    language=language,
                    speaker_count=speaker_count,
                    target_duration_sec=params.get("target_duration_sec", 60),
                    keywords=params.get("keywords", []),
                )
                task.dialogue_text = raw_text
                task.progress = 40
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Task {task_id}: text generation failed")
                _mark_failed(db, task, "text_generation_failed", str(e))
                return {"ok": False, "error": "text_generation_failed"}
        else:
            # manual
            if not task.dialogue_text:
                _mark_failed(db, task, "missing_dialogue_text", "manual 模式缺少文本")
                return {"ok": False, "error": "missing_dialogue_text"}
            try:
                lines = parse_manual_dialogue(task.dialogue_text)
            except Exception as e:  # noqa: BLE001
                _mark_failed(db, task, "dialogue_parse_failed", str(e))
                return {"ok": False, "error": "dialogue_parse_failed"}

        # ===== 2. 校验说话人数 =====
        speakers_in_text = {sid for sid, _ in lines}
        if len(speakers_in_text) != speaker_count:
            _mark_failed(
                db, task, "speaker_count_mismatch",
                f"文本中 {len(speakers_in_text)} 个 speaker，配置 {speaker_count} 个",
            )
            return {"ok": False, "error": "speaker_count_mismatch"}

        # ===== 3. 音频合成 =====
        task.status = TaskStatus.SYNTHESIZING.value
        task.progress = 50
        db.commit()
        logger.info(f"Task {task_id}: synthesizing {len(lines)} lines via CosyVoice")

        try:
            tts = get_tts_provider()
            audio_bytes, duration_sec, segments = synthesize_lines(
                tts=tts,
                lines=lines,
                voice_assignments=voice_assignments,
                language=language,
                output_format=audio_format,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Task {task_id}: synthesis failed")
            _mark_failed(db, task, "synthesis_failed", str(e))
            return {"ok": False, "error": "synthesis_failed"}

        task.progress = 90
        db.commit()

        # ===== 4. 存 MinIO + 入库 =====
        file_id = uuid.uuid4()
        file_name = build_file_name(topic, audio_format)
        storage_key = build_audio_key(str(file_id), file_name)

        content_type = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
        }.get(audio_format, "application/octet-stream")

        try:
            upload_bytes(storage_key, audio_bytes, content_type=content_type)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Task {task_id}: minio upload failed")
            _mark_failed(db, task, "storage_failed", str(e))
            return {"ok": False, "error": "storage_failed"}

        # 校验 folder（如果指定）
        folder_uuid: uuid.UUID | None = None
        if params.get("folder_id"):
            try:
                fuuid = uuid.UUID(params["folder_id"])
                folder = db.query(Folder).filter(Folder.folder_id == fuuid).first()
                if folder and folder.user_id == task.user_id:
                    folder_uuid = fuuid
            except (ValueError, TypeError):
                pass

        audio_file = AudioFile(
            file_id=file_id,
            user_id=task.user_id,
            folder_id=folder_uuid,
            file_name=file_name,
            storage_key=storage_key,
            file_size=len(audio_bytes),
            duration_sec=round(duration_sec, 2),
            format=audio_format,
            language=language,
            speaker_count=speaker_count,
            scene=params.get("template") or "custom",
            topic=topic,
            source="generated",
            task_id=task.task_id,
        )

        # 挂标签
        tag_names = params.get("tag_names") or []
        if tag_names:
            audio_file.tags = upsert_tags_by_names(db, tag_names)

        db.add(audio_file)
        db.flush()  # 让 audio_file 进 DB（拿到 FK），但还未 commit

        # ===== 5. Transcript：段级时间码（始终存）+ JSON/SRT 文件（按需）=====
        transcript_record = Transcript(
            file_id=file_id,
            segments=segments,
        )

        if params.get("generate_scripts"):
            # PRD §12: 同名前缀 + _transcript.json / _transcript.srt
            base = file_name.rsplit(".", 1)[0]
            json_content = build_json_transcript(
                audio_id=str(file_id),
                duration_sec=duration_sec,
                language=language,
                speaker_count=speaker_count,
                segments=segments,
            )
            srt_content = build_srt_transcript(segments)

            json_key = build_audio_key(str(file_id), f"{base}_transcript.json")
            srt_key = build_audio_key(str(file_id), f"{base}_transcript.srt")

            try:
                upload_bytes(json_key, json_content.encode("utf-8"),
                             content_type="application/json; charset=utf-8")
                upload_bytes(srt_key, srt_content.encode("utf-8"),
                             content_type="application/x-subrip; charset=utf-8")
                transcript_record.json_storage_key = json_key
                transcript_record.srt_storage_key = srt_key
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Script upload failed: {e}")

        db.add(transcript_record)

        task.status = TaskStatus.SUCCEEDED.value
        task.progress = 100
        task.file_id = file_id
        task.finished_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Task {task_id}: success, file_id={file_id}, duration={duration_sec:.2f}s"
        )
        return {"ok": True, "file_id": str(file_id)}

    finally:
        db.close()


def _mark_failed(db, task: Task, code: str, message: str) -> None:
    task.status = TaskStatus.FAILED.value
    task.error_code = code
    task.error_message = message[:500]
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
