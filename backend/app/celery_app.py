"""Celery 应用入口。

启动 worker:
  celery -A app.celery_app worker --loglevel=info -Q text_gen,audio_synth --concurrency=2
启动 beat (定时任务):
  celery -A app.celery_app beat --loglevel=info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "audio_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.generation",
        "app.tasks.cleanup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_routes={
        "app.tasks.generation.run_generation_task": {"queue": "audio_synth"},
        "app.tasks.cleanup.*": {"queue": "default"},
    },
    # 重试
    task_default_retry_delay=10,
    task_max_retries=2,
    # 超时
    task_soft_time_limit=900,
    task_time_limit=960,
    # ===== Beat schedule（PRD §13.4 / §19.4）=====
    beat_schedule={
        "purge-old-trash-daily": {
            "task": "app.tasks.cleanup.purge_old_trash",
            "schedule": crontab(hour=3, minute=0),  # 每日 UTC 03:00
        },
        "purge-old-failed-tasks-daily": {
            "task": "app.tasks.cleanup.purge_old_failed_tasks",
            "schedule": crontab(hour=3, minute=30),
        },
    },
)
