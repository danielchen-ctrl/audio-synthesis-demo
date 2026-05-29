"""音色目录 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VoiceOut(BaseModel):
    voice_id: str
    name: str
    language: str
    gender: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VoiceCreateResponse(BaseModel):
    voice_id: str
    name: str
    verified: bool    # E2E 合成验证是否通过
    message: str      # 人可读的结果描述
