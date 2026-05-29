"""任务相关 Pydantic 模型。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 与 PRD §6.1 一致的语种枚举
LANG_CODES = Literal["zh", "en", "ja", "ko", "es", "fr", "de", "pt", "it", "ru", "ar", "id"]
SCENE_CODES = Literal["meeting", "interview", "medical", "custom", "other"]
GEN_MODE = Literal["llm", "manual"]
# 模板：'custom' 或 preset_topics.json 里的 id。运行时通过 service 校验。
TEMPLATE_CODES = str


class VoiceAssignment(BaseModel):
    """每个 speaker 分配的音色。"""
    voice_id: str
    voice_name: str | None = None


class TaskCreate(BaseModel):
    """对应 PRD §5/§6/§9/§10 的入参。"""
    generation_mode: GEN_MODE

    # 通用必填
    topic: str = Field(min_length=1, max_length=255)
    language: LANG_CODES
    speaker_count: int = Field(ge=1, le=10)
    voice_assignments: dict[str, VoiceAssignment]  # key 是 speaker 序号 "1", "2", ...
    audio_format: Literal["wav", "mp3", "m4a"] = "mp3"

    # LLM 模式必填
    template: TEMPLATE_CODES | None = None
    custom_prompt: str | None = None
    keywords: list[str] = Field(default_factory=list)
    target_duration_sec: int = Field(default=60, ge=10, le=43200)

    # manual 模式必填
    dialogue_text: str | None = None  # 用户直接输入的对话文本

    # 可选元数据（生成成功后挂在 AudioFile 上）
    folder_id: str | None = None      # UUID 字符串；None = 默认目录
    tag_names: list[str] = Field(default_factory=list)
    generate_scripts: bool = False    # PRD §12: 同时生成 JSON / SRT


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    status: str
    generation_mode: str
    progress: int
    params: dict
    dialogue_text: str | None
    file_id: uuid.UUID | None
    error_code: str | None
    error_message: str | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class DialoguePreviewRequest(BaseModel):
    """LLM 文本预览：仅生成对话文本，不入 Celery 队列。"""
    topic: str = Field(min_length=1, max_length=255)
    template: TEMPLATE_CODES
    custom_prompt: str | None = None
    language: LANG_CODES
    speaker_count: int = Field(ge=1, le=10)
    target_duration_sec: int = Field(default=60, ge=10, le=43200)
    keywords: list[str] = Field(default_factory=list)


class DialoguePreviewResult(BaseModel):
    dialogue_text: str
    line_count: int
    model: str


class TaskListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    status: str
    generation_mode: str
    progress: int
    queued_at: datetime
    finished_at: datetime | None
    error_message: str | None
    file_id: uuid.UUID | None
    # 从 params 中提取的便利字段
    topic: str | None = None
    language: str | None = None
    speaker_count: int | None = None
