"""定时清理任务：回收站 30 天自动永久删除（PRD §13.4 / §19.4）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from app.celery_app import celery_app
from app.core.db import SessionLocal
from app.models import AudioFile, Task, TaskStatus
from app.providers.storage.minio_client import delete_object

RETENTION_DAYS_TRASH = 30
RETENTION_DAYS_FAILED_TASK = 90


@celery_app.task(name="app.tasks.cleanup.purge_old_trash")
def purge_old_trash() -> dict:
    """删除 deleted_at < now - 30d 的文件（DB + MinIO）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS_TRASH)
    db = SessionLocal()
    try:
        rows = (
            db.query(AudioFile)
            .filter(AudioFile.deleted_at.is_not(None), AudioFile.deleted_at < cutoff)
            .all()
        )
        count = 0
        for f in rows:
            try:
                delete_object(f.storage_key)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"purge: minio delete failed for {f.storage_key}: {e}")
            db.delete(f)
            count += 1
        db.commit()
        logger.info(f"purge_old_trash: removed {count} files older than {RETENTION_DAYS_TRASH}d")
        return {"purged": count}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup.purge_old_failed_tasks")
def purge_old_failed_tasks() -> dict:
    """删除 90 天前的 failed/cancelled 任务记录（PRD §19.4）。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS_FAILED_TASK)
    db = SessionLocal()
    try:
        deleted = (
            db.query(Task)
            .filter(
                Task.status.in_([TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]),
                Task.finished_at.is_not(None),
                Task.finished_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(f"purge_old_failed_tasks: removed {deleted} task records older than {RETENTION_DAYS_FAILED_TASK}d")
        return {"deleted": deleted}
    finally:
        db.close()
