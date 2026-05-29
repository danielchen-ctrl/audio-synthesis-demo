"""任务 API：提交 / 列表 / 详情 / 取消。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models import Task, TaskStatus
from app.schemas.task import (
    DialoguePreviewRequest,
    DialoguePreviewResult,
    TaskCreate,
    TaskListItem,
    TaskOut,
)

router = APIRouter()
settings = get_settings()

_ACTIVE_STATUSES = {
    TaskStatus.QUEUED.value,
    TaskStatus.TEXT_GENERATING.value,
    TaskStatus.SYNTHESIZING.value,
}


@router.post("/preview-dialogue", response_model=DialoguePreviewResult)
def preview_dialogue(
    payload: DialoguePreviewRequest, current_user: CurrentUser
) -> DialoguePreviewResult:
    """PRD §8: LLM 生成对话文本但不入队，给前端预览/编辑。"""
    from app.providers.llm import get_llm_provider
    from app.services.dialogue import generate_dialogue

    from app.services.preset_topics import is_valid_template_code
    if not is_valid_template_code(payload.template):
        raise HTTPException(status_code=400, detail=f"未知的模板 code: {payload.template}")
    if payload.template == "custom" and not payload.custom_prompt:
        raise HTTPException(status_code=400, detail="自定义模板必须提供 custom_prompt")

    try:
        llm = get_llm_provider()
        raw_text, lines = generate_dialogue(
            llm=llm,
            template=payload.template,
            custom_prompt=payload.custom_prompt,
            topic=payload.topic,
            language=payload.language,
            speaker_count=payload.speaker_count,
            target_duration_sec=payload.target_duration_sec,
            keywords=payload.keywords or [],
        )
    except ValueError as e:
        # 包含：LLM 返回空 / 解析失败 / speaker 超数
        raise HTTPException(status_code=422, detail=f"生成失败: {e}") from e
    except Exception as e:  # noqa: BLE001
        logger.exception("Preview dialogue failed")
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {e}") from e

    return DialoguePreviewResult(
        dialogue_text=raw_text,
        line_count=len(lines),
        model=settings.LLM_MODEL,
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, current_user: CurrentUser, db: DbSession) -> TaskOut:
    """提交生成任务。"""
    # 校验：manual 模式必须有 dialogue_text；LLM 模式必须有 template
    if payload.generation_mode == "manual" and not payload.dialogue_text:
        raise HTTPException(status_code=400, detail="manual 模式必须提供 dialogue_text")
    if payload.generation_mode == "llm" and not payload.template:
        raise HTTPException(status_code=400, detail="LLM 模式必须提供 template")
    if payload.template:
        from app.services.preset_topics import is_valid_template_code
        if not is_valid_template_code(payload.template):
            raise HTTPException(status_code=400, detail=f"未知的模板 code: {payload.template}")
    if payload.template == "custom" and not payload.custom_prompt:
        raise HTTPException(status_code=400, detail="自定义模板必须提供 custom_prompt")

    # 校验：speaker_count 与 voice_assignments 一致
    if len(payload.voice_assignments) != payload.speaker_count:
        raise HTTPException(
            status_code=400,
            detail=f"voice_assignments 数量({len(payload.voice_assignments)})与 speaker_count 不符",
        )

    # PRD §19.2：单用户同时进行中任务 ≤ 3
    active_count = (
        db.query(Task)
        .filter(Task.user_id == current_user.user_id, Task.status.in_(_ACTIVE_STATUSES))
        .count()
    )
    if active_count >= settings.MAX_CONCURRENT_TASKS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"当前已有 {active_count} 个任务进行中，请等待任务完成后再提交",
        )

    # 创建任务记录（status=queued）
    task = Task(
        user_id=current_user.user_id,
        status=TaskStatus.QUEUED.value,
        generation_mode=payload.generation_mode,
        params=payload.model_dump(mode="json"),
        dialogue_text=payload.dialogue_text,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 入 Celery 队列（延迟导入避免循环）
    from app.tasks.generation import run_generation_task
    run_generation_task.delay(str(task.task_id))

    logger.info(f"Task {task.task_id} created by user {current_user.username}")
    return TaskOut.model_validate(task)


@router.get("", response_model=list[TaskListItem])
def list_tasks(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> list[TaskListItem]:
    """列出当前用户的任务（按 queued_at 倒序）。"""
    q = (
        db.query(Task)
        .filter(Task.user_id == current_user.user_id)
        .order_by(Task.queued_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[TaskListItem] = []
    for t in q.all():
        out = TaskListItem.model_validate(t)
        # 从 params 中抽便利字段
        params = t.params or {}
        out.topic = params.get("topic")
        out.language = params.get("language")
        out.speaker_count = params.get("speaker_count")
        items.append(out)
    return items


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> TaskOut:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权查看他人任务")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/retry", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def retry_task(task_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> TaskOut:
    """PRD §17.5: 失败任务重新生成。复用原参数创建新任务。"""
    src = db.query(Task).filter(Task.task_id == task_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="任务不存在")
    if src.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人任务")
    if src.status != TaskStatus.FAILED.value:
        raise HTTPException(status_code=400, detail="仅失败任务可重新生成")

    # 重新查并发限制
    active_count = (
        db.query(Task)
        .filter(Task.user_id == current_user.user_id, Task.status.in_(_ACTIVE_STATUSES))
        .count()
    )
    if active_count >= settings.MAX_CONCURRENT_TASKS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=f"当前已有 {active_count} 个任务进行中，请等待任务完成后再提交",
        )

    new_task = Task(
        user_id=current_user.user_id,
        status=TaskStatus.QUEUED.value,
        generation_mode=src.generation_mode,
        params=src.params,
        dialogue_text=src.dialogue_text if src.generation_mode == "manual" else None,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    from app.tasks.generation import run_generation_task
    run_generation_task.delay(str(new_task.task_id))
    logger.info(f"Task {new_task.task_id} retried from {src.task_id}")
    return TaskOut.model_validate(new_task)


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> TaskOut:
    """PRD §17.5：取消队列中或进行中的任务。"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人任务")
    if task.status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail=f"任务当前状态 {task.status} 不可取消")

    from datetime import datetime, timezone
    task.status = TaskStatus.CANCELLED.value
    task.cancelled_at = datetime.now(timezone.utc)
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    logger.info(f"Task {task.task_id} cancelled by user {current_user.username}")
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """删除任务记录（不影响已生成文件）。"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="无权操作他人任务")
    db.delete(task)
    db.commit()
