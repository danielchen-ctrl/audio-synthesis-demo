"""音频文件 Pydantic 模型。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag_id: uuid.UUID
    name: str


class AudioFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: uuid.UUID
    user_id: uuid.UUID
    file_name: str
    file_size: int
    duration_sec: float | None
    format: str | None
    language: str
    speaker_count: int
    scene: str
    topic: str | None
    source: str
    created_at: datetime
    folder_id: uuid.UUID | None = None
    deleted_at: datetime | None = None
    tags: list[TagOut] = []
    has_transcript: bool = False  # PRD §15.6 用于 SRT 徽章显示


class AudioFileUpdate(BaseModel):
    """PATCH /files/{id}：详情页编辑用。所有字段可选。"""
    file_name: str | None = Field(default=None, max_length=255)
    language: str | None = None
    speaker_count: int | None = Field(default=None, ge=1, le=10)
    scene: Literal["meeting", "interview", "medical", "custom", "other"] | None = None
    tag_names: list[str] | None = None  # 整体覆盖；None 表示不动


class AudioFileDownload(BaseModel):
    file_id: uuid.UUID
    download_url: str
    expires_in_sec: int


class TranscriptLine(BaseModel):
    speaker_id: str
    text: str
    start_time: float | None = None
    end_time: float | None = None


class TranscriptResponse(BaseModel):
    file_id: uuid.UUID
    has_transcript: bool
    lines: list[TranscriptLine]
    has_json: bool = False
    has_srt: bool = False
    json_download_url: str | None = None
    srt_download_url: str | None = None
